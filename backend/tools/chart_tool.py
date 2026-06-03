import json
import plotly.graph_objects as go
from tools.base import BaseTool, ToolResult
from typing import Callable, Awaitable


class GenerateChartTool(BaseTool):
    name = "generate_chart"
    description = (
        "Generate an interactive chart from query result data. "
        "Use for trends, comparisons, and distributions. "
        "Pass the data returned by execute_query."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "description": "Query result with 'columns' (list of str) and 'rows' (list of lists)",
            },
            "chart_type": {
                "type": "string",
                "enum": ["bar", "line", "area", "pie", "donut", "scatter", "heatmap"],
            },
            "title": {"type": "string"},
            "x_column": {"type": "string", "description": "Column name for X axis"},
            "y_column": {"type": "string", "description": "Column name for Y axis"},
            "color_column": {"type": "string", "description": "Optional column for color grouping"},
        },
        "required": ["data", "chart_type", "title", "x_column", "y_column"],
    }

    async def execute(
        self,
        send_event: Callable[[dict], Awaitable[None]],
        data: dict,
        chart_type: str,
        title: str,
        x_column: str,
        y_column: str,
        color_column: str | None = None,
    ) -> ToolResult:
        columns = data.get("columns", [])
        rows = data.get("rows", [])

        if x_column not in columns or y_column not in columns:
            return ToolResult(type="text", cancelled=True, reason=f"Columns '{x_column}' or '{y_column}' not found in data")

        xi = columns.index(x_column)
        yi = columns.index(y_column)
        ci = columns.index(color_column) if color_column and color_column in columns else None

        x_vals = [r[xi] for r in rows]
        y_vals = []
        for r in rows:
            try:
                y_vals.append(float(r[yi]))
            except (TypeError, ValueError):
                y_vals.append(r[yi])

        color_vals = [r[ci] for r in rows] if ci is not None else None

        layout = go.Layout(
            title={"text": title, "font": {"size": 16}},
            paper_bgcolor="white",
            plot_bgcolor="#f8fafc",
            font={"family": "Arial", "color": "#333"},
            margin={"l": 50, "r": 30, "t": 60, "b": 50},
        )

        fig = None

        if chart_type == "bar":
            fig = go.Figure(
                data=[go.Bar(x=x_vals, y=y_vals, marker_color="#1A56B0")],
                layout=layout,
            )
        elif chart_type == "line":
            fig = go.Figure(
                data=[go.Scatter(x=x_vals, y=y_vals, mode="lines+markers", line={"color": "#1A56B0"})],
                layout=layout,
            )
        elif chart_type == "area":
            fig = go.Figure(
                data=[go.Scatter(x=x_vals, y=y_vals, fill="tozeroy", mode="lines", line={"color": "#1A56B0"})],
                layout=layout,
            )
        elif chart_type in ("pie", "donut"):
            hole = 0.4 if chart_type == "donut" else 0
            fig = go.Figure(
                data=[go.Pie(labels=x_vals, values=y_vals, hole=hole)],
                layout=layout,
            )
        elif chart_type == "scatter":
            fig = go.Figure(
                data=[go.Scatter(x=x_vals, y=y_vals, mode="markers", marker={"color": "#1A56B0", "size": 8})],
                layout=layout,
            )
        elif chart_type == "heatmap":
            fig = go.Figure(
                data=[go.Heatmap(z=y_vals, x=x_vals, colorscale="Blues")],
                layout=layout,
            )

        if fig is None:
            return ToolResult(type="text", cancelled=True, reason=f"Unsupported chart type: {chart_type}")

        plotly_json = json.loads(fig.to_json())
        result = ToolResult(type="chart", data=plotly_json, source=title)
        result.sse_event = {"event": "chart", "data": {"plotly_json": plotly_json, "title": title}}
        return result
