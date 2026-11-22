-- One row per event × report file. is_latest picks the report gold `impacts` uses:
-- terminal first, then the latest date, then the highest number (addenda like "#17A" have no number).
select
    event_id,
    report_no,
    report_date,
    is_terminal,
    source_url,
    sha256,
    row_number() over (
        partition by event_id
        order by is_terminal desc, report_date desc nulls last, report_no desc nulls last
    ) = 1 as is_latest
from {{ ref('stg_reports') }}
