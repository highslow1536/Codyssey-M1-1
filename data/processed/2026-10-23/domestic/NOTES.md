> 공개판 안내: 작성 당시 연구 기록입니다. 원가격·주가·벤치마크 원본과 복원 가능한 파일은 제외했습니다. 현재 공개 범위·실행법은 루트 README와 데이터 이용 안내를 따릅니다.

# domestic history export (2026-10-23) - schema note

Derivative of the frozen snapshot data/feasibility/2026-10-21 for dashboard use.
Raw responses are read-only; this folder holds only history.json (this note excepted).
Built by scripts/prepare_domestic_history.py, verified by tests/test_domestic_history.py.
Standard library only. Existing analysis/dashboard/scripts/export_dashboard_data.py untouched.

## top level

- schema: domestic_history/1
- snapshot / snapshot_date_kst: source snapshot and its KST date (2026-10-21)
- generated_date_kst: export run date (KST); excluded from reproducibility compare
- currency: KRW
- price_semantics: historical_field=minPrice, price_basis=source_label_lowest_price_trend,
  shipping/cash_card/coupon basis=unknown, aggregation_basis=unconfirmed, weekly_aggregation=unknown
- counts: products=8, weekly 12 per product / 96 total, monthly mobile 185 / desktop 179,
  plus 24m-window comparison counters (matched / value_mismatch / mobile_only / desktop_only)
- audit_consistency.cited: audit all-window totals (13 value mismatches, 6 mobile-only,
  0 desktop-only, 9 PC-internal, 0 mobile-internal) with a scope note; export comparison is 24m-scoped
- cautions: partial month, label authority, no-representative-claim, no appended row,
  no outlier removal, unresolved boundary months
- sources: 48 raw files with sha256 and row counts (40 mobile + 8 desktop)
- products: 8 entries in products.csv order

## per product

- product_code, category, name, product_url (from products.csv, verbatim)
- currency / historical_field / price_basis / shipping_basis / cash_card_basis /
  coupon_basis / aggregation_basis / weekly_aggregation (same unconfirmed/unknown semantics)
- weekly_3m: 12 rows, file order. Each row keeps label_mobile (MM-DD), label_desktop (MM-DD),
  desktop_fulldate (YY-MM-DD), mobile_price, desktop_price, match. Display aid iso_date is the
  desktop Fulldate with 20-prefix; iso_year_inferred=true because the mobile MM-DD side carries
  no year and the year comes from snapshot context (2026-10). Labels are never renamed.
- monthly_mobile_24m / monthly_desktop_24m: separate arrays, file order, verbatim label (YY-MM)
  and minPrice. No merging, no outlier removal.
- monthly_comparison_24m: union of 24m month labels (mobile order, then desktop-only).
  status is matched | value_mismatch | mobile_only | desktop_only; both prices kept side by side,
  null on the absent side. month_iso (20-prefix) is a display string; month_label stays
  authoritative. partial_month=true only for 26-10 (incomplete current month).

## rules enforced by tests

- weekly arrays equal raw 3m rows on both surfaces (96 rows, all match)
- monthly arrays equal raw 24m rows in order (mobile 185, desktop 179)
- comparison covers the exact union: no duplicates, no dropped months (24m: 6 mobile-only,
  0 desktop-only); spot labels 24-11 mobile-only and 24-12 value_mismatch preserved
- 26-10 flagged partial everywhere; no appended current-price row
- no W-FRI renaming; no verified-minimum / representative-market-price claim keys
- RTX 4060 2025-11 spike values kept as returned
- ISO rules: month stays a month string; weekly YY-MM-DD only by 20-prefix, MM-DD year flagged
- 48 source sha256 recomputed from raw; build_history() output equals history.json
