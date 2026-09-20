"""Readable evidence must preserve selections across duplicate source IDs."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node required')
class EvidenceDisplayTests(unittest.TestCase):
    def test_duplicate_original_keeps_existing_reference_and_distinct_text(self):
        script = r'''
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const context = vm.createContext({CONTENT_KINDS: [], DISTRIBUTION_KINDS: []});
vm.runInContext(fs.readFileSync('curate.js','utf8'), context);
vm.runInContext(`
const ref = {manifest:'m1', entry:'K3'};
const normalized = {id:'old', field:'normalized.description', observation:'Original text', source_ref:ref};
const raw = {...normalized, id:'new', field:'raw.Global'};
const merged = displayEvidence([normalized, raw]);
if (merged.length !== 1 || merged[0].id !== 'old') throw Error('Wrong visible source');
if (!evidenceIds(merged[0]).includes('new')) throw Error('Existing raw selection lost');
if (!evidenceIds(merged[0]).includes('old')) throw Error('Existing normalized selection lost');
if (displayEvidence([raw,normalized]).length !== 1) throw Error('Order-dependent merge');
if (displayEvidence([normalized,{...raw,observation:'Different text'}]).length !== 2) throw Error('Different wording lost');
if (displayEvidence([normalized,{...raw,source_ref:{manifest:'m2',entry:'K3'}}]).length !== 2) throw Error('Different source lost');
if (raw.aliases || normalized.aliases) throw Error('Source data mutated');
`, context);
'''
        subprocess.run(['node', '-e', script], cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True, text=True)
