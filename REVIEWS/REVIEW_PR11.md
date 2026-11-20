# REVIEW_PR11: CDPH fail-open fix (REVIEW_3 P3-1)

**Reviewed: post-merge main `fb9f0fd`** (PR #11 head was `b130be7`, merged as `fb9f0fd`). Files: `backend/adapters/cdph.py`, `tests/test_cdph_failopen.py`.
Tests on `fb9f0fd`: **151 passed, 1 skipped**. I also ran my own probes through `adapter.fetch` with a stubbed `_fetch_live`.

## Verdict: P3-1 is CLOSED at the adapter level (yes)
| Probe | status | any_region_advisory | cannot_confirm | observed_at |
|---|---|---|---|---|
| HTTP 200 + `error` body (both or one layer) | down | None | True | None |
| empty layers / no `features` key | down | None | True | None |
| county pins only (the live shape) | down | None | True | None |
| visible=0, or advisory for another county | down | None | True | None |
| layer with only `lastEditDate`, no features | down | None | True | data time |
| fresh dated visible region advisory | ok | True | False | advisory DATE |
| 2025 dated visible advisory | down (too old) | True | False | 2025-07-10 |

- `any_region_advisory` is `None` unless the parse succeeds, and **it is never `False`** (`cdph.py:~65`, `_unconfirmed` and `_validate`). The adapter can only say "advisory present" or "unknown", never "clear". That is the safe choice.
- `observed_at` comes from the layer `editingInfo.lastEditDate` or the advisory `DATE`. The fetch clock is no longer attached (`_fetch_live` returns the raw bodies only).
- `_apply_freshness` forces `down` when `cannot_confirm` is set or `observed_at` is missing. This fixes the base-class gap where a missing `observed_at` stayed `ok` (REVIEW_3 P3-2, CDPH only).
- The shellfish gate cannot go eligible through this adapter: the only `ok` result is `any=True`. Every other path is `down`, and the scorer's `source_problem` turns a `down` source into `cannot_confirm`.

## Residual risks (not blockers for this PR)
1. **PR3-5 is still open at the glue.** No code maps `ShellfishPayload` into `HourlyFeatures.active_alerts`; nothing outside the adapter and scorer references `any_region_advisory`. The scorer decides "active" by substring match on alert text (`predicates.py:116`, `base.py:226`). If the glue forwards `any=True, status=ok` as an alert string without a word like "shellfish" or "biotoxin" (the config patterns), the gate reads "inactive" and **passes**. When the glue is written, it must emit a pattern-matching string such as `"shellfish advisory active"` for `any=True`, and treat any other state as unknown.
2. Because the adapter never returns "clear", the shellfish gate can never be positively confirmed for clamming or crabbing. That is correct until a source with per-county status and a date exists (REVIEW_2 N1), but `/recommend` will show those activities as `cannot_confirm`.
3. A visible dated advisory is matched to the region by county names in its title or description. A closure worded without those names (for example "Sonoma coast") would be `cannot_confirm`, which is safe.
4. `/recommend` still returns `windows=[]` (`orchestrator.py:169`); the scorer wiring is separate.
