from __future__ import annotations

import html

import streamlit.components.v1 as components


def render_mermaid(diagram: str, *, height: int = 480) -> None:
    """Отрисовать Mermaid-диаграмму в Streamlit через mermaid.js."""
    escaped = html.escape(diagram.strip())
    components.html(
        f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    body {{ margin: 0; padding: 8px; background: transparent; }}
    .mermaid {{ font-family: sans-serif; }}
  </style>
</head>
<body>
  <pre class="mermaid">{escaped}</pre>
  <script>
    mermaid.initialize({{
      startOnLoad: true,
      theme: "default",
      er: {{ layoutDirection: "TB" }},
      securityLevel: "loose"
    }});
  </script>
</body>
</html>
        """,
        height=height,
        scrolling=True,
    )
