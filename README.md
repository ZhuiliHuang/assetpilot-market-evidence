# AssetPilot Market Evidence

This public repository builds deterministic, versioned market-evidence packages for AssetPilot's lightweight display layer.

## Boundaries

- Public market identifiers, source metadata, reproducible calculations, and validated public conclusions only.
- No local AssetPilot database, holdings, transactions, accounts, costs, quantities, screenshots, OCR text, insurance material, or private logs.
- Numeric curves and historical percentiles are calculated by deterministic programs, never invented by a language model.
- ChatGPT scheduled reviews are read-only. A candidate can enter the untrusted branch only through a separately approved writer; ChatGPT's official GitHub app cannot push repository changes.
- Wind remains an optional local cross-check; Wind data and credentials are never committed here.

## Repository lanes

- `main`: trusted code, schemas, tests, and workflows.
- `data`: validated, Actions-managed public packages.
- `chatgpt-inbox`: untrusted analysis candidates only; created after the trusted validator exists.

The workday numeric collection schedule is enabled for `20:30 Asia/Shanghai`. A `22:00 Asia/Shanghai` ChatGPT task was acceptance-tested on 2026-07-17 and correctly read the repository, but its attempted write failed with HTTP 403 because the official ChatGPT GitHub app is read-only. The task must therefore remain a read-only review until a separate supported writer is explicitly approved.

## Intended public endpoints

- Repository: `https://github.com/ZhuiliHuang/assetpilot-market-evidence`
- GitHub Pages: `https://zhuilihuang.github.io/assetpilot-market-evidence/`

These endpoints are live. The accepted public version contains all fifteen directions, compact metric/source/cross-validation provenance, and no degraded direction.

The ChatGPT scheduled task must use the read-only prompt in [`docs/chatgpt-scheduled-task-prompt.md`](docs/chatgpt-scheduled-task-prompt.md). Manual valid-candidate and intentional invalid-candidate drills proved the trusted publication lane, but those drills do not imply that the ChatGPT GitHub app can write. Numeric refresh now retains a hash-verified prior analysis as a stale fallback; AssetPilot labels that fallback as review-only and never lets it raise actionability.

## Local checks

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

Build a real public-only package into a disposable directory with:

```powershell
python scripts/update_market_data.py --output <temporary-directory>
```

The live path sends only the fifteen locked public index or explicitly documented ETF proxy identifiers and bounded date/field parameters to approved public hosts. It never reads AssetPilot, Wind credentials, or private files. Keep `publish=false` until the generated tree, source conflicts, missing cross-checks, and failure-retention behavior have been inspected.
