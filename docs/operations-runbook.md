# Operations runbook

## Safety invariants

- This repository contains public market identifiers, public-source metadata, deterministic derivatives, and validated public conclusions only.
- Never add AssetPilot databases, holdings, accounts, quantities, costs, transactions, totals, screenshots, OCR text, local files, private logs, Wind credentials, or Wind raw data.
- `main` owns trusted code and validation. `data` owns Actions-published packages. `chatgpt-inbox` is untrusted and may add only one `ai-inbox/YYYY-MM-DD.json` candidate per commit.
- A failed numeric refresh or AI candidate must leave the last valid official package unchanged.

## Before remote publication

1. Confirm `git status --short` is clean and inspect the complete tracked-file list.
2. Run `python -m pytest -q`.
3. Run `python scripts/audit_source_coverage.py --offline`.
4. Build fixture evidence into a new temporary directory with `python scripts/update_market_data.py --fixtures --output <temporary-directory>`.
5. Build live public evidence into a separate temporary directory with `python scripts/update_market_data.py --output <temporary-directory>`.
6. Inspect both manifests, category packages, direction details, hashes, source URLs, cross-validation states, gaps, file counts, and total sizes. Delete only those verified temporary directories after acceptance.
7. Create a public repository named `assetpilot-market-evidence` under `ZhuiliHuang`, then push the existing `main`, `data`, and `chatgpt-inbox` branches.
8. Keep both schedules disabled. Manually run live publication, verify Pages, and verify the fixed Pages origin is the only remote origin used by AssetPilot.

## Numeric publication gate

Enable the weekday numeric schedule only after one manually dispatched public-data run passes all of these checks:

- all fifteen first-level directions are represented;
- source coverage and redistribution status pass the allow-list audit;
- every published package validates and every manifest hash matches;
- partial-source failure is labeled and retains usable prior evidence;
- complete failure does not replace the last valid official version;
- Pages serves the exact validated `public` tree;
- AssetPilot can load the package using an isolated temporary SQLite database.

The intended weekday schedule is `20:30 Asia/Shanghai`. GitHub cron uses UTC, so account for seasonal assumptions explicitly and document the chosen expression before enabling it.

## ChatGPT publication gate

1. Grant the ChatGPT GitHub app access only to this public repository, not the private AssetPilot repository.
2. Create a paused workday task for `22:00 Asia/Shanghai`, with no project files and medium reasoning on a supported non-Pro model.
3. Use [`chatgpt-scheduled-task-prompt.md`](chatgpt-scheduled-task-prompt.md) verbatim.
4. Run it manually once. Confirm it changes exactly one dated file on `chatgpt-inbox`.
5. Confirm the candidate binds to the current evidence version and manifest hash, every reference resolves, the trusted validator publishes to `data`, Pages updates, and AssetPilot shows separate evidence and analysis dates.
6. Commit one intentionally invalid simulated candidate and confirm validation fails while the prior official analysis remains available.
7. Enable the task only after both the success path and failure-retention drill pass.

## Failure response

- Do not delete or overwrite the last valid package.
- Record the failed source or candidate, its attempted time, the retained data date, and the decision impact.
- Prefer another approved public source only when its license and schema mapping are already registered.
- Never repair a cloud failure by adding Wind data, secrets, personal context, or unreviewed files.

## Acceptance record

Accepted on 2026-07-16:

- Live numeric workflow `29477180354` completed build, publication, and Pages deployment. Evidence version `2026-07-16.0bdcb9092724` contains fifteen ready directions, compact provenance on every category card, zero degraded directions, and zero forbidden-field matches.
- Valid candidate receiver `29491407664` and trusted publisher `29491416728` completed successfully. The official analysis contains two focus directions and one risk direction, bound to the exact public manifest.
- Intentional trading-language candidate publisher `29491639810` failed with the expected validation error; the preceding official analysis hash remained unchanged.
- The candidate branch was restored to a valid candidate and trusted publisher `29491744826` completed successfully.
- The workday numeric cron is enabled at the UTC expression corresponding to `20:30 Asia/Shanghai`. The workday `22:00 Asia/Shanghai` ChatGPT task is the only remaining external setup item.
