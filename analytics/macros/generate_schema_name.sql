{# Use custom schema names verbatim (staging, marts) instead of dbt's
   default "<target>_<custom>" prefixing, so grants can target marts. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
