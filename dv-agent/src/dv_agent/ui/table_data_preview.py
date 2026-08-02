from __future__ import annotations

import pandas as pd
import streamlit as st

from dv_agent.model.dv_schema import SourceTable
from dv_agent.parser.sql_data import MAX_PREVIEW_ROWS


def render_table_data_section(
    tables: list[SourceTable],
    previews: dict[str, tuple[list[dict[str, object]], str]],
) -> None:
    st.markdown("#### Данные таблиц (первые 30 строк)")

    if not tables:
        st.info("Сначала разберите SQL.")
        return

    table_names = sorted({table.name for table in tables})
    selected = st.selectbox("Таблица", table_names, key="preview_table_select")

    rows, source = previews.get(selected, ([], "нет данных"))
    st.caption(f"Источник: {source} · показано до {MAX_PREVIEW_ROWS} строк")

    if not rows:
        st.info("Для этой таблицы нет строк в INSERT SQL и нет данных в PostgreSQL.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Строк: {len(df)}")
