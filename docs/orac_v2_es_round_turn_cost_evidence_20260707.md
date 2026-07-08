# ORAC v2 ES Round-Turn Cost Evidence Refresh

Evidence date: 2026-07-07

Scope: ES only, round-turn commission, exchange fee recovery, clearing fee, and regulatory fee components only. This packet does not approve ORAC v2 discovery execution, WFA/modeling, Phase 8, tuning, promotion, artifact freeze, paper, live trading, provider downloads, or cost-config mutation.

## Status

Evidence refresh status: `REFRESHED_VALUES_MATCH_CURRENT_ES_DOLLAR_COMPONENTS`.

`configs/costs.yaml` was not changed. Its ES dollar component values are supported by the primary-source refresh, but its stored effective date remains `2026-06-14`; the current CME fee schedule page points to a later CME schedule effective `2026-06-29`. Treat this packet as supplemental dated evidence unless a later explicit cost-config metadata update is approved.

## Primary Sources Checked

- IBKR futures commissions page: https://www.interactivebrokers.com/en/pricing/commissions-futures.php
- IBKR CME electronic Globex exchange/regulatory fee recovery page: https://www.interactivebrokers.com/en/accounts/fees/CME.php
- CME clearing and trading fees page: https://www.cmegroup.com/company/clearing-fees.html
- CME fee schedule PDF linked from the clearing and trading fees page: https://www.cmegroup.com/company/files/cme-fee-schedule-2026-06-29.pdf

## ES Component Evidence

The IBKR futures commissions page shows USD-denominated futures commission tiers with the first tier and fixed rate at `0.85` USD per contract. The same page gives an ES example with these per-side components:

| Component | Refreshed value | Source |
| --- | ---: | --- |
| IBKR execution commission | 0.85 USD per contract per side | IBKR futures commissions ES example |
| Exchange fee recovery | 1.38 USD per contract per side | IBKR futures commissions ES example and IBKR CME fee recovery page |
| Clearing fee | 0.00 USD per contract per side | IBKR futures commissions ES example |
| Regulatory fee | 0.02 USD per contract per side | IBKR futures commissions ES example and IBKR CME fee recovery page |

The IBKR CME fee recovery page lists `ES` under E-mini S&P equity futures at `1.38` USD and lists the regulatory fee recovery charge for all products at `0.02` USD. IBKR notes that its fee recovery charges are client charges intended to cover execution costs and may differ from exact exchange charges.

The CME clearing and trading fees page links the current CME schedule. The current CME equity product PDF page visually cross-checks non-member E-mini equity futures `Globex - Outrights` at `1.38` USD per side as of the June 29, 2026 schedule. This supports the ES exchange fee recovery component used by the current config.

## Reconciliation To `configs/costs.yaml`

Current ES config values:

| Config field | Current value | Refreshed evidence status |
| --- | ---: | --- |
| `commission_per_contract_dollars` | 0.85 | Supported |
| `exchange_fee_recovery_dollars` | 1.38 | Supported |
| `clearing_fee_dollars` | 0.00 | Supported |
| `regulatory_fee_dollars` | 0.02 | Supported |
| `fees_per_side_dollars` | 1.40 | Supported as exchange plus regulatory fee recovery |
| `round_turn_cost_dollars` | 29.50 | Supported when current internal slippage assumption is included |
| `round_turn_cost_ticks` | 2.36 | Supported when current internal slippage assumption is included |

Fee-only math:

```text
per-side fee-only dollars = 0.85 + 1.38 + 0.00 + 0.02 = 2.25
round-turn fee-only dollars = 2 * 2.25 = 4.50
```

Configured slippage math:

```text
slippage dollars = 2 sides * 1.0 tick per side * 12.50 dollars per tick = 25.00
configured round-turn dollars = 4.50 + 25.00 = 29.50
configured round-turn ticks = 29.50 / 12.50 = 2.36
```

The slippage component is an internal research assumption already labeled in `configs/costs.yaml` as `approved_internal_model_assumption_2026-06-14`; it is not primary-source commission, exchange, clearing, or regulatory fee evidence.

## Stop Condition Before Discovery

Do not run ORAC v2 `discovery-run` from this packet alone. A separate explicit bounded discovery-run approval must first cite this packet, the existing ORAC v2 alpha-discovery config, the still-absent expected discovery outputs, and the decision to proceed with unchanged cost values despite the config metadata effective-date caveat or to perform a separate approved cost-config metadata update first.
