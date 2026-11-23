-- Accuracy check 1 (project.md §5.3): each level adds up to the level above, within 1%.
-- Warn only: DSWD's own totals are sometimes off (123 files known at M3) and are never fixed.
--   towns + PLGU lines → the province DSWD lists them under
--   provinces + towns listed under no province (NCR cities) → their region
--   regions → GRAND TOTAL
-- HUCs (no PSGC province) and ICCs (Santiago, Naga, Ormoc, Dagupan, Cotabato) listed under a province: DSWD counts them in the province total in
-- some reports and only in the region total in others, so both readings pass.
-- shortcut: "either" is per province / region, not per HUC; tighten if mixed cases matter.
-- Group rows (Metro Manila, Maguindanao) are sub-headers and are left out of every sum.
{{ config(severity = 'warn') }}

with p as (
    select
        pm.*,
        pm.level in ('town', 'other') and pm.dswd_parent_code is not null
        and (pm.province_code is null or s.city_class is not distinct from 'ICC') as is_huc
    from {{ ref('place_metrics') }} as pm
    left join {{ ref('psgc') }} as s on s.psgc_code = pm.psgc_code
    where pm.value is not null
),

parts as (
    select
        sha256, 'town>province' as check_name, dswd_parent_code as parent_code, metric,
        sum(value) as part_sum, sum(value) filter (where not is_huc) as alt_sum
    from p where level in ('town', 'other') and dswd_parent_code is not null group by all
    union all
    select
        sha256, 'province>region', region_code, metric,
        sum(value) filter (where not is_huc), sum(value)
    from p where level = 'province' or (level in ('town', 'other') and (dswd_parent_code is null or is_huc)) group by all
    union all
    select sha256, 'region>total', 'total', metric, sum(value), sum(value)
    from p where level = 'region' group by all
),

parents as (
    select sha256, coalesce(psgc_code, 'total') as parent_code, level, metric, sum(value) as parent_value
    from p where level in ('province', 'region', 'total') group by all
)

select parts.*, parents.parent_value
from parts
inner join parents
    on parents.sha256 = parts.sha256
    and parents.metric = parts.metric
    and parents.parent_code = parts.parent_code
    and parents.level = case parts.check_name
        when 'town>province' then 'province'
        when 'province>region' then 'region'
        else 'total' end
where abs(coalesce(parts.part_sum, 0) - parents.parent_value) > greatest(1, 0.01 * abs(parents.parent_value))
    and abs(coalesce(parts.alt_sum, 0) - parents.parent_value) > greatest(1, 0.01 * abs(parents.parent_value))
