-- One row per (event, report file) that extracted to bronze. A file posted under two events keeps both rows.
with manifest as (
    select * from {{ source('lake', 'manifest') }}
    where status = 'ok'
),

extracted as (
    select sha256, status as extract_status from {{ source('lake', 'extract_log') }}
)

select
    regexp_extract(m.event_url, 'dromic\.dswd\.gov\.ph/([^/]+)', 1) as event_id,
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
where e.extract_status = 'ok'
