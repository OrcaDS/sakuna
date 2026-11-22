-- One row per report file × place × metric.
-- 1. When a metric shows up in two tables of the same file (2017–18 "displaced" or "combined" next to
--    the specific table), keep the specific table.
-- 2. A place listed twice in one table (105 files, e.g. Parañaque in Ulysses) is summed and flagged.
--    Never resolved silently: n_source_rows > 1 marks it.
with cells as (
    select
        *,
        case kind when 'displaced' then 2 when 'combined' then 3 else 1 end as kind_rank
    from {{ ref('stg_cells') }}
    where metric is not null
),

preferred as (
    select *
    from cells
    qualify kind_rank = min(kind_rank) over (partition by sha256, metric)
)

select
    sha256,
    level,
    region,
    case level when 'province' then name else province end as province,
    case level when 'town' then name end as town,
    name,
    metric,
    sum(value) as value,
    count(*) as n_source_rows,
    count(*) filter (where value is null) as n_unreadable
from preferred
group by all
