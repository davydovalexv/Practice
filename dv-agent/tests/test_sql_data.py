from pathlib import Path

from dv_agent.parser.sql_data import extract_inserts_from_text


def test_extract_inserts_with_columns():
    sql = """
    CREATE TABLE legal_entities (id SERIAL, enterprise_code TEXT, enterprise_name TEXT);
    INSERT INTO legal_entities (enterprise_code, enterprise_name) VALUES
        ('LE01', 'ЮЛ 1'),
        ('LE02', 'ЮЛ 2');
    """
    data = extract_inserts_from_text(sql, dialect="postgres")
    assert "legal_entities" in data
    assert len(data["legal_entities"]) == 2
    assert data["legal_entities"][0]["enterprise_code"] == "LE01"


def test_extract_inserts_without_columns_uses_table_columns():
    sql = """
    INSERT INTO employee_categories (category_name) VALUES ('Специалист'), ('Рабочий');
    """
    table_columns = {"employee_categories": ["id", "category_name"]}
    data = extract_inserts_from_text(
        sql,
        dialect="postgres",
        table_columns=table_columns,
        max_rows_per_table=30,
    )
    assert data["employee_categories"][0]["category_name"] == "Специалист"


def test_extract_inserts_respects_row_limit():
    values = ", ".join(f"({index})" for index in range(50))
    sql = f"INSERT INTO nums (id) VALUES {values};"
    data = extract_inserts_from_text(
        sql,
        dialect="postgres",
        table_columns={"nums": ["id"]},
        max_rows_per_table=30,
    )
    assert len(data["nums"]) == 30


def test_extract_from_hr_fixture():
    path = Path(__file__).resolve().parents[2] / "output/uploads/workspace/hr_postgres_schema.sql"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    data = extract_inserts_from_text(text, dialect="postgres")
    assert len(data["legal_entities"]) == 4
    assert len(data["employee_categories"]) == 5
