-- One row per event (DROMIC post). Name, type and start date are read from the post title,
-- e.g. 'Tropical Storm “BASYANG” (I.N. SANBA) [12 Feb 2018]'; NULL when the title does not say.
with titles as (
    select
        event_id,
        any_value(event_title) as event_title,
        any_value(event_year) as event_year,
        count(*) as n_reports,
        max(report_date) as last_report_date,
        bool_or(is_terminal) as has_terminal_report
    from {{ ref('stg_reports') }}
    group by event_id
),

parsed as (
    select
        *,
        trim(regexp_replace(event_title, '\s*\[(terminated|termin)[^\]]*\]?\s*$', '', 'i')) as title,
        lower(event_title) as t,
        -- the first quoted name, else the word after the storm type ("TD (TD) Ester");
        -- combined events keep only their first name
        coalesce(
            nullif(regexp_extract(event_title, '[“"]([A-Za-z]+)', 1), ''),
            nullif(regexp_extract(
                event_title,
                '(?:Typhoon|Storm|Depression|Cyclones?|STY|STS|TS|TD|TCs?)\s*(?:\([A-Z]+\)\s*)?([A-Z][A-Za-z]+)', 1
            ), '')
        ) as raw_local,
        coalesce(
            -- title date ("20 Sept 2019", "30 Nov. 2019"), else the one in the post's slug
            try_strptime(replace(replace(
                regexp_extract(event_title, '\[(\d{1,2} [A-Za-z.]+ \d{4})\]', 1), 'Sept ', 'Sep '), '.', ''
            ), ['%d %b %Y', '%d %B %Y']),
            try_strptime(replace(
                regexp_extract(event_id, '(\d{1,2}-[a-z]+-\d{4})', 1), 'sept-', 'sep-'
            ), ['%d-%b-%Y', '%d-%B-%Y'])
        )::date as start_date,
        nullif(regexp_extract(event_title, 'I\.\s?N\.?\s+([A-Za-z]+)', 1), '') as raw_intl
    from titles
)

select
    event_id,
    title as event_title,
    upper(left(raw_local, 1)) || lower(raw_local[2:]) as local_name,
    upper(left(raw_intl, 1)) || lower(raw_intl[2:]) as international_name,
    case
        when t like '%super typhoon%' then 'super typhoon'
        when t like '%typhoon%' then 'typhoon'
        when t like '%severe tropical storm%' then 'severe tropical storm'
        when t like '%tropical storm%' then 'tropical storm'
        when t like '%tropical depression%' then 'tropical depression'
        when t like '%tropical cyclone%' then 'tropical cyclone'
        when t like '%monsoon%' or t like '%habagat%' then 'monsoon'
        else 'other'
    end as event_type,
    t like '%monsoon%' or t like '%habagat%' as with_monsoon,
    event_year,
    start_date,
    n_reports,
    last_report_date,
    has_terminal_report or t like '%terminat%' as is_terminated
from parsed
