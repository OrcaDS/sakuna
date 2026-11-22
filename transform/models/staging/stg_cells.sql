-- One row per non-empty bronze cell, typed, with the gold metric it feeds.
-- Which place a row is (level, PSGC code) is decided in silver `table_rows`.
with keyed as (
    select
        sha256,
        kind,
        row_no,
        "column" as header,
        trim(value) as raw_value,
        regexp_replace(upper("column"), '[^A-Z]', '', 'g') as p,
        -- measure words live after the table title; Henry 2022's title holds "Families Persons CUM NOW"
        regexp_replace(upper(coalesce(nullif(regexp_extract("column", ' > (.*)$', 1), ''), '')), '[^A-Z]', '', 'g') as tail
    from {{ source('lake', 'bronze') }}
    where trim(value) <> ''
),

mapped as (
    select
        *,
        case
            when p similar to '.*(RETURNEDHOME|TOTALSERVED|TOTALDISPLACED|SEXAGE|POPULATION).*' then null
            when p similar to '.*(EVACUATIONCENTERS|NOOFECS|ACTIVEECS).*' then 'inside_ec_count'
            when p like '%INSIDE%' and tail like '%FAMIL%' then 'inside_ec_families'
            when p like '%INSIDE%' and tail like '%PERSON%' then 'inside_ec_persons'
            when p like '%OUTSIDE%' and tail like '%FAMIL%' then 'outside_ec_families'
            when p like '%OUTSIDE%' and tail like '%PERSON%' then 'outside_ec_persons'
            when p like '%AFFECTED%' and tail like '%FAMIL%' then 'affected_families'
            when p like '%AFFECTED%' and tail like '%PERSON%' then 'affected_persons'
            when p like '%AFFECTED%' and tail like '%BARANGAY%' then 'affected_brgys'
            when p like '%DAMAGEDHOUSES%' and tail like '%TOTALLY%' then 'houses_totally_damaged'
            when p like '%DAMAGEDHOUSES%' and tail like '%PARTIAL%' then 'houses_partially_damaged'
            when p like '%DAMAGEDHOUSES%' and tail like '%TOTAL%' then 'houses_total'
            when p like '%COSTOFASSISTANCE%' and tail like '%DSWD%' then 'cost_dswd'
            when p like '%COSTOFASSISTANCE%' and tail like '%LGU%' then 'cost_lgu'
            when p like '%COSTOFASSISTANCE%' and tail like '%NGO%' then 'cost_ngo'
            when p like '%COSTOFASSISTANCE%' and tail similar to '.*(OTHERS|THERS|OTHES).*' then 'cost_other'
            when p like '%COSTOFASSISTANCE%' and tail similar to '.*(GRAND|RANDTOTAL|TOTA).*' then 'cost_total'
        end as base_metric
    from keyed
)

select
    sha256,
    kind,
    row_no,
    header,
    raw_value,
    case
        when base_metric like 'inside_ec%' or base_metric like 'outside_ec%' then
            base_metric || case
                when tail like '%NOW' or p like '%CURRENTLY%' then '_now'
                else '_cum'  -- 2017 tables with no CUM/NOW split are cumulative
            end
        else base_metric
    end as metric,
    -- Clean numbers only: "1,017" / "1017" / "1,017.50" (a trailing * is a footnote mark); "-" is 0.
    -- Anything else (typos like "28,12") becomes NULL and is counted in n_unreadable.
    case
        when raw_value = '-' then 0
        when regexp_full_match(raw_value, '(\d{1,3}(,\d{3})*|\d+)(\.\d+)?\*?')
            then cast(replace(replace(raw_value, ',', ''), '*', '') as decimal(18, 2))
    end as value
from mapped
