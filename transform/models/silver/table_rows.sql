-- One row per table row in bronze: which place it is, decided from PSGC rather than PDF bold font
-- (bold is unreliable: "City of Naga" or the town "Sampaloc" can come out as provinces).
--   region   : bronze region rows, via the region_aliases seed
--   province : the name is a PSGC province (nationwide; NIR provinces sat under Region VI/VII
--              before 2024), unless bronze says town and the current province has a town of that name
--              (Quezon, Quezon)
--   group    : sub-headers with no PSGC code (Metro Manila, Maguindanao before the 2022 split); seed
--   other    : aid lines that are not places (PLGU, Legislator); seed + "PLGU" prefix
--   town     : everything else; matched within its province, then its region, then unique nationwide.
--              A name with "City" only matches cities and is never a province (Quezon City). No match → NULL psgc_code, never guessed.
with rows as (
    select distinct sha256, kind, row_no, level as bronze_level, name
    from {{ source('lake', 'bronze') }}
),

aliases as (
    select {{ norm_place('dswd_name') }} as k, {{ norm_place('psgc_name') }} as psgc_key
    from {{ ref('place_aliases') }}
),

groups as (
    select
        {{ norm_place('g.dswd_name') }} as k,
        any_value(g.level) as level,
        -- under a group with known provinces (Maguindanao → del Norte, del Sur), those count as the province
        list(gp.province_code) filter (where gp.province_code is not null) as group_provinces
    from {{ ref('place_groups') }} as g
    left join {{ ref('group_provinces') }} as gp on gp.dswd_name = g.dswd_name
    group by 1
),

keyed as (
    select
        r.*,
        coalesce(a.psgc_key, {{ norm_place('r.name') }}) as k,
        r.name ilike '%city%' as is_city,
        case when r.name ilike 'PLGU%' then 'other' else g.level end as group_level,
        g.group_provinces,
        ra.region_code as own_region_code
    from rows as r
    left join aliases as a on a.k = {{ norm_place('r.name') }}
    left join groups as g on g.k = {{ norm_place('r.name') }}
    left join {{ ref('region_aliases') }} as ra
        on r.bronze_level = 'region'
        and ra.region_key = regexp_replace(upper(r.name), '^REGION\s+|[^A-Z]', '', 'g')
),

moves as (
    select province_code, old_region_code from {{ ref('province_moves') }}
),

current_names as (
    select *, {{ norm_place('name') }} as k from {{ ref('psgc') }}
),

psgc as (
    select * from current_names
    union all  -- old names ("Sexmoan" → Sasmuan), unless the old name is also a current name
    select * replace ({{ norm_place('old_names') }} as k) from current_names
    where old_names is not null and old_names not like '%,%'
        and {{ norm_place('old_names') }} not in (select k from current_names)
),

provinces as (
    select k, any_value(psgc_code) as psgc_code, any_value(region_code) as region_code, count(distinct psgc_code) as n
    from psgc where level = 'Prov' group by k
),

towns as (
    select distinct k, psgc_code, level, region_code, province_code
    from psgc where level in ('City', 'Mun')
),

pass1 as (
    select
        keyed.*,
        p.region_code as prov_region,
        case
            when bronze_level not in ('total', 'region') and group_level is null and not is_city and p.n = 1
                then p.psgc_code
        end as prov_candidate,
        -- row_no of the latest region row, so a province never carries over into the next region
        max(case when bronze_level in ('region', 'total') then row_no end) over w as region_row,
        last_value(own_region_code ignore nulls) over w as region_code
    from keyed
    left join provinces as p on p.k = keyed.k
    window w as (partition by sha256, kind order by row_no rows unbounded preceding)
),

pass2 as (
    select
        *,
        -- the last row that is a province by both bold font and PSGC; two province-named towns in a
        -- row (Quezon, Rizal in Nueva Ecija) must not become each other's province
        last_value(case when prov_candidate is not null and bronze_level = 'province' then {'row_no': row_no, 'code': prov_candidate} end ignore nulls)
            over (partition by sha256, kind order by row_no rows between unbounded preceding and 1 preceding) as prev_prov
    from pass1
),

classified as (
    select
        *,
        case
            when bronze_level = 'total' then 'total'
            when bronze_level = 'region' then 'region'
            when group_level is not null then group_level
            -- a town named like a province: the province lies in another region (Isabela, Negros
            -- Occidental; Rizal, Palawan), or bronze says town and the current province has a town of
            -- that name (Rizal, Nueva Ecija). Provinces that changed region match either (seed).
            when prov_candidate is not null
                and (prov_region = region_code or (prov_candidate, region_code) in (select (province_code, old_region_code) from moves))
                and not (
                    bronze_level = 'town'
                    and prev_prov.row_no > region_row
                    and exists (select 1 from towns t where t.k = pass2.k and t.province_code = prev_prov.code)
                ) then 'province'
            else 'town'
        end as level
    from pass2
),

with_context as (
    select
        *,
        -- a group (Metro Manila, Maguindanao) also ends the province before it, with no code of its own
        last_value(case when level in ('province', 'group') then {'row_no': row_no, 'code': prov_candidate, 'group_provinces': group_provinces} end ignore nulls)
            over (partition by sha256, kind order by row_no rows unbounded preceding) as cur_prov
    from classified
),

town_rows as (
    select
        sha256, kind, row_no, k, is_city, region_code,
        case when cur_prov.row_no > region_row then cur_prov.code end as province_code,
        case when cur_prov.row_no > region_row then cur_prov.group_provinces end as group_provinces
    from with_context
    where level = 'town'
),

candidates as (
    select
        tr.sha256, tr.kind, tr.row_no,
        t.psgc_code,
        t.province_code,
        case
            when t.province_code = tr.province_code or list_contains(tr.group_provinces, t.province_code) then 1
            when t.region_code = tr.region_code
                or (t.province_code, tr.region_code) in (select (province_code, old_region_code) from moves) then 2
            else 3
        end as scope
    from town_rows as tr
    inner join towns as t on t.k = tr.k and (not tr.is_city or t.level = 'City')
),

town_match as (
    -- keep the narrowest scope; it must have exactly one candidate
    select sha256, kind, row_no, psgc_code, province_code, ['province', 'region', 'nationwide'][scope] as match_rule
    from candidates
    qualify scope = min(scope) over (partition by sha256, kind, row_no)
        and count(*) over (partition by sha256, kind, row_no, scope) = 1
)

select
    c.sha256,
    c.kind,
    c.row_no,
    c.bronze_level,
    c.level,
    c.name,
    c.region_code,
    case
        when c.level = 'province' then c.prov_candidate
        when c.level in ('town', 'other') then coalesce(
            m.province_code,
            case when m.psgc_code is null and c.cur_prov.row_no > c.region_row then c.cur_prov.code end
        )
    end as province_code,
    case
        when c.level = 'region' then c.own_region_code
        when c.level = 'province' then c.prov_candidate
        when c.level = 'town' then m.psgc_code
    end as psgc_code,
    case when c.level = 'town' then coalesce(m.match_rule, 'unmatched') end as match_rule,
    -- the province DSWD lists the row under; differs from PSGC for HUCs (Cagayan de Oro under
    -- Misamis Oriental) and is what the report's own totals add up by
    case when c.level in ('town', 'other') and c.cur_prov.row_no > c.region_row then c.cur_prov.code end
        as dswd_parent_code
from with_context as c
left join town_match as m using (sha256, kind, row_no)
