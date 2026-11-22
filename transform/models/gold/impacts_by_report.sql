-- One row per event × report × place (grand total, region, province and town rows).
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
        region,
        province,
        town,
        name,
        {%- for m in metrics %}
        max(value) filter (where metric = '{{ m }}') as {{ m }},
        {%- endfor %}
        max(n_source_rows) > 1 as has_repeated_rows,
        sum(n_unreadable) as n_unreadable
    from {{ ref('place_metrics') }}
    group by all
)

select
    r.event_id,
    r.report_no,
    r.report_date,
    r.is_latest,
    p.*,
    r.source_url
from places as p
inner join {{ ref('reports') }} as r on r.sha256 = p.sha256
