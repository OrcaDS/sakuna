-- One row per event × report × place, for every report (not only the latest).
-- Levels: total, region, province, town, plus group (sub-headers like Metro Manila) and other (PLGU aid lines).
-- Names are PSA's official ones; an unmatched place keeps DSWD's spelling and a NULL psgc_code.
{%- set metrics = [
    'affected_brgys', 'affected_families', 'affected_persons',
    'inside_ec_count_cum', 'inside_ec_count_now',
    'inside_ec_families_cum', 'inside_ec_families_now',
    'inside_ec_persons_cum', 'inside_ec_persons_now',
    'outside_ec_families_cum', 'outside_ec_families_now',
    'outside_ec_persons_cum', 'outside_ec_persons_now',
    'houses_totally_damaged', 'houses_partially_damaged', 'houses_total',
    'cost_dswd', 'cost_lgu', 'cost_ngo', 'cost_other', 'cost_total',
] %}
with places as (
    select
        sha256,
        level,
        region_code,
        province_code,
        psgc_code,
        unmatched_name,
        any_value(name) as dswd_name,
        any_value(match_rule) as match_rule,
        {%- for m in metrics %}
        max(value) filter (where metric = '{{ m }}') as {{ m }},
        {%- endfor %}
        max(n_source_rows) > 1 as has_repeated_rows,
        sum(n_unreadable) as n_unreadable
    from {{ ref('place_metrics') }}
    group by sha256, level, region_code, province_code, psgc_code, unmatched_name
),

psgc as (
    select psgc_code, name from {{ ref('psgc') }}
)

select
    r.event_id,
    r.report_no,
    r.report_date,
    r.is_latest,
    p.level,
    p.psgc_code,
    p.region_code,
    reg.name as region,
    p.province_code,
    prov.name as province,
    case p.level
        when 'town' then coalesce(town.name, p.dswd_name)
        when 'province' then prov.name
        when 'region' then reg.name
        else p.dswd_name
    end as place,
    p.dswd_name,
    p.match_rule,
    {%- for m in metrics %}
    p.{{ m }},
    {%- endfor %}
    p.has_repeated_rows,
    p.n_unreadable,
    r.source_url,
    p.sha256
from places as p
inner join {{ ref('reports') }} as r on r.sha256 = p.sha256
left join psgc as reg on reg.psgc_code = p.region_code
left join psgc as prov on prov.psgc_code = p.province_code
left join psgc as town on town.psgc_code = p.psgc_code and p.level = 'town'
