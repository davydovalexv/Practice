from __future__ import annotations

import re

from dv_agent.model.dv_schema import SourceTable

_MERMAID_SAFE = re.compile(r"[^a-zA-Z0-9_]")
_RESERVED_ATTR = frozenset({
    "end",
    "start",
    "order",
    "join",
    "year",
    "month",
    "key",
    "value",
    "type",
    "name",
    "date",
    "user",
    "group",
    "table",
    "index",
    "check",
    "default",
    "null",
    "true",
    "false",
})


def mermaid_entity_id(name: str) -> str:
    cleaned = _MERMAID_SAFE.sub("_", name)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned or "table"


def mermaid_attr_name(column: str) -> str:
    cleaned = _MERMAID_SAFE.sub("_", column)
    if not cleaned:
        return "col"
    if cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    if cleaned.lower() in _RESERVED_ATTR:
        cleaned = f"col_{cleaned}"
    return cleaned


def _short_type(data_type: str) -> str:
    token = data_type.split("(")[0].strip().lower()
    mapping = {
        "character varying": "varchar",
        "varchar": "varchar",
        "integer": "int",
        "int": "int",
        "bigint": "bigint",
        "smallint": "smallint",
        "bigserial": "bigserial",
        "smallserial": "smallserial",
        "serial": "serial",
        "timestamp without time zone": "timestamp",
        "timestamp with time zone": "timestamptz",
        "timestamptz": "timestamptz",
        "numeric": "numeric",
        "decimal": "decimal",
        "double precision": "float",
        "boolean": "bool",
        "bool": "bool",
        "text": "text",
        "date": "date",
    }
    safe = mapping.get(token, token.replace(" ", "_")[:24] or "text")
    return _MERMAID_SAFE.sub("_", safe) or "text"


def _parse_ref_table(ref: str) -> str:
    target = ref.strip()
    if "(" in target:
        target = target.split("(", 1)[0].strip()
    if "." in target:
        target = target.rsplit(".", 1)[-1]
    return target


def _table_index(tables: list[SourceTable]) -> dict[str, SourceTable]:
    index: dict[str, SourceTable] = {}
    for table in tables:
        index[table.name] = table
        index[table.qualified_name] = table
        if table.schema_name:
            index[f"{table.schema_name}.{table.name}"] = table
    return index


def _entity_ids(tables: list[SourceTable]) -> dict[str, str]:
    """Уникальный Mermaid ID для каждой таблицы (schema + name при коллизии)."""
    ids: dict[str, str] = {}
    used: dict[str, str] = {}
    for table in sorted(tables, key=lambda item: item.qualified_name):
        base = mermaid_entity_id(table.name)
        candidate = base
        if table.schema_name and table.schema_name not in ("public", ""):
            candidate = mermaid_entity_id(f"{table.schema_name}_{table.name}")
        if candidate in used and used[candidate] != table.qualified_name:
            candidate = mermaid_entity_id(table.qualified_name.replace(".", "_"))
        suffix = 2
        while candidate in used and used[candidate] != table.qualified_name:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used[candidate] = table.qualified_name
        ids[table.qualified_name] = candidate
        ids[table.name] = candidate
    return ids


def _infer_parent_table(
    fk_column: str,
    child_table: SourceTable,
    tables: list[SourceTable],
    table_index: dict[str, SourceTable],
) -> str | None:
    if fk_column.endswith("_id"):
        stem = fk_column[:-3]
        for candidate in (stem, f"{stem}s"):
            if candidate in table_index and candidate != child_table.name:
                return candidate

    for table in tables:
        if table.name == child_table.name:
            continue
        for column in table.columns:
            if column.is_primary_key and column.name == fk_column:
                return table.name
    return None


def collect_foreign_keys(
    table: SourceTable,
    tables: list[SourceTable],
    *,
    include_inferred: bool = True,
) -> list[tuple[str, str, str]]:
    """Возвращает (child_table, fk_column, parent_table)."""
    table_index = _table_index(tables)
    links: list[tuple[str, str, str]] = []

    for column in table.columns:
        if column.is_primary_key:
            continue

        parent: str | None = None
        if column.references:
            parent = _parse_ref_table(column.references)
            if parent not in table_index:
                parent = _infer_parent_table(column.name, table, tables, table_index) or parent
        elif include_inferred:
            parent = _infer_parent_table(column.name, table, tables, table_index)

        if not parent or parent == table.name:
            continue
        if parent not in table_index:
            continue
        links.append((table.name, column.name, parent))

    return links


def collect_all_foreign_keys(
    tables: list[SourceTable],
    *,
    include_inferred: bool = True,
) -> list[tuple[str, str, str]]:
    links: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for table in tables:
        for link in collect_foreign_keys(table, tables, include_inferred=include_inferred):
            if link not in seen:
                seen.add(link)
                links.append(link)
    return links


def build_er_diagram(tables: list[SourceTable], *, include_inferred: bool = True) -> str:
    if not tables:
        return "erDiagram\n    EMPTY[\"No tables\"]"

    entity_ids = _entity_ids(tables)
    all_links = collect_all_foreign_keys(tables, include_inferred=include_inferred)
    fk_columns = {(child, col) for child, col, _ in all_links}

    lines: list[str] = ["erDiagram"]

    for table in sorted(tables, key=lambda item: item.qualified_name):
        entity = entity_ids[table.qualified_name]
        lines.append(f"    {entity} {{")
        for column in table.columns:
            tags: list[str] = []
            if column.is_primary_key:
                tags.append("PK")
            elif (table.name, column.name) in fk_columns:
                tags.append("FK")
            tag = f" {' '.join(tags)}" if tags else ""
            attr = mermaid_attr_name(column.name)
            lines.append(f"        {_short_type(column.data_type)} {attr}{tag}")
        lines.append("    }")

    seen_edges: set[tuple[str, str, str]] = set()
    for child, col, parent in all_links:
        parent_id = entity_ids.get(parent) or mermaid_entity_id(parent)
        child_id = entity_ids.get(child) or mermaid_entity_id(child)
        edge_key = (parent_id, child_id, col)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        label = mermaid_attr_name(col)
        lines.append(f'    {parent_id} ||--o{{ {child_id} : "{label}"')

    if not all_links and len(tables) > 0:
        lines.append('    NO_LINKS["No FK links detected"]')

    return "\n".join(lines)
