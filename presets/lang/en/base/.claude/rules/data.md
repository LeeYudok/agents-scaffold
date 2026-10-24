---
paths:
  - "data/**/*.py"
  - "data/**/*.sql"
---

# Data Script Rules (data/)

Baseline for Python scripts that collect/clean/load external or public datasets.

## P0
- **Never stage bulk data in git**: raw/derived files under `data/` (*.csv, *.xls, temp import
  dirs) must never be committed. When deleting/moving files, verify the `.gitignore` rules still
  cover them.

## P1
- **Encodings**: external/public CSVs often use legacy encodings — declare the encoding
  explicitly when reading (`encoding=...`), and normalize final load files to `utf-8`.
- **Memory**: no whole-file loads (`readlines()`) for large CSVs — use line generators/chunked
  processing to prevent OOM.
- **Validate key fields up front**: check the key-field format first and skip (and count)
  malformed rows.
- **Progress logs**: print processed/skipped/success·failure counts — e.g.
  `print(f"{basename}: kept={n} skipped={s} -> {out}")`.

## P2
- Isolate intermediate files in a gitignored temp dir (e.g. `data/.import_tmp/`).
