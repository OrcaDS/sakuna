-- One row per report file × place × metric.
-- 1. When a metric shows up in two tables of the same file (2017–18 "displaced" or "combined" next to
--    the specific table), keep the specific table.
-- 2. A place listed twice in one table (e.g. Parañaque in Ulysses) is summed and flagged
--    (n_source_rows > 1). Kurt, 2026-11-23.
-- Places are keyed by PSGC code; unmatched rows (code NULL) by name, so they stay separate and listed.
with cells as (
    select
        c.*,
        r.level,
        r.region_code,
        r.province_code,
        r.psgc_code,
        r.name,
        r.match_rule,
        r.dswd_parent_code,
        case c.kind when 'displaced' then 2 when 'combined' then 3 else 1 end as kind_rank
    from {{ ref('stg_cells') }} as c
    inner join {{ ref('table_rows') }} as r using (sha256, kind, row_no)
    where c.metric is not null
),

preferred as (
    select *
    from cells
    qualify kind_rank = min(kind_rank) over (partition by sha256, metric)
)

select
    sha256,
    level,
    region_code,
    province_code,
    psgc_code,
    case when psgc_code is null then name end as unmatched_name,
    any_value(name) as name,
    any_value(match_rule) as match_rule,
    any_value(dswd_parent_code) as dswd_parent_code,
    metric,
    sum(value) as value,
    count(*) as n_source_rows,
    count(*) filter (where value is null) as n_unreadable
from preferred
group by sha256, level, region_code, province_code, psgc_code, unmatched_name, metric
