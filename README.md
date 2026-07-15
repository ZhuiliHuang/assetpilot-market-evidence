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

## Local checks

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

The canonical repository and GitHub Pages URLs will be recorded here after the public repository is created and validated.

