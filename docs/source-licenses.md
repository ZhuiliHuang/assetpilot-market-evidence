# Redistribution and source-use policy

Audit date: 2026-07-15

This repository uses a conservative four-state policy. The policy describes what this project may publish; it does not claim ownership of any upstream market data.

| Policy | Allowed use |
| --- | --- |
| `publish_raw` | Raw observations may be published only when the upstream terms explicitly permit redistribution. No current production source receives this status by default. |
| `publish_derived_only` | Fetch in memory, calculate deterministic ranks or quality metadata, discard raw responses, and publish only the derived output plus attribution. |
| `link_only` | Use the page to verify name, code, methodology, or date. Store only the URL and small factual metadata; do not copy the file or time series. |
| `blocked` | Do not fetch in scheduled production runs and do not use the source in a fallback chain. |

## Current decisions

- China Securities Index, Shenzhen Stock Exchange, and Hang Seng Indexes official pages are `link_only`. Their factsheets and methodologies establish proxy identity and document the metric, but the repository does not mirror those files.
- AKShare is an open-source adapter, not the owner of every underlying dataset. Its adapters are therefore `publish_derived_only`; each run must retain the actual upstream provider in provenance.
- Eastmoney, Sina Finance, and Stooq public endpoints are `publish_derived_only`. Raw responses and raw close/valuation tables are not committed, served through Pages, or placed in Actions artifacts.
- Wind is deliberately absent from the cloud source registry. It remains a local, optional verification tier only.
- If an upstream term, endpoint, or redistribution boundary becomes unclear, the source is changed to `blocked` before the next scheduled publication.

## Derived output limits

Permitted derived output is intentionally narrow:

- daily or lower-frequency percentile ranks;
- sample counts, date ranges, gaps, and quality flags;
- source identity, source date, attempted fallback order, and conflict state;
- deterministic hashes and calculation versions.

The evidence package does not publish raw price, raw PE/PB, raw constituents, full upstream payloads, cookies, request headers, credentials, or account-bound downloads. Percentile points are rounded and remain traceable to a calculation definition without enabling reconstruction of the full upstream table.

## Review triggers

Re-audit a source before use when its terms URL changes, the adapter changes upstream provider, login becomes required, robots or rate-limit behaviour changes, a response starts including personalized fields, or a publisher asks that derived redistribution stop. A failed review degrades the affected direction and leaves the previous valid package in place.
