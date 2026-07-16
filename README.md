# AssetPilot Market Evidence

This public repository builds deterministic, versioned market-evidence packages for AssetPilot's lightweight display layer.

## Boundaries

- Public market identifiers, source metadata, reproducible calculations, and validated public conclusions only.
- No local AssetPilot database, holdings, transactions, accounts, costs, quantities, screenshots, OCR text, insurance material, or private logs.
- Numeric curves and historical percentiles are calculated by deterministic programs, never invented by a language model.
- ChatGPT candidates will use a separate untrusted branch and cannot directly change trusted code or official published packages.
- Wind remains an optional local cross-check; Wind data and credentials are never committed here.

## Repository lanes

- `main`: trusted code, schemas, tests, and workflows.
- `data`: validated, Actions-managed public packages.
- `chatgpt-inbox`: untrusted analysis candidates only; created after the trusted validator exists.

Scheduled collection and ChatGPT review remain disabled until end-to-end acceptance is complete.

## Intended public endpoints

- Repository: `https://github.com/ZhuiliHuang/assetpilot-market-evidence`
- GitHub Pages: `https://zhuilihuang.github.io/assetpilot-market-evidence/`

These endpoints are recorded for client allow-listing but are not considered live until the repository is created, a manual live public-data publication is inspected on GitHub Pages, and the end-to-end checklist in [`docs/operations-runbook.md`](docs/operations-runbook.md) passes.

The ChatGPT scheduled task must use the exact reusable prompt in [`docs/chatgpt-scheduled-task-prompt.md`](docs/chatgpt-scheduled-task-prompt.md). Keep the task paused until its first manual candidate is accepted and published without changing the last valid package on a failure drill.

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
