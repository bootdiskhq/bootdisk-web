#!/usr/bin/env python3
"""Build a static, read-only view of the original HTML menu on a K-CD.

The builder reads an explicit selection from a CD (HTML pages, the menu stylesheet and
raster images) and writes a filtered copy under ``<site>/cd-meny/<medium>/``. Nothing
from the CD is executed or copied wholesale: scripts, event handlers, forms, frames,
plug-ins and external requests are removed, and links to installers, PDF files, video
or search are replaced by a Norwegian note. Every byte that is copied is checked
against the SHA-256 in the medium's ingest manifest.

Each source entry of the medium is bound to its own original page through the
manifest's ``evidence.html_menu.page`` and the published archive index, never through
titles or folder numbers alone. Articles and video courses that share a page get their
own anchor and return link. The result is described in ``menu-index.json`` next to the
pages, and in the report the command prints or writes.

A build happens in a temporary folder and only replaces the medium's existing menu when
it is not blocked, so an unknown template or a byte mismatch never overwrites a known
good menu.

    python3 scripts/cd_menu.py --medium kcd-18-2013 \\
        --manifest .../kcd-18-2013-observe/manifest.json \\
        --source .../menu-source/kcd-18-2013 \\
        --index .../data/index.json --site BUILD_DIR

``--source`` may be left out. The builder then uses only the entry pages embedded in
the manifest and reports which other files it would have needed (``--dry-run`` makes
that explicit and writes nothing).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import posixpath
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

GENERATOR = "bootdisk-web cd_menu 1"
INDEX_SCHEMA = "bootdisk-cd-menu-1"
REGISTRY_SCHEMA = "bootdisk-cd-menu-index-1"
MENU_DIR = "cd-meny"
MEDIUM_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SAFE_TOKEN = re.compile(r"[A-Za-z0-9_-]+")
SAFE_CLASSES = re.compile(r"[A-Za-z0-9_ -]+")
RASTER = {".png": (b"\x89PNG\r\n\x1a\n",), ".gif": (b"GIF87a", b"GIF89a"), ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",)}

# Pages that are part of the menu but have no static meaning: an article search
# against a remote register, and a member card form meant for printing.
UNSUPPORTED_PAGES = {"html/search.html": "artikkelsøket", "html/membercard.html": "medlemskortet"}
# Interactive parts of the template that only work with the original scripts.
DROPPED_IDS = {"search", "searchresults", "singlehit", "noresults", "searchbringattention", "resultclone", "results",
               "basic-modal-content", "contentoverlay", "flashcontent", "videooverlay"}
DROPPED_TAGS = {"script", "style", "noscript", "iframe", "frame", "frameset", "object", "embed", "applet", "param",
                "svg", "math", "link", "meta", "base", "audio", "video", "source", "track", "canvas", "template",
                "textarea", "select", "option", "button", "map", "area", "title", "head"}
KEPT_TAGS = set("div span ul ol li p h1 h2 h3 h4 h5 h6 strong em b i u small sub sup table thead tbody tfoot tr td th "
                "caption br hr dl dt dd blockquote pre".split())
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
LAYOUT_PROPERTIES = {"float", "clear", "display", "width", "height", "padding", "padding-top", "padding-right",
                     "padding-bottom", "padding-left", "margin", "margin-top", "margin-right", "margin-bottom",
                     "margin-left", "font-size", "vertical-align", "text-align", "line-height", "font-weight"}
LAYOUT_VALUE = re.compile(r"(?:left|right|both|block|none|inline|inline-block|top|middle|bottom|center|bold|normal|auto|0|"
                          r"-?[0-9.]+(?:px|em|%|pt)?)(?: +(?:auto|0|-?[0-9.]+(?:px|em|%|pt)?)){0,3}")
TEMPLATE_IDS = {"wrapper", "menu", "contentwrapper"}
CSP = ("default-src 'none'; style-src 'self'; img-src 'self'; script-src 'none'; object-src 'none'; "
       "frame-src 'none'; connect-src 'none'; font-src 'none'; media-src 'none'; base-uri 'none'; form-action 'none'")

OFF_INSTALL = "installasjon er ikke tilgjengelig i arkivvisningen"
OFF_EXTERNAL = "ekstern lenke, ikke aktiv i arkivvisningen"
OFF_PDF = "PDF-filen vises ikke i arkivvisningen"
OFF_VIDEO = "videoavspilling er ikke tilgjengelig i arkivvisningen"
OFF_SEARCH = "søket er ikke aktivt i arkivvisningen"
OFF_SCRIPT = "funksjonen krevde CD-ens skript og er ikke aktiv"
OFF_PAGE = "siden er ikke med i arkivvisningen"
OFF_BROKEN = "originalsiden er ødelagt på CD-en og vises ikke"


class BuildBlocked(Exception):
    """A problem that stops this medium without touching an existing menu."""


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text or "")).strip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- source

class Source:
    """The manifest's file inventory plus the bytes that can be read for it.

    Bytes come from an extracted source folder or from the documents embedded in the
    manifest. Either way they must match the inventory's size and SHA-256.
    """

    def __init__(self, manifest: dict, root: Path | None):
        self.inventory = {item["path"]: item for item in manifest.get("file_inventory", [])}
        self.folded = defaultdict(list)
        for name in self.inventory:
            self.folded[name.casefold()].append(name)
        self.documents = {path: doc for path, doc in ((manifest.get("source") or {}).get("documents") or {}).items()
                          if isinstance(doc, dict) and "raw_base64" in doc}
        self.root = root.resolve() if root else None

    def resolve(self, page: str, url: str) -> tuple[str | None, str | None]:
        """Return (inventory path, None) or (None, reason) for a reference in ``page``."""
        if url is None:
            return None, "tom adresse"
        url = url.strip()
        if not url or url.startswith("#"):
            return None, "tom adresse"
        parts = urlsplit(url)
        if parts.scheme or parts.netloc:
            return None, "ekstern"
        raw = parts.path
        if not raw or raw.startswith("/") or "\\" in raw or "\x00" in raw:
            return None, "ugyldig sti"
        try:
            decoded = unquote(raw, encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            decoded = unquote(raw, encoding="cp1252", errors="strict")
        if any(ord(ch) < 32 for ch in decoded) or "\\" in decoded or decoded.startswith("/"):
            return None, "ugyldig sti"
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(page), decoded))
        if joined == "." or joined.startswith("../") or joined == ".." or joined.startswith("/"):
            return None, "utenfor CD-en"
        if joined in self.inventory:
            return joined, None
        matches = self.folded.get(joined.casefold(), [])
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, "tvetydig"
        return None, "finnes ikke på CD-en"

    def read(self, path: str) -> bytes | None:
        """Bytes for an inventory path, or None when they are not available here."""
        item = self.inventory.get(path)
        if item is None:
            raise BuildBlocked(f"{path} er ikke i manifestets filinventar")
        data = None
        if self.root is not None:
            candidate = self.root / path
            if candidate.is_symlink():
                raise BuildBlocked(f"{path} er en symbolsk lenke i kildeutvalget")
            if candidate.is_file():
                resolved = candidate.resolve()
                if self.root not in resolved.parents:
                    raise BuildBlocked(f"{path} peker ut av kildeutvalget")
                data = resolved.read_bytes()
        if data is None and path in self.documents:
            data = base64.b64decode(self.documents[path]["raw_base64"], validate=True)
        if data is None:
            return None
        if len(data) != item.get("size", len(data)) or sha256(data) != item["sha256"]:
            raise BuildBlocked(f"{path}: byte stemmer ikke med manifestet")
        return data


# --------------------------------------------------------------------------- html tree

class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict, parent: "Node | None" = None):
        self.tag, self.attrs, self.children, self.parent = tag, attrs, [], parent

    def text(self) -> str:
        return "".join(child if isinstance(child, str) else child.text() for child in self.children)

    def walk(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()

    def find(self, tag: str | None = None, id: str | None = None, cls: str | None = None) -> list["Node"]:
        return [node for node in self.walk()
                if (tag is None or node.tag == tag) and (id is None or node.attrs.get("id") == id)
                and (cls is None or cls in (node.attrs.get("class") or "").split())]


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {key.lower(): (value if value is not None else "") for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {key.lower(): (value if value is not None else "") for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for position in range(len(self.stack) - 1, 0, -1):
            if self.stack[position].tag == tag:
                del self.stack[position:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def decode_html(data: bytes) -> str:
    """Decode a menu page the way a browser would, but refuse ambiguous bytes."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8")
    head = data[:4096].decode("ascii", "replace").lower()
    match = re.search(r"charset\s*=\s*['\"]?([a-z0-9_-]+)", head)
    charset = match[1] if match else "windows-1252"
    if charset in ("utf-8", "utf8"):
        return data.decode("utf-8")
    # ISO-8859-1 is read as Windows-1252, as browsers do. Its five undefined bytes are
    # an error here instead of a silent replacement.
    return data.decode("cp1252")


def parse(data: bytes) -> Node:
    builder = TreeBuilder()
    builder.feed(decode_html(data))
    builder.close()
    return builder.root


# --------------------------------------------------------------------------- build

class MenuBuild:
    def __init__(self, medium: str, manifest_path: Path, source_root: Path | None, index: dict, label: str | None = None):
        if not MEDIUM_RE.fullmatch(medium):
            raise BuildBlocked(f"ugyldig medie-ID {medium!r}")
        raw = manifest_path.read_bytes()
        self.manifest_ref = "sha256:" + sha256(raw)
        self.manifest = json.loads(raw)
        self.medium = medium
        self.source = Source(self.manifest, source_root)
        self.index = index
        self.label = label or self._medium_label()
        self.files: dict[str, bytes] = {}
        self.asset_rows: dict[str, dict] = {}
        self.missing_assets: list[dict] = []
        self.unavailable_assets: set[str] = set()
        self.disabled = Counter()
        self.deviations: list[dict] = []
        self.layout: dict[str, str] = {}
        self.routes: dict[str, str] = {}
        self.unbound: list[dict] = []
        self.broken_pages: dict[str, str] = {}
        self.shared_pages: dict[str, list[str]] = {}
        self.pages_built: list[str] = []
        self.pages_unavailable: list[str] = []

    # -- identity -----------------------------------------------------------------
    def _medium_label(self) -> str:
        for medium in self.index.get("media", []):
            if medium.get("id") == self.medium:
                return medium.get("medium") or self.medium
        return self.medium

    def bind_entries(self):
        """Pair manifest entries with published source posts of this medium only."""
        if self.manifest.get("source", {}).get("format") != "kcd-html-menu-1":
            raise BuildBlocked("ukjent menyformat i manifestet: " + str(self.manifest.get("source", {}).get("format")))
        published = [row for row in self.index.get("entries", []) if row.get("medium_id") == self.medium]
        if not published:
            raise BuildBlocked("ingen publiserte kildeposter for mediet i indeksen")
        matching = [row for row in published if row.get("source_manifest") == self.manifest_ref]
        if not matching:
            raise BuildBlocked("indeksens kildeposter peker på et annet manifest (" + published[0].get("source_manifest", "?") + ")")
        by_source = {row["source_entry"]: row for row in matching}
        self.entries = []
        seen = set()
        for entry in self.manifest.get("entries", []):
            sid = entry.get("source_id")
            evidence = (entry.get("evidence") or {}).get("html_menu") or {}
            page = evidence.get("page")
            observation = evidence.get("observation") or {}
            key = f"{self.medium}--{sid}"
            if not sid or not SAFE_TOKEN.fullmatch(sid) or sid in seen:
                self.unbound.append({"entry": key, "reason": "ugyldig eller duplisert kilde-ID i manifestet"})
                continue
            seen.add(sid)
            row = by_source.get(sid)
            if row is None or row.get("entry") != key:
                self.unbound.append({"entry": key, "reason": "ingen publisert kildepost med samme manifest og kilde-ID"})
                continue
            if not page or page not in self.source.inventory or not page.lower().endswith(".html"):
                self.unbound.append({"entry": key, "reason": "manifestet oppgir ingen gyldig menyside"})
                continue
            self.entries.append({"sid": sid, "key": key, "page": page, "title": clean(observation.get("title") or entry.get("normalized", {}).get("title")),
                                 "category": observation.get("category")})
        manifest_sids = {entry["sid"] for entry in self.entries} | {u["entry"].split("--", 1)[1] for u in self.unbound}
        for row in published:
            if row.get("source_manifest") != self.manifest_ref:
                self.unbound.append({"entry": row["entry"], "reason": "kildeposten er bygget fra et annet manifest"})
            elif row["source_entry"] not in manifest_sids:
                self.unbound.append({"entry": row["entry"], "reason": "kildeposten finnes ikke i manifestet"})

    # -- paths --------------------------------------------------------------------
    @staticmethod
    def href(page: str, target: str, fragment: str = "") -> str:
        relative = posixpath.relpath(target, posixpath.dirname(page) or ".")
        return quote(relative, safe="/._-") + (("#" + fragment) if fragment else "")

    def site_href(self, page: str, target: str) -> str:
        """Link from a menu page to a page at the site root (index.html, archive.html)."""
        start = posixpath.join(MENU_DIR, self.medium, posixpath.dirname(page))
        return posixpath.relpath(target.split("?", 1)[0], start) + (("?" + target.split("?", 1)[1]) if "?" in target else "")

    def entry_href(self, page: str, key: str) -> str:
        return self.site_href(page, "index.html?entry=" + quote(key, safe="-"))

    def archive_href(self, page: str) -> str:
        return self.site_href(page, "archive.html?medium=" + quote(self.medium, safe="-"))

    # -- assets -------------------------------------------------------------------
    def asset(self, page: str, url: str) -> str | None:
        path, reason = self.source.resolve(page, url)
        if path is None:
            self.missing_assets.append({"page": page, "url": url, "reason": reason})
            return None
        suffix = posixpath.splitext(path)[1].lower()
        if suffix not in RASTER:
            self.missing_assets.append({"page": page, "url": url, "reason": "ikke et rasterbilde"})
            return None
        if path not in self.asset_rows:
            data = self.source.read(path)
            if data is None:
                self.unavailable_assets.add(path)
                return self.href(page, path)
            kinds = [name for name, magics in RASTER.items() if data.startswith(magics)]
            if not kinds:
                self.missing_assets.append({"page": page, "url": url, "reason": "filinnholdet er ikke et gyldig bilde"})
                return None
            self.files[path] = data
            self.asset_rows[path] = {"path": path, "sha256": sha256(data), "bytes": len(data)}
            if suffix not in kinds and not (suffix in (".jpg", ".jpeg") and ".jpg" in kinds):
                # Seen on the CDs: PNG files named .jpg. Browsers read them by content.
                self.asset_rows[path]["note"] = "filendelsen stemmer ikke med bildeformatet"
        return self.href(page, path)

    def layout_class(self, style: str) -> str:
        rules = []
        for item in (style or "").lower().split(";"):
            name, _, value = item.partition(":")
            name, value = name.strip(), value.strip()
            if name in LAYOUT_PROPERTIES and LAYOUT_VALUE.fullmatch(value):
                rules.append(f"{name}:{value}")
        if not rules:
            return ""
        rule = ";".join(rules)
        return self.layout.setdefault(rule, f"bd-layout-{len(self.layout)}")

    # -- rendering ----------------------------------------------------------------
    def off(self, label: str, reason: str) -> str:
        self.disabled[reason] += 1
        label = label.strip()
        inner = (html.escape(label) + " ") if label else ""
        return f'<span class="bd-off">{inner}<small class="bd-note">({html.escape(reason)})</small></span>'

    def link(self, node: Node, page: str, inner: str) -> str:
        target = node.attrs.get("href", "")
        onclick = node.attrs.get("onclick", "")
        text = clean(node.text())
        if not inner.strip():
            return ""
        lowered = target.strip().lower()
        if lowered.startswith("javascript:") or (onclick and lowered in ("", "#")):
            if "print" in (lowered + onclick).lower():
                return self.off(text, "utskrift er ikke tilgjengelig i arkivvisningen")
            if ".pdf" in (lowered + onclick).lower():
                return self.off(text, OFF_PDF)
            return self.off(text, OFF_SCRIPT)
        if lowered.startswith(("http:", "https:", "ftp:", "mailto:", "//")):
            return self.off(text, OFF_EXTERNAL)
        path, reason = self.source.resolve(page, target)
        if path is None:
            return self.off(text, OFF_EXTERNAL if reason == "ekstern" else OFF_PAGE)
        fragment = urlsplit(target).fragment
        if path in self.broken_pages:
            return self.off(text, OFF_BROKEN)
        if path in self.page_set and not onclick:
            # A fragment is kept only when the target page has that id; otherwise the
            # link opens the top of the page instead of pointing at nothing.
            keep = fragment if SAFE_TOKEN.fullmatch(fragment or "") and fragment in self.page_ids.get(path, set()) else ""
            return f'<a href="{html.escape(self.href(page, path, keep))}">{inner}</a>'
        suffix = posixpath.splitext(path)[1].lower()
        if suffix in (".exe", ".msi", ".zip", ".rar", ".7z", ".bat", ".cmd", ".com"):
            return self.off(text, OFF_INSTALL)
        if suffix == ".pdf":
            return self.off(text, OFF_PDF)
        if suffix in (".flv", ".swf", ".wmv", ".mp4", ".avi", ".xap"):
            return self.off(text, OFF_VIDEO)
        if path in UNSUPPORTED_PAGES:
            return self.off(text, f"{UNSUPPORTED_PAGES[path]} er ikke aktivt i arkivvisningen")
        return self.off(text, OFF_PAGE)

    def control(self, node: Node) -> str:
        kind = (node.attrs.get("type") or "text").lower()
        onclick = node.attrs.get("onclick", "")
        label = clean(node.attrs.get("value", ""))
        if kind in ("text", "search", "password", "hidden", "checkbox", "radio", "file"):
            return ""
        if "show(" in onclick or "video" in onclick.lower():
            return self.off(label or "Spill av video", OFF_VIDEO)
        if ".pdf" in onclick.lower() or "article" in onclick.lower():
            return self.off(label or "Les veiledning", "artikkelen åpnes ikke i arkivvisningen")
        if "print" in onclick.lower():
            return self.off(label or "Skriv ut", "utskrift er ikke tilgjengelig i arkivvisningen")
        if node.attrs.get("id") in ("btnnew", "searchbutton") or "search" in onclick.lower():
            return self.off(label or "Søk", OFF_SEARCH)
        if "accept" in onclick.lower() or "modal" in onclick.lower():
            return ""
        if kind in ("submit", "reset", "image"):
            return self.off(label or "Send", "skjemaet er ikke aktivt i arkivvisningen")
        return self.off(label or "Knapp", OFF_SCRIPT)

    def render(self, node, page: str, extras: dict) -> str:
        if isinstance(node, str):
            return html.escape(node, quote=False)
        tag, attrs = node.tag, node.attrs
        if tag in DROPPED_TAGS or attrs.get("id") in DROPPED_IDS:
            return ""
        if tag == "input":
            return self.control(node)
        if tag == "form":
            return "".join(self.render(child, page, extras) for child in node.children)
        inner = "".join(self.render(child, page, extras) for child in node.children)
        if tag == "a":
            return self.link(node, page, inner)
        layout = self.layout_class(attrs.get("style", ""))
        if tag == "img":
            url = self.asset(page, attrs.get("src", ""))
            if not url:
                gone = self.missing_assets and self.missing_assets[-1]["reason"] == "finnes ikke på CD-en"
                return '<span class="bd-missing">[' + ("Bildet mangler på CD-en" if gone else "Bildet vises ikke i arkivvisningen") + ']</span>'
            size = "".join(f' {name}="{attrs[name]}"' for name in ("width", "height") if re.fullmatch(r"[0-9]{1,4}", attrs.get(name, "")))
            css = (" " + attrs["class"] if SAFE_CLASSES.fullmatch(attrs.get("class", "") or "-") and attrs.get("class") else "") + (" " + layout if layout else "")
            return f'<img src="{html.escape(url)}" alt="{html.escape(attrs.get("alt", ""))}"{size}' + (f' class="{css.strip()}"' if css.strip() else "") + ">"
        if tag not in KEPT_TAGS:
            return inner
        if tag in ("br", "hr"):
            return f"<{tag}>"
        element_id = attrs.get("id", "")
        classes = attrs.get("class", "") if SAFE_CLASSES.fullmatch(attrs.get("class", "") or "-") else ""
        prefix, suffix = "", ""
        hook = extras.get(id(node))
        if hook:
            element_id = hook.get("id", element_id)
            classes = (classes + " " + hook.get("class", "")).strip()
            prefix, suffix = hook.get("before", ""), hook.get("after", "")
        if layout:
            classes = (classes + " " + layout).strip()
        out = f"<{tag}"
        if element_id and SAFE_TOKEN.fullmatch(element_id):
            out += f' id="{element_id}"'
        if classes:
            out += f' class="{html.escape(classes)}"'
        for name in ("colspan", "rowspan"):
            if re.fullmatch(r"[0-9]{1,2}", attrs.get(name, "")):
                out += f' {name}="{attrs[name]}"'
        return out + ">" + prefix + inner + suffix + f"</{tag}>"

    # -- css ----------------------------------------------------------------------
    def stylesheet(self, path: str) -> bytes | None:
        data = self.source.read(path)
        if data is None:
            return None
        text = data.decode("utf-8-sig") if data.startswith(b"\xef\xbb\xbf") else data.decode("cp1252")
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"@import[^;]*;", "", text, flags=re.I)
        text = re.sub(r"@charset[^;]*;", "", text, flags=re.I)
        # Declarations that run code in old browsers are dropped whole.
        text = re.sub(r"(?i)[^;{}]*(?:expression\s*\(|behavior\s*:|-moz-binding\s*:|javascript:)[^;{}]*;?", "", text)

        def url(match):
            asset = self.asset(path, match[1].strip("'\" "))
            return f'url("{asset}")' if asset else "none"
        text = re.sub(r"url\(([^)]*)\)", url, text, flags=re.I)
        return text.encode("utf-8")

    # -- pages --------------------------------------------------------------------
    def page_tree(self, page: str) -> tuple[Node | None, str | None]:
        data = self.source.read(page)
        if data is None:
            return None, "ikke i kildeutvalget"
        try:
            tree = parse(data)
        except UnicodeDecodeError as error:
            return None, f"ugyldig tegnkoding (byte {error.start})"
        body = tree.find("body")
        if not body or not body[0].find(id="contentwrapper"):
            return None, "siden mangler menymalens innholdsområde"
        return tree, None

    def discover_pages(self) -> list[str]:
        pages = {"default.html"}
        pages.update(entry["page"] for entry in self.entries)
        for name in self.source.inventory:
            if posixpath.dirname(name) == "html" and name.lower().endswith(".html") and name not in UNSUPPORTED_PAGES:
                pages.add(name)
        return sorted(pages)

    def bar(self, page: str, back: dict | None) -> str:
        links = [f'<a href="{html.escape(self.href(page, "default.html"))}">Menyforsiden</a>',
                 f'<a href="{html.escape(self.archive_href(page))}">CD-oversikt i Bootdisk</a>',
                 f'<a href="{html.escape(self.href(page, "index.html"))}">Om visningen</a>']
        if back:
            links.insert(0, f'<a class="bd-back" href="{html.escape(self.entry_href(page, back["key"]))}">← Til kildeposten: {html.escape(back["title"] or back["key"])}</a>')
        return ('<nav class="bd-bar" aria-label="Bootdisk-arkivvisning"><strong class="bd-brand">Bootdisk · '
                + html.escape(self.label) + ' · original CD-meny</strong>' + "".join(links)
                + '<span class="bd-hint">Menyen er laget for en bred skjerm. Dra sidelengs i menyen for å se hele siden.</span></nav>')

    def document(self, title: str, body: str, page: str, sheets: list[str]) -> bytes:
        links = "".join(f'<link rel="stylesheet" href="{html.escape(self.href(page, sheet))}">' for sheet in sheets)
        return ('<!doctype html><html lang="nb"><head><meta charset="utf-8">'
                f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
                '<meta name="referrer" content="no-referrer"><meta name="robots" content="noindex">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{html.escape(title)}</title>{links}</head><body class="bd-menu">{body}</body></html>').encode("utf-8")

    def shared_block(self, tree: Node, entry: dict) -> Node | None:
        for cls in ("guide", "video"):
            matches = [block for block in tree.find(cls=cls)
                       if any(clean(head.text()) == entry["title"] for head in block.find(cls=cls + "headline"))]
            if matches:
                return matches[0] if len(matches) == 1 else None
        return None

    def build(self) -> dict:
        self.bind_entries()
        self.page_set = set(self.discover_pages())
        trees = {}
        for page in sorted(self.page_set):
            tree, problem = self.page_tree(page)
            if tree is not None:
                trees[page] = tree
            elif problem == "ikke i kildeutvalget":
                self.pages_unavailable.append(page)
            else:
                self.broken_pages[page] = problem
        if "default.html" in self.broken_pages:
            raise BuildBlocked("menyforsiden kan ikke leses: " + self.broken_pages["default.html"])
        if "default.html" in trees:
            ids = {node.attrs.get("id") for node in trees["default.html"].walk()}
            if not TEMPLATE_IDS <= ids:
                raise BuildBlocked("ukjent menymal på forsiden (mangler " + ", ".join(sorted(TEMPLATE_IDS - ids)) + ")")
        self.page_set -= set(self.broken_pages)
        self.page_ids = {page: {node.attrs.get("id") for node in tree.walk() if node.attrs.get("id")} for page, tree in trees.items()}

        by_page = defaultdict(list)
        for entry in self.entries:
            by_page[entry["page"]].append(entry)
        extras = defaultdict(dict)
        backs = {}
        for page, entries in by_page.items():
            if page in self.broken_pages:
                for entry in entries:
                    self.unbound.append({"entry": entry["key"], "title": entry["title"], "reason": "ødelagt originalside: " + self.broken_pages[page],
                                         "explanation": OFF_BROKEN})
                continue
            tree = trees.get(page)
            if len(entries) > 1:
                self.shared_pages[page] = [entry["sid"] for entry in entries]
            for entry in entries:
                if tree is None:
                    # Dry run without the page bytes: the route is known but not verified.
                    self.unbound.append({"entry": entry["key"], "reason": "menysiden er ikke i kildeutvalget"})
                    continue
                block = self.shared_block(tree, entry)
                if len(entries) == 1 and block is None:
                    content = tree.find(id="content") or tree.find(id="widecontent") or tree.find(id="largecontent")
                    heads = [clean(node.text()) for node in (content[0].find("h1") if content else [])]
                    if entry["title"] not in heads and entry["title"] not in clean(tree.text()):
                        self.unbound.append({"entry": entry["key"], "reason": "tittelen fra manifestet står ikke på menysiden"})
                        continue
                    backs[page] = entry
                    self.routes[entry["key"]] = page
                    continue
                if block is None:
                    self.unbound.append({"entry": entry["key"], "reason": "fant ikke én entydig omtale på den delte siden"})
                    continue
                anchor = "post-" + entry["sid"]
                extras[page][id(block)] = {"id": anchor, "class": "bd-anchor", "before": "",
                                           "after": f'<p class="bd-post"><a href="{html.escape(self.entry_href(page, entry["key"]))}">← Til kildeposten i Bootdisk: {html.escape(entry["title"])}</a></p>'}
                self.routes[entry["key"]] = page + "#" + anchor

        for page in sorted(trees):
            tree = trees[page]
            body = tree.find("body")[0]
            titles = tree.find("title")
            title = clean(titles[0].text()) if titles else self.label
            content = self.render(body, page, extras[page])
            # The archive's own bar and notes are kept outside the original layout.
            inner = content[len("<body>"):-len("</body>")] if content.startswith("<body") else content
            sheets = ["html/main.css", "archive.css"] if "html/main.css" in self.source.inventory else ["archive.css"]
            self.files[page] = self.document(f"{title} · arkivvisning", self.bar(page, backs.get(page)) + '<div class="bd-original">' + inner + "</div>", page, sheets)
            self.pages_built.append(page)

        css = self.stylesheet("html/main.css") if "html/main.css" in self.source.inventory else None
        if css is not None:
            self.files["html/main.css"] = css
        elif "html/main.css" in self.source.inventory:
            self.pages_unavailable.append("html/main.css")
        self.files["archive.css"] = (ARCHIVE_CSS + "".join(f".{name}{{{rule}}}\n" for rule, name in self.layout.items())).encode("utf-8")
        self.files["index.html"] = self.landing()
        return self.report()

    def landing(self) -> bytes:
        disabled = sorted(self.disabled)
        body = ('<main class="bd-landing"><p><a href="' + html.escape(self.archive_href("index.html")) + '">← ' + html.escape(self.label) + ' i Bootdisk</a></p>'
                f'<h1>{html.escape(self.label)} · original CD-meny</h1>'
                '<p><a class="bd-start" href="default.html">Bla i CD-menyen →</a></p>'
                '<p>Dette er en statisk arkivvisning av menyen slik den ble levert på CD-en. Tekst, rekkefølge, menybilder og '
                'utforming kommer fra platen, også feil som sto i originalen. Bootdisk-feltet øverst og merknadene i parentes er lagt til av arkivet.</p>'
                '<p>Installasjon, søk, videoavspilling, PDF-filer og lenker til nettsteder er ikke aktive. Ingen programmer eller skript fra CD-en kjøres.</p>')
        published = {row.get("entry") for row in self.index.get("entries", []) if row.get("medium_id") == self.medium}
        rows = [row for row in self.unbound if row["entry"] in published]
        if rows:
            # Only posts that exist in the archive are linked, so the list has no dead links.
            body += '<h2>Kildeposter uten egen lenke i menyen</h2><ul>' + "".join(
                f'<li><a href="{html.escape(self.entry_href("index.html", row["entry"]))}">{html.escape(row.get("title") or row["entry"])}</a>: {html.escape(row.get("explanation") or row["reason"])}</li>'
                for row in rows) + "</ul>"
        if disabled:
            body += "<h2>Deaktivert i arkivvisningen</h2><ul>" + "".join(f"<li>{html.escape(reason)}: {self.disabled[reason]}</li>" for reason in disabled) + "</ul>"
        body += "</main>"
        return self.document(f"{self.label} · original CD-meny · Bootdisk", body, "index.html", ["archive.css"])

    def report(self) -> dict:
        problems = []
        if self.pages_unavailable:
            problems.append("kildeutvalget mangler filer")
        if any(row["reason"] != "finnes ikke på CD-en" for row in self.missing_assets):
            problems.append("avviste bilder eller bildeadresser")
        if any(row["reason"] == "finnes ikke på CD-en" and not row["page"].endswith(".css") for row in self.missing_assets):
            problems.append("menysider viser bilder som mangler på CD-en")
        if self.unbound:
            problems.append("kildeposter uten verifisert rute")
        if self.broken_pages:
            problems.append("ødelagte originalsider")
        return {
            "schema": INDEX_SCHEMA,
            "generator": GENERATOR,
            "medium_id": self.medium,
            "medium": self.label,
            "manifest": self.manifest_ref,
            "image_sha256": (self.manifest.get("media") or {}).get("sha256"),
            "start": "default.html",
            "status": "review" if problems else "ready",
            "problems": problems,
            "counts": {
                "source_entries": len(self.manifest.get("entries", [])),
                "published_entries": sum(1 for row in self.index.get("entries", []) if row.get("medium_id") == self.medium),
                "routes": len(self.routes),
                "anchored_routes": sum("#" in route for route in self.routes.values()),
                "shared_pages": len(self.shared_pages),
                "pages_built": len(self.pages_built),
                "pages_unavailable": len(self.pages_unavailable),
                "broken_pages": len(self.broken_pages),
                "images": len(self.asset_rows),
                "images_unavailable": len(self.unavailable_assets),
                "missing_images": len(self.missing_assets),
                "disabled": sum(self.disabled.values()),
            },
            "routes": dict(sorted(self.routes.items())),
            "shared_pages": self.shared_pages,
            "unbound": sorted(self.unbound, key=lambda row: row["entry"]),
            "broken_pages": self.broken_pages,
            "pages": sorted(self.pages_built),
            "pages_unavailable": sorted(self.pages_unavailable),
            "images": [self.asset_rows[name] for name in sorted(self.asset_rows)],
            "images_unavailable": sorted(self.unavailable_assets),
            "missing_images": self.missing_assets,
            "disabled": dict(sorted(self.disabled.items())),
        }


ARCHIVE_CSS = """/* Bootdisk archive layer: kept visually apart from the original menu. */
.bd-bar{position:sticky;top:0;z-index:1000;display:flex;flex-wrap:wrap;gap:.4em 1.1em;align-items:center;margin:0;padding:.5em 1em;background:#faf8f1;color:#172b40;font:14px/1.4 system-ui,sans-serif;border-bottom:3px double #6d6a5f;text-align:left}
.bd-bar a,.bd-post a,.bd-landing a{color:#164981!important;text-decoration:underline!important;background:none!important}
.bd-brand{font-weight:700;margin-right:.4em}
.bd-back{font-weight:700}
.bd-post{display:block;margin:.5em 0;padding:4px 8px;background:#faf8f1;border-left:4px solid #ab7016;font:13px/1.4 system-ui,sans-serif;clear:both}
.bd-off{cursor:default}
.bd-note{font:12px/1.3 system-ui,sans-serif;color:#3d3d3d;background:#faf8f1;padding:0 2px}
.bd-missing{display:inline-block;padding:2px 4px;border:1px dashed #6d6a5f;background:#faf8f1;color:#3d3d3d;font:12px system-ui,sans-serif}
.bd-anchor{scroll-margin-top:4rem}
.bd-anchor:target{outline:3px solid #ab7016;outline-offset:3px;background-color:rgba(255,243,196,.6)}
a:focus-visible{outline:3px solid #e07b00!important;outline-offset:2px}
.bd-landing{max-width:46em;margin:2em auto;padding:1em;font:17px/1.5 system-ui,sans-serif;color:#152939;background:#fff}
.bd-start{font-weight:700}
.bd-hint{display:none;flex-basis:100%;font-size:13px;color:#3d3d3d}
@media (max-width:700px){.bd-original{overflow-x:auto}.bd-bar{position:static}.bd-hint{display:block}}
"""


# --------------------------------------------------------------------------- output

def write_menu(site: Path, medium: str, build: MenuBuild, report: dict) -> Path:
    """Write into a temporary folder, then swap it in for the medium's menu."""
    parent = site / MENU_DIR
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{medium}-", dir=parent))
    try:
        for name, data in build.files.items():
            target = temporary / name
            if temporary not in target.resolve().parents:
                raise BuildBlocked(f"utdata utenfor menymappen: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        report = dict(report, files=[{"path": name, "sha256": sha256(data), "bytes": len(data)} for name, data in sorted(build.files.items())])
        (temporary / "menu-index.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        final = parent / medium
        old = parent / f".{medium}.previous"
        if old.exists():
            shutil.rmtree(old)
        if final.exists():
            final.rename(old)
        temporary.rename(final)
        if old.exists():
            shutil.rmtree(old)
        return final
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def register(site: Path, menus: list[dict]) -> Path:
    """Write cd-meny/menus.json, the only file the archive pages read."""
    path = site / MENU_DIR / "menus.json"
    media = {}
    for report in sorted(menus, key=lambda row: row["medium_id"]):
        prefix = f"{MENU_DIR}/{report['medium_id']}/"
        media[report["medium_id"]] = {
            "manifest": report["manifest"],
            "start": prefix + report["start"],
            "routes": {key: prefix + route for key, route in report["routes"].items()},
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": REGISTRY_SCHEMA, "media": media}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_medium(medium: str, manifest: Path, source: Path | None, index: dict, site: Path | None, dry_run: bool = False) -> dict:
    try:
        if source is None and not dry_run:
            raise BuildBlocked("kildeutvalget mangler; bare tørrkjøring er mulig fra manifestet")
        build = MenuBuild(medium, manifest, source, index)
        report = build.build()
        if source is None:
            # Only the entry pages embedded in the manifest were read. Missing files are
            # expected here, so they are listed as unchecked rather than as problems.
            report["status"] = "dry_run"
            report["problems"] = [item for item in report["problems"] if item != "kildeutvalget mangler filer"]
            report["unchecked"] = {"pages": report["counts"]["pages_unavailable"], "images": report["counts"]["images_unavailable"],
                                   "template": "default.html" not in report["pages"]}
        elif report["pages_unavailable"] and not dry_run:
            raise BuildBlocked("kildeutvalget mangler " + ", ".join(report["pages_unavailable"][:5]))
        if site is not None and not dry_run:
            write_menu(site, medium, build, report)
        return report
    except BuildBlocked as error:
        return {"schema": INDEX_SCHEMA, "medium_id": medium, "status": "blocked", "blocked": str(error)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--medium", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source", type=Path, help="extracted menu selection (default: only manifest documents)")
    parser.add_argument("--index", required=True, type=Path, help="published data/index.json")
    parser.add_argument("--site", type=Path, help="site folder; menu goes to SITE/cd-meny/MEDIUM")
    parser.add_argument("--dry-run", action="store_true", help="check and report without writing")
    parser.add_argument("--register", action="store_true", help="also write SITE/cd-meny/menus.json for this medium")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    index = json.loads(args.index.read_text(encoding="utf-8"))
    report = build_medium(args.medium, args.manifest, args.source, index, None if args.dry_run else args.site, args.dry_run)
    if args.register and args.site and report["status"] in ("ready", "review"):
        register(args.site, [report])
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    summary = {key: report.get(key) for key in ("medium_id", "status", "blocked", "problems", "counts")}
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
