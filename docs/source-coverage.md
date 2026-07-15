# Source coverage

Audit date: 2026-07-15

The registry locks exactly one first-level public proxy per AssetPilot direction. Official publishers establish identity and methodology; separate public adapters are probed for historical observations. A configured source is not treated as healthy until its runtime probe succeeds. The latest local acceptance probe used only public identifiers and produced data for all fifteen directions; it did not publish the temporary package.

| Category | Direction | Locked proxy | Official publisher | Implemented public history | Latest local acceptance state |
| --- | --- | --- | --- | --- | --- |
| broad/style | 沪深300 | 000300 | China Securities Index | Eastmoney → Sina | ready; cross-check confirmed |
| broad/style | 中证500 | 000905 | China Securities Index | Eastmoney → Sina | ready; cross-check confirmed |
| broad/style | 中证1000 | 000852 | China Securities Index | Eastmoney → Sina | ready; cross-check confirmed |
| broad/style | 创业板 | 399006 | Shenzhen Securities Information | Eastmoney → Sina | ready; cross-check confirmed |
| broad/style | 科创50 | 000688 | Shanghai Stock Exchange / China Securities Index | Eastmoney → Sina | ready; cross-check confirmed |
| broad/style | 红利 | 000922 | China Securities Index | Eastmoney → Sina | ready; second exact-code source unavailable |
| industry | 信息科技 | 000993 | China Securities Index | Eastmoney → Sina | ready; cross-check confirmed |
| industry | 军工 | 399967 | China Securities Index | Eastmoney → Sina | ready; cross-check confirmed |
| industry | 医疗 | 000991 | China Securities Index | Eastmoney → Sina | ready; cross-check confirmed |
| industry | 消费 | 000990 | China Securities Index | Eastmoney → Sina | ready; second exact-code source unavailable |
| industry | 金融 | 932075 | China Securities Index | Eastmoney → Sina | data available; history below percentile threshold |
| industry | 周期资源 | 000961 | China Securities Index | Eastmoney → Sina | ready; second exact-code source unavailable |
| Hong Kong | 恒生指数 | HSI | Hang Seng Indexes | Eastmoney → Stooq | ready; second source unavailable during probe |
| Hong Kong | 恒生科技 | HSTECH | Hang Seng Indexes | Eastmoney | ready; exact-code fallback pending |
| Hong Kong | 港股红利 | HSHDYI | Hang Seng Indexes | Eastmoney | ready; exact-code fallback pending |

## Coverage rules

- Official pages and factsheets are identity evidence, not a license to republish raw files.
- Runtime packages record the approved source identity/homepage, observation date, attempt time, cross-validation result, sample count, and failure/degradation class. Request URLs are reconstructed only from locked public codes and bounded fields; raw responses are not retained.
- A direction becomes `ready` only after at least one permitted history source returns a valid series and the official proxy identity matches.
- Cross-validation is `confirmed` only when independent upstream providers agree within the configured tolerance. Two adapters backed by the same upstream do not count as independent.
- If valuation history is unavailable, the package may publish a clearly labelled price-percentile curve. It must never relabel price percentile as valuation percentile.
- If no permitted history source succeeds, the direction remains visible with a structured missing-data explanation. It must not receive a synthetic curve.
- Local Wind may verify an identifier or conflict, but its response, credentials, and raw values never enter this public repository.

Exact source definitions, timeouts, retry limits, and official URLs live in [`config/sources.json`](../config/sources.json).
