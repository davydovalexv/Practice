from __future__ import annotations

import re
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from dv_agent.model.dv_schema import SourceTable
from dv_agent.parser.loader import _read_sql_file
from dv_agent.parser.options import ParseOptions
from dv_agent.parser.sql_preprocess import split_sql_statements, sanitize_sql

MAX_PREVIEW_ROWS = 30

_INSERT_STMT_PATTERN = re.compile(
    r"INSERT\s+INTO\b.+?;",
    re.IGNORECASE | re.DOTALL,
)


def _iter_insert_statements(cleaned: str) -> list[str]:
    seen: set[str] = set()
    statements: list[str] = []

    def add(statement: str) -> None:
        key = re.sub(r"\s+", " ", statement.strip().rstrip(";")).lower()
        if key and key not in seen:
            seen.add(key)
            statements.append(statement)

    for statement in split_sql_statements(cleaned):
        if statement.strip().upper().startswith("INSERT"):
            add(statement)

    for match in _INSERT_STMT_PATTERN.finditer(cleaned):
        add(match.group(0))

    return statements


def _literal_to_python(node: exp.Expression | None) -> object:
    if node is None or isinstance(node, exp.Null):
        return None
    if isinstance(node, exp.Boolean):
        return str(node.this).lower() == "true"
    if isinstance(node, exp.Literal):
        if node.is_string:
            return node.this
        text = node.this
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return text
    if isinstance(node, exp.Cast):
        return _literal_to_python(node.this)
    if isinstance(node, exp.Neg):
        value = _literal_to_python(node.this)
        if isinstance(value, (int, float)):
            return -value
    return node.sql().strip("'\"")


def _insert_target(insert: exp.Insert) -> tuple[str, str | None, list[str]]:
    target = insert.this
    columns: list[str] = []
    if isinstance(target, exp.Schema):
        table_expr = target.this
        columns = [
            col.name
            for col in target.expressions
            if isinstance(col, (exp.Column, exp.Identifier))
        ]
    elif isinstance(target, exp.Table):
        table_expr = target
    else:
        return "unknown", None, []

    if not isinstance(table_expr, exp.Table):
        return "unknown", None, columns

    schema = table_expr.db or None
    return table_expr.name, schema, columns


def _rows_from_values(
    values: exp.Values,
    columns: list[str],
    fallback_columns: list[str],
) -> list[dict[str, object]]:
    col_names = columns or fallback_columns
    rows: list[dict[str, object]] = []
    for tuple_expr in values.expressions:
        if not isinstance(tuple_expr, exp.Tuple):
            continue
        cells = [_literal_to_python(cell) for cell in tuple_expr.expressions]
        if col_names and len(col_names) == len(cells):
            rows.append(dict(zip(col_names, cells, strict=True)))
        elif col_names:
            padded = cells + [None] * max(0, len(col_names) - len(cells))
            rows.append(dict(zip(col_names, padded[: len(col_names)], strict=True)))
        else:
            rows.append({f"col_{index + 1}": value for index, value in enumerate(cells)})
    return rows


def _extract_insert_rows(
    insert: exp.Insert,
    table_columns: dict[str, list[str]],
) -> tuple[str, list[dict[str, object]]]:
    table_name, _schema, columns = _insert_target(insert)
    expression = insert.expression
    if isinstance(expression, exp.Values):
        fallback = table_columns.get(table_name, [])
        return table_name, _rows_from_values(expression, columns, fallback)
    return table_name, []


def extract_inserts_from_text(
    sql_text: str,
    *,
    dialect: str = "postgres",
    table_columns: dict[str, list[str]] | None = None,
    max_rows_per_table: int = MAX_PREVIEW_ROWS,
) -> dict[str, list[dict[str, object]]]:
    columns_map = table_columns or {}
    result: dict[str, list[dict[str, object]]] = {}
    cleaned = sanitize_sql(sql_text)

    for statement in _iter_insert_statements(cleaned):
        try:
            parsed = sqlglot.parse_one(statement, dialect=dialect)
        except ParseError:
            continue
        if not isinstance(parsed, exp.Insert):
            continue

        table_name, rows = _extract_insert_rows(parsed, columns_map)
        if not rows:
            continue

        bucket = result.setdefault(table_name, [])
        for row in rows:
            if len(bucket) >= max_rows_per_table:
                break
            bucket.append(row)

    return result


def extract_inserts_from_files(
    paths: list[Path],
    tables: list[SourceTable],
    *,
    options: ParseOptions | None = None,
    max_rows_per_table: int = MAX_PREVIEW_ROWS,
) -> dict[str, list[dict[str, object]]]:
    opts = options or ParseOptions()
    table_columns = {
        table.name: [column.name for column in table.columns]
        for table in tables
    }
    merged: dict[str, list[dict[str, object]]] = {}

    for path in paths:
        if not path.is_file():
            continue
        try:
            text, _encoding = _read_sql_file(path, opts.encodings)
        except UnicodeDecodeError:
            continue
        part = extract_inserts_from_text(
            text,
            dialect=opts.dialect_name,
            table_columns=table_columns,
            max_rows_per_table=max_rows_per_table,
        )
        for table_name, rows in part.items():
            bucket = merged.setdefault(table_name, [])
            for row in rows:
                if len(bucket) >= max_rows_per_table:
                    break
                bucket.append(row)

    return merged
