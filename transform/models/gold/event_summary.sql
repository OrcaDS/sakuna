-- One row per event: national totals summed from `impacts` (towns of the latest report),
-- next to DSWD's own GRAND TOTAL from the same report, so gaps are visible. Never adjusted.
{%- set metrics = [
    'affected_families', 'affected_persons',
    'inside_ec_families', 'inside_ec_persons', 'outside_ec_families', 'outside_ec_persons',
    'houses_totally_damaged', 'houses_partially_damaged', 'cost_total',
] %}
with towns as (
    select
        event_id,
        count(*) as n_towns,
        count(*) filter (where psgc_code is null) as n_unmatched_towns,
        {%- for m in metrics %}
        sum({{ m }}) as {{ m }},
        {%- endfor %}
        any_value(source_url) as source_url
    from {{ ref('impacts') }}
    group by event_id
),

dswd as (
    select
        event_id,
        {%- for m in metrics %}
        {%- set col = m ~ '_cum' if m.startswith('inside_ec') or m.startswith('outside_ec') else m %}
        sum({{ col }}) as dswd_{{ m }}{{ ',' if not loop.last }}
        {%- endfor %}
    from {{ ref('impacts_by_report') }}
    where is_latest and level = 'total'
    group by event_id
)

select
    e.event_id,
    e.event_title,
    e.local_name,
    e.event_type,
    e.event_year,
    e.start_date,
    t.n_towns,
    t.n_unmatched_towns,
    {%- for m in metrics %}
    t.{{ m }},
    {%- endfor %}
    {%- for m in metrics %}
    d.dswd_{{ m }},
    {%- endfor %}
    t.source_url
from {{ ref('events') }} as e
inner join towns as t on t.event_id = e.event_id
left join dswd as d on d.event_id = e.event_id
