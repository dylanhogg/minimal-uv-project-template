from __future__ import annotations

import csv
import io
import json
import time
from pathlib import Path
from typing import Any

import duckdb
import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

app = typer.Typer(
    help="Interactive DuckDB SQL explorer for CSV/Parquet files.",
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=True,
)


def _detect_reader(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return "read_csv_auto"
    if suffix in {".parquet", ".pq"}:
        return "read_parquet"
    raise typer.BadParameter("Only .csv and .parquet/.pq files are supported.")


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _split_pipe_sections(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("|") if part.strip()]


def _format_scalar(value: Any, max_chars: int | None) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    if max_chars is None or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return f"{text[: max_chars - 3]}..."


def _is_numeric_type(type_name: str) -> bool:
    numeric_markers = ("INT", "DECIMAL", "DOUBLE", "FLOAT", "REAL", "NUMERIC")
    upper = type_name.upper()
    return any(marker in upper for marker in numeric_markers)


def _parse_toggle(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered == "on":
        return True
    if lowered == "off":
        return False
    return None


def _rows_to_csv(columns: list[str], rows: list[tuple[Any, ...]], max_chars: int | None) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_format_scalar(v, max_chars) for v in row])
    return buf.getvalue().rstrip("\n")


def _rows_to_markdown(columns: list[str], rows: list[tuple[Any, ...]], max_chars: int | None) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(_format_scalar(v, max_chars) for v in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _rows_to_json(columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    records = [dict(zip(columns, row, strict=False)) for row in rows]
    return json.dumps(records, indent=2, default=str)


@app.command()
def main(
    data: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True, help="CSV or Parquet file path."),
    table_name: str = typer.Option("data", "--table", "-t", help="Logical table/view name inside DuckDB."),
    limit: int = typer.Option(100, "--limit", "-l", min=1, help="Default row limit for raw selects/sample views."),
    database: str = typer.Option(":memory:", "--db", help="DuckDB database path. Use :memory: for in-memory session."),
    execute: str | None = typer.Option(None, "--execute", "-e", help="Run SQL non-interactively and exit."),
    query_file: Path | None = typer.Option(
        None,
        "--file",
        "-f",
        exists=True,
        readable=True,
        resolve_path=True,
        help="Run SQL from file non-interactively and exit.",
    ),
) -> None:
    if execute and query_file:
        raise typer.BadParameter("Use either --execute or --file, not both.")

    file_path = data.expanduser().resolve()
    reader = _detect_reader(file_path)
    safe_table = table_name.replace('"', "")

    console = Console()
    conn = duckdb.connect(database=database)

    conn.execute(f'DROP VIEW IF EXISTS "{safe_table}"')
    conn.execute(f'CREATE VIEW "{safe_table}" AS SELECT * FROM {reader}({_sql_literal(str(file_path))})')

    schema_rows = conn.execute(f'DESCRIBE "{safe_table}"').fetchall()
    columns = [str(row[0]) for row in schema_rows]
    column_types = {str(row[0]): str(row[1]) for row in schema_rows}
    column_lookup = {col.lower(): col for col in columns}

    class SchemaCompleter(Completer):
        def __init__(self, words: list[str]) -> None:
            self.words = sorted(set(words), key=str.lower)

        def get_completions(self, document: Any, complete_event: Any) -> Any:
            word = document.get_word_before_cursor(WORD=True)
            low = word.lower()
            for candidate in self.words:
                if candidate.lower().startswith(low):
                    yield Completion(candidate, start_position=-len(word), display=candidate)

    sql_keywords = [
        "SELECT",
        "FROM",
        "WHERE",
        "GROUP BY",
        "ORDER BY",
        "HAVING",
        "LIMIT",
        "DISTINCT",
        "ASC",
        "DESC",
    ]
    sql_functions = [
        "COUNT()",
        "SUM()",
        "AVG()",
        "MIN()",
        "MAX()",
        "COALESCE()",
        "ROUND()",
        "LENGTH()",
        "LOWER()",
        "UPPER()",
        "DATE_TRUNC()",
        "QUANTILE_CONT()",
    ]

    aliases = ["d", "t"]
    aliased_columns = [f"{alias}.{col}" for alias in aliases for col in columns]

    help_entries: list[tuple[str, str, str | None]] = [
        (":help", "Show command guide", None),
        (":schema", "Show schema and types", None),
        (":sample [n]", "Preview first rows", ":sample 10"),
        (":filter <condition>", "Apply WHERE condition", ":filter label = 1"),
        (":sort <exprs>", "Sort rows", ":sort label DESC, text ASC"),
        (":group <cols> | <aggs> [| having]", "Group and aggregate", ":group label | count(*) AS n"),
        (":agg <aggs> [| where]", "Run aggregate expressions", ":agg count(*) AS n, avg(label) AS avg_label"),
        (":history [n]", "Show recent executed SQL", ":history 15"),
        (":rerun <n>", "Execute SQL from :history index", ":rerun 3"),
        (":format <table|csv|json|markdown>", "Set output format", ":format markdown"),
        (":page <on|off>", "Toggle pager for long output", ":page on"),
        (":truncate rows <n|off>", "Set max displayed rows", ":truncate rows 200"),
        (":truncate values <n|off>", "Set max chars per value", ":truncate values 120"),
        (":width <n|auto>", "Set table column width", ":width 40"),
        (":show types", "Show type and null/count summary", None),
        (":profile <col>", "Distinct/null/min/max/quantiles", ":profile label"),
        (":top <col> [n]", "Top value frequencies", ":top label 10"),
        (":describe", "Dataset stats and quality summary", None),
        (":save <path>", "Save last result (.csv/.parquet/.json)", ":save /tmp/result.parquet"),
        (":query", "Open guided query builder", None),
        (":last", "Show previous SQL", None),
        (":clear", "Clear screen", None),
        (":exit, :quit", "Exit", None),
    ]

    helper_commands = [
        ":help",
        ":schema",
        ":sample",
        ":filter",
        ":sort",
        ":group",
        ":agg",
        ":query",
        ":history",
        ":rerun",
        ":format",
        ":page",
        ":truncate",
        ":width",
        ":show",
        ":profile",
        ":top",
        ":describe",
        ":save",
        ":last",
        ":clear",
        ":exit",
        ":quit",
    ]

    completer = SchemaCompleter(
        [
            safe_table,
            *columns,
            *aliased_columns,
            *aliases,
            *sql_keywords,
            *sql_functions,
            *helper_commands,
        ]
    )

    history_path = str(Path.home() / ".my_project_sql_history")
    session: PromptSession[str] = PromptSession(
        completer=completer,
        history=FileHistory(history_path),
        auto_suggest=AutoSuggestFromHistory(),
        style=Style.from_dict({"prompt": "bold cyan", "continuation": "cyan"}),
    )

    output_format = "table"
    paging_enabled = False
    max_rows_display: int | None = 200
    max_value_chars: int | None = 120
    column_width: int | None = None

    executed_sql: list[str] = []
    last_sql = f'SELECT * FROM "{safe_table}" LIMIT {limit}'
    last_result_sql: str | None = None

    def row_count() -> int:
        out = conn.execute(f'SELECT COUNT(*) FROM "{safe_table}"').fetchone()
        if out is None:
            raise RuntimeError("Failed to count rows.")
        return int(out[0])

    def resolve_column(raw: str) -> str | None:
        candidate = raw.strip()
        if candidate.startswith('"') and candidate.endswith('"') and len(candidate) >= 2:
            candidate = candidate[1:-1].replace('""', '"')
        return column_lookup.get(candidate.lower())

    def display_rows(rows: list[tuple[Any, ...]]) -> tuple[list[tuple[Any, ...]], bool]:
        if max_rows_display is None:
            return rows, False
        if len(rows) <= max_rows_display:
            return rows, False
        return rows[:max_rows_display], True

    def print_renderable(renderable: RenderableType, use_pager: bool = False) -> None:
        if paging_enabled and use_pager:
            with console.pager(styles=True):
                console.print(renderable)
            return
        console.print(renderable)

    def print_text(text: str, use_pager: bool = False) -> None:
        if paging_enabled and use_pager:
            with console.pager(styles=False):
                console.print(text)
            return
        console.print(text)

    def render_rows(sql_text: str, generated: bool = False, remember: bool = True) -> bool:
        nonlocal last_sql
        nonlocal last_result_sql
        t0 = time.perf_counter()
        try:
            rel = conn.execute(sql_text)
            rows = rel.fetchall()
            cols = [str(d[0]) for d in rel.description] if rel.description else []
            elapsed_ms = (time.perf_counter() - t0) * 1000
        except Exception as exc:  # noqa: BLE001
            console.print(Panel(str(exc), title="Query Error", border_style="red"))
            return False

        last_sql = sql_text
        if remember:
            executed_sql.append(str(sql_text))

        if generated:
            console.print(
                Panel(
                    Syntax(sql_text, "sql", line_numbers=False),
                    title="Generated SQL",
                    border_style="magenta",
                )
            )

        if not cols:
            console.print(Panel(f"Statement executed in {elapsed_ms:.1f} ms", border_style="green"))
            return True

        shown_rows, truncated = display_rows(rows)
        shown_count = len(shown_rows)
        last_result_sql = sql_text

        if output_format == "table":
            table = Table(
                title=f"Result ({len(rows)} rows, {elapsed_ms:.1f} ms)",
                box=box.MINIMAL_DOUBLE_HEAD,
                show_lines=False,
            )
            for col in cols:
                if column_width is None:
                    table.add_column(col, overflow="fold")
                else:
                    table.add_column(col, overflow="fold", max_width=column_width)
            for row in shown_rows:
                table.add_row(*[_format_scalar(v, max_value_chars) for v in row])
            print_renderable(table, use_pager=len(rows) > shown_count)
        elif output_format == "csv":
            print_text(_rows_to_csv(cols, shown_rows, max_value_chars), use_pager=len(rows) > shown_count)
        elif output_format == "markdown":
            print_text(_rows_to_markdown(cols, shown_rows, max_value_chars), use_pager=len(rows) > shown_count)
        elif output_format == "json":
            print_text(_rows_to_json(cols, shown_rows), use_pager=len(rows) > shown_count)

        if truncated:
            console.print(f"[yellow]Showing {shown_count} of {len(rows)} rows.[/yellow]")
        console.print(
            f"[dim]format={output_format} page={'on' if paging_enabled else 'off'} elapsed={elapsed_ms:.1f}ms[/dim]"
        )
        return True

    def build_help_text() -> str:
        lines = [f"[bold]Run SQL directly[/bold]: `SELECT * FROM {safe_table} LIMIT 20;`", "[bold]Helpers[/bold]:"]
        usage_width = max(len(usage) for usage, _, _ in help_entries)
        for usage, description, example in help_entries:
            lines.append(f"  {usage:<{usage_width}}  {description}")
            if example is not None:
                lines.append(f"  {'':<{usage_width}}  e.g. {example}")
        lines.append(
            f"\n[bold]Display[/bold]: format={output_format}, page={'on' if paging_enabled else 'off'}, "
            f"rows={'off' if max_rows_display is None else max_rows_display}, "
            f"values={'off' if max_value_chars is None else max_value_chars}, "
            f"width={'auto' if column_width is None else column_width}"
        )
        return "\n".join(lines)

    def schema_table() -> Table:
        table = Table(title=f"Schema: {safe_table}", box=box.SIMPLE_HEAVY)
        table.add_column("Column", style="bold")
        table.add_column("Type")
        table.add_column("Nullable")
        for row in schema_rows:
            table.add_row(str(row[0]), str(row[1]), str(row[2]))
        return table

    def null_counts_by_column() -> dict[str, int]:
        counts: dict[str, int] = {}
        for col in columns:
            qcol = _quote_ident(col)
            out = conn.execute(f'SELECT SUM(CASE WHEN {qcol} IS NULL THEN 1 ELSE 0 END) FROM "{safe_table}"').fetchone()
            counts[col] = 0 if out is None or out[0] is None else int(out[0])
        return counts

    def show_type_summary() -> None:
        total_rows = row_count()
        nulls = null_counts_by_column()
        table = Table(title="Column Summary", box=box.SIMPLE_HEAVY)
        table.add_column("Column", style="bold")
        table.add_column("Type")
        table.add_column("Nulls", justify="right")
        table.add_column("Non-null", justify="right")
        table.add_column("Null %", justify="right")
        for col in columns:
            null_count = nulls[col]
            non_null = total_rows - null_count
            pct = (100.0 * null_count / total_rows) if total_rows else 0.0
            table.add_row(col, column_types[col], str(null_count), str(non_null), f"{pct:.2f}%")
        console.print(table)

    def describe_dataset() -> None:
        total_rows = row_count()
        total_columns = len(columns)
        nulls = null_counts_by_column()
        null_cells = sum(nulls.values())
        total_cells = total_rows * total_columns
        completeness = (100.0 * (total_cells - null_cells) / total_cells) if total_cells else 100.0

        distinct_rows_result = conn.execute(
            f'SELECT COUNT(*) FROM (SELECT DISTINCT * FROM "{safe_table}") as distinct_rows'
        ).fetchone()
        distinct_rows = int(distinct_rows_result[0]) if distinct_rows_result else total_rows
        duplicate_rows = max(0, total_rows - distinct_rows)

        summary = Table(title="Dataset Summary", box=box.SIMPLE_HEAVY)
        summary.add_column("Metric", style="bold")
        summary.add_column("Value", justify="right")
        summary.add_row("Rows", str(total_rows))
        summary.add_row("Columns", str(total_columns))
        summary.add_row("Total null cells", str(null_cells))
        summary.add_row("Completeness", f"{completeness:.2f}%")
        summary.add_row("Duplicate rows", str(duplicate_rows))
        console.print(summary)

        quality = Table(title="Top Null-Rate Columns", box=box.SIMPLE_HEAVY)
        quality.add_column("Column", style="bold")
        quality.add_column("Nulls", justify="right")
        quality.add_column("Null %", justify="right")
        ranked = sorted(columns, key=lambda c: nulls[c], reverse=True)[:5]
        for col in ranked:
            pct = (100.0 * nulls[col] / total_rows) if total_rows else 0.0
            quality.add_row(col, str(nulls[col]), f"{pct:.2f}%")
        console.print(quality)

    def profile_column(raw_column: str) -> None:
        resolved = resolve_column(raw_column)
        if resolved is None:
            console.print(f"[red]Unknown column: {raw_column}[/red]")
            return
        qcol = _quote_ident(resolved)
        stats = conn.execute(
            f'''SELECT
                COUNT(*) AS total_rows,
                COUNT(DISTINCT {qcol}) AS distinct_count,
                SUM(CASE WHEN {qcol} IS NULL THEN 1 ELSE 0 END) AS null_count,
                MIN({qcol}) AS min_value,
                MAX({qcol}) AS max_value
            FROM "{safe_table}"'''
        ).fetchone()
        if stats is None:
            console.print("[red]Unable to compute profile.[/red]")
            return

        profile = Table(title=f"Profile: {resolved}", box=box.SIMPLE_HEAVY)
        profile.add_column("Metric", style="bold")
        profile.add_column("Value")
        profile.add_row("Type", column_types[resolved])
        profile.add_row("Rows", str(int(stats[0])))
        profile.add_row("Distinct", str(int(stats[1])))
        profile.add_row("Nulls", str(int(stats[2])))
        profile.add_row("Min", _format_scalar(stats[3], max_value_chars))
        profile.add_row("Max", _format_scalar(stats[4], max_value_chars))

        if _is_numeric_type(column_types[resolved]):
            quantiles = conn.execute(
                f'''SELECT
                    QUANTILE_CONT({qcol}, 0.25),
                    QUANTILE_CONT({qcol}, 0.50),
                    QUANTILE_CONT({qcol}, 0.75)
                FROM "{safe_table}"
                WHERE {qcol} IS NOT NULL'''
            ).fetchone()
            if quantiles is not None:
                profile.add_row("P25", _format_scalar(quantiles[0], max_value_chars))
                profile.add_row("P50", _format_scalar(quantiles[1], max_value_chars))
                profile.add_row("P75", _format_scalar(quantiles[2], max_value_chars))

        console.print(profile)

    def top_values(raw_column: str, n: int) -> None:
        resolved = resolve_column(raw_column)
        if resolved is None:
            console.print(f"[red]Unknown column: {raw_column}[/red]")
            return
        n = max(1, n)
        qcol = _quote_ident(resolved)
        sql = (
            f'SELECT {qcol} AS value, COUNT(*) AS count FROM "{safe_table}" '
            f"GROUP BY {qcol} ORDER BY count DESC, value LIMIT {n}"
        )
        render_rows(sql, generated=True)

    def save_last_result(path_arg: str) -> None:
        if last_result_sql is None:
            console.print("[red]No query result to save yet.[/red]")
            return

        out = Path(path_arg).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        suffix = out.suffix.lower()

        try:
            if suffix == ".csv":
                conn.execute(f"COPY ({last_result_sql}) TO {_sql_literal(str(out))} (HEADER, DELIMITER ',')")
            elif suffix in {".parquet", ".pq"}:
                conn.execute(f"COPY ({last_result_sql}) TO {_sql_literal(str(out))} (FORMAT PARQUET)")
            elif suffix == ".json":
                rel = conn.execute(last_result_sql)
                rows = rel.fetchall()
                cols = [str(d[0]) for d in rel.description] if rel.description else []
                out.write_text(_rows_to_json(cols, rows), encoding="utf-8")
            else:
                console.print("[red]Unsupported extension. Use .csv, .parquet/.pq, or .json[/red]")
                return
        except Exception as exc:  # noqa: BLE001
            console.print(Panel(str(exc), title="Save Error", border_style="red"))
            return

        console.print(f"[green]Saved result to {out}[/green]")

    def command_to_sql(raw: str) -> str | None:
        stripped = raw.strip()
        if not stripped:
            return None

        if stripped.startswith(":sample"):
            parts = stripped.split()
            sample_n = limit
            if len(parts) > 1:
                try:
                    sample_n = max(1, int(parts[1]))
                except ValueError:
                    console.print("[red]:sample expects an integer row count[/red]")
                    return None
            return f'SELECT * FROM "{safe_table}" LIMIT {sample_n}'

        if stripped.startswith(":filter"):
            cond = stripped.removeprefix(":filter").strip()
            if not cond:
                console.print("[red]Usage: :filter <where condition>[/red]")
                return None
            return f'SELECT * FROM "{safe_table}" WHERE {cond} LIMIT {limit}'

        if stripped.startswith(":sort"):
            expr = stripped.removeprefix(":sort").strip()
            if not expr:
                console.print("[red]Usage: :sort <order expressions>[/red]")
                return None
            return f'SELECT * FROM "{safe_table}" ORDER BY {expr} LIMIT {limit}'

        if stripped.startswith(":group"):
            payload = stripped.removeprefix(":group").strip()
            parts = _split_pipe_sections(payload)
            if len(parts) < 2:
                console.print("[red]Usage: :group <group cols> | <aggregates> [| having][/red]")
                return None
            group_cols = parts[0]
            aggs = parts[1]
            having = parts[2] if len(parts) > 2 else ""
            sql = f'SELECT {group_cols}, {aggs} FROM "{safe_table}" GROUP BY {group_cols}'
            if having:
                sql += f" HAVING {having}"
            sql += f" ORDER BY {group_cols}"
            return sql

        if stripped.startswith(":agg"):
            payload = stripped.removeprefix(":agg").strip()
            parts = _split_pipe_sections(payload)
            if not parts:
                console.print("[red]Usage: :agg <aggregates> [| where][/red]")
                return None
            aggs = parts[0]
            where = parts[1] if len(parts) > 1 else ""
            sql = f'SELECT {aggs} FROM "{safe_table}"'
            if where:
                sql += f" WHERE {where}"
            return sql

        if stripped.startswith(":query"):
            console.print("[cyan]Query builder (leave blank to skip a section)[/cyan]")
            select_expr = session.prompt("select> ").strip() or "*"
            where_expr = session.prompt("where> ").strip()
            group_expr = session.prompt("group by> ").strip()
            having_expr = session.prompt("having> ").strip()
            order_expr = session.prompt("order by> ").strip()
            limit_expr = session.prompt(f"limit [{limit}]> ").strip() or str(limit)
            sql = f'SELECT {select_expr} FROM "{safe_table}"'
            if where_expr:
                sql += f" WHERE {where_expr}"
            if group_expr:
                sql += f" GROUP BY {group_expr}"
            if having_expr:
                sql += f" HAVING {having_expr}"
            if order_expr:
                sql += f" ORDER BY {order_expr}"
            sql += f" LIMIT {limit_expr}"
            return sql

        return str(stripped)

    def print_startup_ui() -> None:
        meta = Table.grid(expand=True)
        meta.add_column(justify="left")
        meta.add_column(justify="right")
        meta.add_row(f"[bold]File[/bold] {file_path}", f"[bold]Rows[/bold] {row_count()}")
        meta.add_row(f"[bold]Engine[/bold] DuckDB ({database})", f"[bold]Columns[/bold] {len(columns)}")
        console.print(Panel(meta, title="Data Explorer", border_style="cyan"))
        console.print(schema_table())
        console.print(Panel(build_help_text(), title="Command Guide", border_style="blue"))

        first_col = columns[0] if columns else "<col>"
        numeric_col = next((col for col in columns if _is_numeric_type(column_types[col])), first_col)
        hints = [
            ":sample 10",
            f'SELECT * FROM "{safe_table}" LIMIT 20;',
            f":top {first_col} 10",
            f":profile {numeric_col}",
            ":describe",
        ]
        hint_lines = [f"  {idx}. {item}" for idx, item in enumerate(hints, start=1)]
        console.print(Panel("\n".join(hint_lines), title="Try These First", border_style="green"))

    non_interactive_sql = execute
    if query_file is not None:
        non_interactive_sql = query_file.read_text(encoding="utf-8").strip()

    if non_interactive_sql is not None:
        once_sql: str = str(non_interactive_sql).rstrip(";")
        render_rows(once_sql, remember=False)
        return

    print_startup_ui()

    while True:
        try:
            raw: str = str(session.prompt([("class:prompt", "sql> ")]))
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cyan]Exiting SQL explorer.[/cyan]")
            break

        stripped: str = str(raw).strip()
        if not stripped:
            continue

        if stripped in {":exit", ":quit"}:
            break
        if stripped == ":help":
            console.print(Panel(build_help_text(), title="Command Guide", border_style="blue"))
            continue
        if stripped == ":schema":
            console.print(schema_table())
            continue
        if stripped == ":clear":
            console.clear()
            continue
        if stripped == ":last":
            console.print(Panel(Syntax(last_sql, "sql", line_numbers=False), title="Last SQL", border_style="magenta"))
            continue
        if stripped.startswith(":history"):
            parts = stripped.split()
            count = 20
            if len(parts) > 1:
                try:
                    count = max(1, int(parts[1]))
                except ValueError:
                    console.print("[red]Usage: :history [n][/red]")
                    continue
            history_queries = [str(item) for item in executed_sql]
            if not history_queries:
                console.print("[yellow]No SQL has been executed yet.[/yellow]")
                continue
            hist = Table(title="Query History", box=box.SIMPLE_HEAVY)
            hist.add_column("#", justify="right")
            hist.add_column("SQL")
            for idx, sql in list(enumerate(history_queries, start=1))[-count:]:
                hist.add_row(str(idx), _format_scalar(sql, 180))
            console.print(hist)
            continue
        if stripped.startswith(":rerun"):
            parts = stripped.split()
            if len(parts) != 2:
                console.print("[red]Usage: :rerun <n>[/red]")
                continue
            try:
                idx = int(parts[1])
            except ValueError:
                console.print("[red]:rerun expects a numeric history index[/red]")
                continue
            history_queries = [str(item) for item in executed_sql]
            history_size: int = len(history_queries)
            if idx < 1 or idx > history_size:
                console.print("[red]History index out of range.[/red]")
                continue
            rerun_sql: str = history_queries[idx - 1]
            render_rows(rerun_sql, generated=True)
            continue
        if stripped.startswith(":page"):
            parts = stripped.split(maxsplit=1)
            if len(parts) != 2:
                console.print("[red]Usage: :page <on|off>[/red]")
                continue
            parsed = _parse_toggle(parts[1])
            if parsed is None:
                console.print("[red]Usage: :page <on|off>[/red]")
                continue
            paging_enabled = parsed
            console.print(f"[green]Paging {'enabled' if paging_enabled else 'disabled'}.[/green]")
            continue
        if stripped.startswith(":truncate"):
            parts = stripped.split()
            if len(parts) != 3:
                console.print("[red]Usage: :truncate rows <n|off> OR :truncate values <n|off>[/red]")
                continue
            target = parts[1].lower()
            value = parts[2].lower()
            parsed_int: int | None
            if value == "off":
                parsed_int = None
            else:
                try:
                    parsed_int = max(1, int(value))
                except ValueError:
                    console.print("[red]Truncation value must be an integer or off.[/red]")
                    continue
            if target == "rows":
                max_rows_display = parsed_int
                console.print(
                    f"[green]Row truncation set to {'off' if max_rows_display is None else max_rows_display}.[/green]"
                )
                continue
            if target == "values":
                max_value_chars = parsed_int
                console.print(
                    f"[green]Value truncation set to {'off' if max_value_chars is None else max_value_chars}.[/green]"
                )
                continue
            console.print("[red]Usage: :truncate rows <n|off> OR :truncate values <n|off>[/red]")
            continue
        if stripped.startswith(":width"):
            parts = stripped.split(maxsplit=1)
            if len(parts) != 2:
                console.print("[red]Usage: :width <n|auto>[/red]")
                continue
            value = parts[1].strip().lower()
            if value == "auto":
                column_width = None
                console.print("[green]Column width set to auto.[/green]")
                continue
            try:
                column_width = max(1, int(value))
            except ValueError:
                console.print("[red]Usage: :width <n|auto>[/red]")
                continue
            console.print(f"[green]Column width set to {column_width}.[/green]")
            continue
        if stripped.startswith(":format"):
            parts = stripped.split(maxsplit=1)
            if len(parts) != 2:
                console.print("[red]Usage: :format <table|csv|json|markdown>[/red]")
                continue
            chosen = parts[1].strip().lower()
            if chosen not in {"table", "csv", "json", "markdown"}:
                console.print("[red]Format must be one of: table, csv, json, markdown[/red]")
                continue
            output_format = chosen
            console.print(f"[green]Output format set to {output_format}.[/green]")
            continue
        if stripped == ":show types":
            show_type_summary()
            continue
        if stripped.startswith(":profile"):
            payload = stripped.removeprefix(":profile").strip()
            if not payload:
                console.print("[red]Usage: :profile <col>[/red]")
                continue
            profile_column(payload)
            continue
        if stripped.startswith(":top"):
            parts = stripped.split()
            if len(parts) < 2 or len(parts) > 3:
                console.print("[red]Usage: :top <col> [n][/red]")
                continue
            top_n = 10
            if len(parts) == 3:
                try:
                    top_n = int(parts[2])
                except ValueError:
                    console.print("[red]Usage: :top <col> [n][/red]")
                    continue
            top_values(parts[1], top_n)
            continue
        if stripped == ":describe":
            describe_dataset()
            continue
        if stripped.startswith(":save"):
            payload = stripped.removeprefix(":save").strip()
            if not payload:
                console.print("[red]Usage: :save <path>[/red]")
                continue
            save_last_result(payload)
            continue

        sql_candidate: str | None = command_to_sql(stripped)
        if sql_candidate is None:
            continue

        sql_text: str = sql_candidate.rstrip(";")
        render_rows(sql_text, generated=stripped.startswith(":"))


if __name__ == "__main__":
    app()
