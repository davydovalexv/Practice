from dv_agent.model.dv_schema import SourceColumn, SourceTable
from dv_agent.ui.schema_diagram import build_er_diagram, collect_foreign_keys, mermaid_entity_id


def _oil_tables() -> list[SourceTable]:
    return [
        SourceTable(
            name="wells",
            schema_name="src",
            columns=[
                SourceColumn(name="well_id", data_type="VARCHAR(50)", is_primary_key=True),
            ],
        ),
        SourceTable(
            name="production",
            schema_name="src",
            columns=[
                SourceColumn(name="production_id", data_type="VARCHAR(50)", is_primary_key=True),
                SourceColumn(name="well_id", data_type="VARCHAR(50)", references="wells"),
            ],
        ),
        SourceTable(
            name="oil_stations",
            schema_name="src",
            columns=[
                SourceColumn(name="station_id", data_type="VARCHAR(50)", is_primary_key=True),
            ],
        ),
        SourceTable(
            name="deliveries",
            schema_name="src",
            columns=[
                SourceColumn(name="delivery_id", data_type="VARCHAR(50)", is_primary_key=True),
                SourceColumn(name="well_id", data_type="VARCHAR(50)", references="wells"),
                SourceColumn(name="station_id", data_type="VARCHAR(50)"),
                SourceColumn(name="batch_id", data_type="VARCHAR(50)"),
            ],
        ),
    ]


def test_mermaid_entity_id():
    assert mermaid_entity_id("oil_stations") == "oil_stations"
    assert mermaid_entity_id("src.wells") == "src_wells"


def test_build_er_diagram_explicit_fk():
    diagram = build_er_diagram(_oil_tables())
    assert "erDiagram" in diagram
    assert "production" in diagram
    assert "well_id" in diagram
    assert "||--o{" in diagram


def test_collect_foreign_keys_inferred():
    tables = _oil_tables()
    deliveries = next(table for table in tables if table.name == "deliveries")
    links = collect_foreign_keys(deliveries, tables)
    parents = {parent for _, _, parent in links}
    assert "wells" in parents
    assert "oil_stations" in parents


def test_hr_schema_no_spurious_id_links():
    from pathlib import Path

    from dv_agent.parser.loader import parse_sql_path
    from dv_agent.parser.options import ParseOptions

    sql = Path("/home/weiss/HR/hr_postgres_schema.sql")
    if not sql.is_file():
        return
    parsed = parse_sql_path(sql, ParseOptions())
    diagram = build_er_diagram(parsed.tables, include_inferred=True)
    assert "employee_categories : \"id\"" not in diagram
    assert "col_year" in diagram or "year" not in diagram.split("monthly_average_headcount {")[1].split("}")[0]
    assert "||--o{" in diagram
