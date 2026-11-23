-- One row per event × town, from the event's latest report (project.md §5.4).
-- Evacuation counts are the cumulative (CUM) columns: everyone who stayed, not who is still there.
-- Unmatched towns stay in, with a NULL psgc_code and DSWD's spelling.
select
    event_id,
    report_no,
    report_date,
    psgc_code,
    region_code,
    region,
    province_code,
    province,
    place as town,
    dswd_name,
    match_rule,
    affected_brgys,
    affected_families,
    affected_persons,
    inside_ec_count_cum as inside_ec_count,
    inside_ec_families_cum as inside_ec_families,
    inside_ec_persons_cum as inside_ec_persons,
    outside_ec_families_cum as outside_ec_families,
    outside_ec_persons_cum as outside_ec_persons,
    houses_totally_damaged,
    houses_partially_damaged,
    cost_dswd,
    cost_lgu,
    cost_ngo,
    cost_other,
    cost_total,
    has_repeated_rows,
    n_unreadable,
    source_url
from {{ ref('impacts_by_report') }}
where is_latest and level = 'town'
