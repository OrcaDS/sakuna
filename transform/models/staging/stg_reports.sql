-- One row per (event, report file) that extracted to bronze. A file posted under two events keeps both rows.
with manifest as (
    select * from {{ source('lake', 'manifest') }}
    where status = 'ok'
),

extracted as (
    select sha256, status as extract_status from {{ source('lake', 'extract_log') }}
)

select
    coalesce(em.event_id, regexp_extract(m.event_url, 'dromic\.dswd\.gov\.ph/([^/]+)', 1)) as event_id,
    m.event_title,
    cast(m.event_year as integer) as event_year,
    m.sha256,
    m.file_url as source_url,
    m.label,
    m.report_no = 'terminal' as is_terminal,
    try_cast(m.report_no as integer) as report_no,
    try_cast(m.report_date as date) as report_date,
    e.extract_status
from manifest as m
inner join extracted as e on e.sha256 = m.sha256
-- one event split over two posts (seed event_merges): report under the main post
left join {{ ref('event_merges') }} as em
    on em.old_event_id = regexp_extract(m.event_url, 'dromic\.dswd\.gov\.ph/([^/]+)', 1)
where e.extract_status = 'ok'
    -- "Effects of Southwest Monsoon in Mindanao [22 Jul 2026][MERGED TC Kiyapo]" holds only Kiyapo's
    -- Report 1; DSWD merged the event, so the file counts under Kiyapo alone (Kurt, 2026-11-23)
    and m.event_title not like '%[MERGED%'
