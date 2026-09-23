# Bootdisk Web 1.2.0-rc3

Adds the five-disc trial to the previous two-disc collection: 178 entries from
seven CDs, 172 original descriptions, and 576 public image objects. See
[five-disc results and limitations](five-disc-trial.md).

The release builder accepts per-medium `description_requirements.minimum_count`
in addition to image requirements, and reports description coverage. The new
regression proves missing original wording stops packaging and restoring it
permits the same build. The frontend runtime and local curator are unchanged.

Local release inputs and original media remain outside Git. Only the public
allowlist, generated data and referenced image objects are packaged. This version
supersedes rc2 for the planned site update; building it does not deploy it.
