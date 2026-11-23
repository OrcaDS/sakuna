{#- Matching key for a place name: "Sta. Cruz (capital)" and "Santa Cruz" → "santacruz",
    "City of Naga" / "Naga City" / "C ity of Naga" → "naga";
    "Lal0lo" → "lallo" (Ompong 2018 .docx turned - into 0). Province or region context tells same-named places apart. -#}
{% macro norm_place(expr) -%}
{%- set steps = [
    ('\\([^)]*\\)', ' '),
    ('\\bsta\\b\\.?', 'santa'),
    ('\\bsto\\b\\.?', 'santo'),
    ('\\bgen\\b\\.?', 'general'),
    ('\\bpres\\b\\.?', 'president'),
    ('([a-z])0([a-z])', '\\1\\2'),
    ('[^a-z0-9]', ''),
    ('^(cityof|provinceof|municipalityof)|city$', ''),
] -%}
{%- set ns = namespace(sql='lower(strip_accents(trim(' ~ expr ~ ')))') -%}
{%- for pattern, repl in steps -%}
{%- set ns.sql = "regexp_replace(" ~ ns.sql ~ ", '" ~ pattern ~ "', '" ~ repl ~ "', 'g')" -%}
{%- endfor -%}
{{ ns.sql }}
{%- endmacro %}
