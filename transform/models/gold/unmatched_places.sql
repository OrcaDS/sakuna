-- One row per town spelling in `impacts` that found no PSGC code (project.md §5: listed, never guessed).
-- To fix one, add the spelling to seed `place_aliases`, not here.
select
    region_code,
    region,
    province_code,
    province,
    dswd_name,
    count(*) as n_events,
    min(event_id) as example_event_id,
    min(source_url) as example_source_url
from {{ ref('impacts') }}
where psgc_code is null
group by all
order by region_code, province_code, dswd_name
