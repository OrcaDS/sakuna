-- Accuracy check 1 (project.md §5.3): each level adds up to the level above, within 1%.
-- Warn only: DSWD's own totals are sometimes off (123 files known at M3) and are never fixed.
{{ config(severity = 'warn') }}

with p as (
    select * from {{ ref('place_metrics') }}
),

parts as (
    select sha256, 'town>province' as check_name, region, province as parent, metric, sum(value) as part_sum
    from p where level = 'town' and province is not null group by all
    union all
    select sha256, 'province+ncr_town>region', region, region, metric, sum(value)
    from p where level = 'province' or (level = 'town' and province is null) group by all
    union all
    select sha256, 'region>total', null, 'GRAND TOTAL', metric, sum(value)
    from p where level = 'region' group by all
),

parents as (
    select sha256, region, name as parent, level, metric, value as parent_value from p
    where level in ('province', 'region', 'total')
)

select parts.*, parents.parent_value
from parts
inner join parents
    on parents.sha256 = parts.sha256
    and parents.metric = parts.metric
    and parents.parent = parts.parent
    and (parts.check_name = 'region>total' or parents.region = parts.region)
    and parents.level = case parts.check_name
        when 'town>province' then 'province'
        when 'region>total' then 'total'
        else 'region' end
where abs(parts.part_sum - parents.parent_value) > greatest(1, 0.01 * abs(parents.parent_value))
