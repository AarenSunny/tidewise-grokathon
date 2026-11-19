# Build probes

Live HTTP probes for every Part A source in `DATA_SOURCES.md`.

```bash
# from repo root, with venv
make probe
# or
.venv/bin/python scripts/probes/run_all.py
```

- `REPORT.md` — committed summary of shapes + discrepancies (re-run to refresh).
- `out/` — gitignored per-batch JSON dumps.
- Research-owned scripts stay in `scripts/research_probes/` (do not edit from build).
