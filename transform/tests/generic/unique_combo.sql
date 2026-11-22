{% test unique_combo(model, columns) %}
-- Rows whose column combination is not unique (NULLs compare equal). No package needed.
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by all
having count(*) > 1
{% endtest %}
