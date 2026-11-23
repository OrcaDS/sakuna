-- Privacy guard: an unmatched row whose name carries an official's title (Cong., Hon., Mayor...) may hold a
-- person's name. Real towns with a title (Governor Generoso) match PSGC and are not checked.
select sha256, kind, row_no, level, name
from {{ ref('table_rows') }}
where psgc_code is null
    and regexp_matches(name, '\b(?i:cong|congressman|congresswoman|rep|hon|mayor|gov|governor|sen|senator|atty|engr|dr|mr|mrs|ms|vice)\b')
