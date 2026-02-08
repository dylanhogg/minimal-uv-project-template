from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, cast

import duckdb
import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, RichLog, Static, TextArea

app = typer.Typer(
    help="Interactive DuckDB SQL explorer for CSV/TSV/Parquet files.",
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=True,
)

ResultStatus = Literal["ok", "info", "error"]
HELPER_COMMANDS = [
    ":help",
    ":schema",
    ":sample",
    ":filter",
    ":sort",
    ":group",
    ":agg",
    ":top",
    ":profile",
    ":describe",
    ":history",
    ":rerun",
    ":rows",
    ":values",
    ":limit",
    ":save",
    ":last",
    ":clear",
    ":exit",
    ":quit",
]
SQL_KEYWORDS = [
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP",
    "BY",
    "HAVING",
    "ORDER",
    "LIMIT",
    "AS",
    "AND",
    "OR",
    "NOT",
    "IN",
    "IS",
    "NULL",
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "DISTINCT",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "LIKE",
    "BETWEEN",
    "DESC",
    "ASC",
    "JOIN",
    "LEFT",
    "RIGHT",
    "INNER",
    "OUTER",
    "ON",
]
_HELPER_PREFIX_RE = re.compile(r"(?<!\S)(:[A-Za-z_]*)$")
_IDENT_PREFIX_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_$]*)$")
_QUOTED_PREFIX_RE = re.compile(r'("(?:""|[^"])*)$')
_SIMPLE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


@dataclass(slots=True)
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[tuple[Any, ...]]
    elapsed_ms: float
    total_rows: int
    truncated: bool


@dataclass(slots=True)
class EngineResponse:
    status: ResultStatus
    message: str
    result: QueryResult | None = None
    generated_sql: str | None = None
    should_exit: bool = False
    load_query: str | None = None
    clear_editor: bool = False


@dataclass(slots=True)
class FileReader:
    function_name: str
    args: str


def _detect_reader(file_path: Path) -> FileReader:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return FileReader(function_name="read_csv_auto", args="")
    if suffix == ".tsv":
        return FileReader(function_name="read_csv_auto", args=", delim='\\t'")
    if suffix in {".parquet", ".pq"}:
        return FileReader(function_name="read_parquet", args="")
    raise typer.BadParameter("Only .csv, .tsv, and .parquet/.pq files are supported.")


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _is_simple_ident(name: str) -> bool:
    return bool(_SIMPLE_IDENT_RE.fullmatch(name))


def _split_pipe_sections(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("|") if part.strip()]


def _parse_optional_positive_int(raw: str) -> int | None:
    lowered = raw.strip().lower()
    if lowered in {"off", "none"}:
        return None
    try:
        return max(1, int(lowered))
    except ValueError:
        return None


def _format_scalar(value: Any, max_chars: int | None = None) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    if max_chars is None or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return f"{text[: max_chars - 3]}..."


def _is_numeric_type(type_name: str) -> bool:
    upper = type_name.upper()
    return any(marker in upper for marker in ("INT", "DOUBLE", "FLOAT", "DECIMAL", "REAL", "NUMERIC"))


class SqlExplorerEngine:
    def __init__(
        self,
        data_path: Path,
        table_name: str,
        database: str,
        default_limit: int,
        max_rows_display: int,
        max_value_chars: int,
    ) -> None:
        self.data_path = data_path
        self.table_name = table_name.replace('"', "")
        self.database = database
        self.default_limit = max(1, default_limit)
        self.max_rows_display = max(1, max_rows_display)
        self.max_value_chars = max(8, max_value_chars)

        self.conn = duckdb.connect(database=database)
        self.executed_sql: list[str] = []
        self.last_sql = self.default_query
        self.last_result_sql: str | None = None

        reader = _detect_reader(self.data_path)
        source_sql = f"{reader.function_name}({_sql_literal(str(self.data_path))}{reader.args})"
        self.conn.execute(f'DROP VIEW IF EXISTS "{self.table_name}"')
        self.conn.execute(f'CREATE VIEW "{self.table_name}" AS SELECT * FROM {source_sql}')

        self._schema_rows: list[tuple[Any, ...]] = []
        self.columns: list[str] = []
        self.column_types: dict[str, str] = {}
        self.column_lookup: dict[str, str] = {}
        self.refresh_schema()

    @property
    def default_query(self) -> str:
        return f'SELECT * FROM "{self.table_name}" LIMIT {self.default_limit}'

    def close(self) -> None:
        self.conn.close()

    def refresh_schema(self) -> None:
        schema_rows = self.conn.execute(f'DESCRIBE "{self.table_name}"').fetchall()
        self._schema_rows = [tuple(row) for row in schema_rows]
        self.columns = [str(row[0]) for row in self._schema_rows]
        self.column_types = {str(row[0]): str(row[1]) for row in self._schema_rows}
        self.column_lookup = {col.lower(): col for col in self.columns}

    def row_count(self) -> int:
        out = self.conn.execute(f'SELECT COUNT(*) FROM "{self.table_name}"').fetchone()
        if out is None:
            return 0
        return int(out[0])

    def schema_preview(self, max_columns: int = 24) -> str:
        rows = self.row_count()
        head = [
            "Data Explorer",
            f"file: {self.data_path}",
            f"table: {self.table_name}",
            f"rows: {rows:,}",
            f"columns: {len(self.columns)}",
            "",
            "Schema",
        ]
        for name in self.columns[:max_columns]:
            head.append(f"- {name}: {self.column_types[name]}")
        if len(self.columns) > max_columns:
            head.append(f"... +{len(self.columns) - max_columns} more columns")
        head.extend(
            [
                "",
                "Shortcuts",
                "Ctrl+Enter run query",
                "Ctrl+J sample query",
                "Ctrl+K clear editor",
                "Ctrl+H help",
                "Ctrl+Q quit",
                "",
                "Helper Commands",
                ":sample [n]",
                ":filter <cond>",
                ":sort <exprs>",
                ":group cols | aggs [| having]",
                ":agg aggs [| where]",
                ":top <col> [n]",
                ":profile <col>",
                ":describe",
                ":history [n]",
                ":rerun <n>",
                ":schema  :last  :save <path>",
                ":rows <n> :values <n> :limit <n>",
                ":clear  :exit",
            ]
        )
        return "\n".join(head)

    def help_text(self) -> str:
        lines = [
            "Run standard SQL directly. Helper commands:",
            ":help",
            ":schema",
            ":sample [n]",
            ":filter <where condition>",
            ":sort <order expressions>",
            ":group <group cols> | <aggregates> [| having]",
            ":agg <aggregates> [| where]",
            ":top <column> [n]",
            ":profile <column>",
            ":describe",
            ":history [n]",
            ":rerun <history_index>",
            ":rows <n>",
            ":values <n>",
            ":limit <n>",
            ":save <path.csv|path.parquet|path.json>",
            ":last",
            ":clear",
            ":exit / :quit",
            "",
            f"settings: limit={self.default_limit}, rows={self.max_rows_display}, values={self.max_value_chars}",
        ]
        return "\n".join(lines)

    def _resolve_column(self, raw_column: str) -> str | None:
        candidate = raw_column.strip()
        if candidate.startswith('"') and candidate.endswith('"') and len(candidate) > 1:
            candidate = candidate[1:-1].replace('""', '"')
        return self.column_lookup.get(candidate.lower())

    def _display_rows(self, rows: list[tuple[Any, ...]]) -> tuple[list[tuple[Any, ...]], bool]:
        if len(rows) <= self.max_rows_display:
            return rows, False
        return rows[: self.max_rows_display], True

    def _table_response(self, columns: list[str], rows: list[tuple[Any, ...]], message: str) -> EngineResponse:
        shown, truncated = self._display_rows(rows)
        result = QueryResult(
            sql="",
            columns=columns,
            rows=shown,
            elapsed_ms=0.0,
            total_rows=len(rows),
            truncated=truncated,
        )
        return EngineResponse(status="ok", message=message, result=result)

    def run_sql(self, sql_text: str, remember: bool = True) -> EngineResponse:
        sql = sql_text.strip().rstrip(";")
        if not sql:
            return EngineResponse(status="info", message="Query is empty.")

        t0 = time.perf_counter()
        try:
            relation = self.conn.execute(sql)
            rows = relation.fetchall()
            columns = [str(item[0]) for item in relation.description] if relation.description else []
        except Exception as exc:  # noqa: BLE001
            return EngineResponse(status="error", message=str(exc))

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.last_sql = sql
        if remember:
            self.executed_sql.append(sql)

        if not columns:
            return EngineResponse(status="ok", message=f"Statement executed in {elapsed_ms:.1f} ms")

        shown, truncated = self._display_rows(rows)
        self.last_result_sql = sql
        result = QueryResult(
            sql=sql,
            columns=columns,
            rows=shown,
            elapsed_ms=elapsed_ms,
            total_rows=len(rows),
            truncated=truncated,
        )
        message = f"{len(shown):,}/{len(rows):,} rows shown in {elapsed_ms:.1f} ms"
        if truncated:
            message += f" (row display limit={self.max_rows_display})"
        return EngineResponse(status="ok", message=message, result=result)

    def run_input(self, raw_input: str) -> EngineResponse:
        text = raw_input.strip()
        if not text:
            return EngineResponse(status="info", message="Type SQL or :help.")
        if text.startswith(":"):
            return self._run_command(text)
        return self.run_sql(text)

    def _run_command(self, command: str) -> EngineResponse:
        stripped = command.strip()
        if stripped in {":exit", ":quit"}:
            return EngineResponse(status="info", message="Exiting SQL explorer.", should_exit=True)
        if stripped == ":help":
            return EngineResponse(status="info", message=self.help_text())
        if stripped == ":schema":
            rows = [(str(r[0]), str(r[1]), str(r[2])) for r in self._schema_rows]
            return self._table_response(["column", "type", "nullable"], rows, "Schema")
        if stripped == ":clear":
            return EngineResponse(status="info", message="Editor cleared.", clear_editor=True)
        if stripped == ":last":
            return EngineResponse(status="info", message="Loaded last SQL in editor.", load_query=self.last_sql)
        if stripped == ":describe":
            return self._describe_dataset()

        if stripped.startswith(":history"):
            parts = stripped.split()
            count = 20
            if len(parts) == 2:
                try:
                    count = max(1, int(parts[1]))
                except ValueError:
                    return EngineResponse(status="error", message="Usage: :history [n]")
            history = self.executed_sql[-count:]
            start_idx = max(1, len(self.executed_sql) - len(history) + 1)
            rows = [(idx, sql) for idx, sql in enumerate(history, start=start_idx)]
            return self._table_response(["#", "sql"], rows, f"History ({len(history)} queries)")

        if stripped.startswith(":rerun"):
            parts = stripped.split()
            if len(parts) != 2:
                return EngineResponse(status="error", message="Usage: :rerun <n>")
            try:
                idx = int(parts[1])
            except ValueError:
                return EngineResponse(status="error", message=":rerun expects an integer index")
            if idx < 1 or idx > len(self.executed_sql):
                return EngineResponse(status="error", message="History index out of range")
            sql = self.executed_sql[idx - 1]
            out = self.run_sql(sql)
            out.generated_sql = sql
            return out

        if stripped.startswith(":rows"):
            payload = stripped.removeprefix(":rows").strip()
            parsed = _parse_optional_positive_int(payload)
            if parsed is None:
                return EngineResponse(status="error", message="Usage: :rows <n>")
            self.max_rows_display = parsed
            return EngineResponse(status="ok", message=f"Row display limit set to {self.max_rows_display}")

        if stripped.startswith(":values"):
            payload = stripped.removeprefix(":values").strip()
            parsed = _parse_optional_positive_int(payload)
            if parsed is None:
                return EngineResponse(status="error", message="Usage: :values <n>")
            self.max_value_chars = parsed
            return EngineResponse(status="ok", message=f"Value display limit set to {self.max_value_chars}")

        if stripped.startswith(":limit"):
            payload = stripped.removeprefix(":limit").strip()
            parsed = _parse_optional_positive_int(payload)
            if parsed is None:
                return EngineResponse(status="error", message="Usage: :limit <n>")
            self.default_limit = parsed
            return EngineResponse(status="ok", message=f"Default helper query limit set to {self.default_limit}")

        if stripped.startswith(":save"):
            payload = stripped.removeprefix(":save").strip()
            if not payload:
                return EngineResponse(status="error", message="Usage: :save <path>")
            return self._save_last_result(payload)

        if stripped.startswith(":profile"):
            payload = stripped.removeprefix(":profile").strip()
            if not payload:
                return EngineResponse(status="error", message="Usage: :profile <column>")
            return self._profile_column(payload)

        generated_sql = self._helper_command_to_sql(stripped)
        if generated_sql is None:
            return EngineResponse(status="error", message=f"Unknown command: {stripped}. Use :help")

        out = self.run_sql(generated_sql)
        out.generated_sql = generated_sql
        return out

    def _helper_command_to_sql(self, command: str) -> str | None:
        if command.startswith(":sample"):
            parts = command.split()
            sample_n = self.default_limit
            if len(parts) == 2:
                try:
                    sample_n = max(1, int(parts[1]))
                except ValueError:
                    return None
            return f'SELECT * FROM "{self.table_name}" LIMIT {sample_n}'

        if command.startswith(":filter"):
            cond = command.removeprefix(":filter").strip()
            if not cond:
                return None
            return f'SELECT * FROM "{self.table_name}" WHERE {cond} LIMIT {self.default_limit}'

        if command.startswith(":sort"):
            expr = command.removeprefix(":sort").strip()
            if not expr:
                return None
            return f'SELECT * FROM "{self.table_name}" ORDER BY {expr} LIMIT {self.default_limit}'

        if command.startswith(":group"):
            payload = command.removeprefix(":group").strip()
            parts = _split_pipe_sections(payload)
            if len(parts) < 2:
                return None
            group_cols = parts[0]
            aggs = parts[1]
            having = parts[2] if len(parts) > 2 else ""
            sql = f'SELECT {group_cols}, {aggs} FROM "{self.table_name}" GROUP BY {group_cols}'
            if having:
                sql += f" HAVING {having}"
            sql += f" ORDER BY {group_cols}"
            return sql

        if command.startswith(":agg"):
            payload = command.removeprefix(":agg").strip()
            parts = _split_pipe_sections(payload)
            if not parts:
                return None
            aggs = parts[0]
            where = parts[1] if len(parts) > 1 else ""
            sql = f'SELECT {aggs} FROM "{self.table_name}"'
            if where:
                sql += f" WHERE {where}"
            return sql

        if command.startswith(":top"):
            parts = command.split()
            if len(parts) < 2 or len(parts) > 3:
                return None
            resolved = self._resolve_column(parts[1])
            if resolved is None:
                return None
            top_n = 10
            if len(parts) == 3:
                try:
                    top_n = max(1, int(parts[2]))
                except ValueError:
                    return None
            qcol = _quote_ident(resolved)
            return (
                f'SELECT {qcol} AS value, COUNT(*) AS count FROM "{self.table_name}" '
                f"GROUP BY {qcol} ORDER BY count DESC, value LIMIT {top_n}"
            )

        return None

    def _describe_dataset(self) -> EngineResponse:
        total_rows = self.row_count()
        total_columns = len(self.columns)
        column_rows: list[tuple[Any, ...]] = []
        for column in self.columns:
            qcol = _quote_ident(column)
            out = self.conn.execute(
                f'''SELECT
                    COUNT(*) AS rows,
                    COUNT({qcol}) AS non_null,
                    COUNT(DISTINCT {qcol}) AS distinct_count
                FROM "{self.table_name}"'''
            ).fetchone()
            if out is None:
                continue
            rows = int(out[0])
            non_null = int(out[1])
            distinct_count = int(out[2])
            nulls = rows - non_null
            null_pct = (100.0 * nulls / rows) if rows else 0.0
            column_rows.append((column, self.column_types[column], distinct_count, nulls, f"{null_pct:.2f}%"))

        message = f"Dataset: {total_rows:,} rows x {total_columns} columns"
        return self._table_response(["column", "type", "distinct", "nulls", "null_%"], column_rows, message)

    def _profile_column(self, raw_column: str) -> EngineResponse:
        column = self._resolve_column(raw_column)
        if column is None:
            return EngineResponse(status="error", message=f"Unknown column: {raw_column}")

        qcol = _quote_ident(column)
        out = self.conn.execute(
            f'''SELECT
                COUNT(*) AS rows,
                COUNT(DISTINCT {qcol}) AS distinct_count,
                SUM(CASE WHEN {qcol} IS NULL THEN 1 ELSE 0 END) AS null_count,
                MIN({qcol}) AS min_value,
                MAX({qcol}) AS max_value
            FROM "{self.table_name}"'''
        ).fetchone()
        if out is None:
            return EngineResponse(status="error", message=f"Failed to profile column: {column}")

        metric_rows: list[tuple[Any, ...]] = [
            ("column", column),
            ("type", self.column_types[column]),
            ("rows", int(out[0])),
            ("distinct", int(out[1])),
            ("nulls", int(out[2])),
            ("min", _format_scalar(out[3])),
            ("max", _format_scalar(out[4])),
        ]

        if _is_numeric_type(self.column_types[column]):
            quantiles = self.conn.execute(
                f'''SELECT
                    QUANTILE_CONT({qcol}, 0.25),
                    QUANTILE_CONT({qcol}, 0.50),
                    QUANTILE_CONT({qcol}, 0.75)
                FROM "{self.table_name}"
                WHERE {qcol} IS NOT NULL'''
            ).fetchone()
            if quantiles is not None:
                metric_rows.append(("p25", _format_scalar(quantiles[0])))
                metric_rows.append(("p50", _format_scalar(quantiles[1])))
                metric_rows.append(("p75", _format_scalar(quantiles[2])))

        return self._table_response(["metric", "value"], metric_rows, f"Profile for {column}")

    def _save_last_result(self, path_arg: str) -> EngineResponse:
        if self.last_result_sql is None:
            return EngineResponse(status="error", message="No query result to save yet")

        out_path = Path(path_arg).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = out_path.suffix.lower()

        try:
            if suffix == ".csv":
                self.conn.execute(
                    f"COPY ({self.last_result_sql}) TO {_sql_literal(str(out_path))} (HEADER, DELIMITER ',')"
                )
            elif suffix in {".parquet", ".pq"}:
                self.conn.execute(f"COPY ({self.last_result_sql}) TO {_sql_literal(str(out_path))} (FORMAT PARQUET)")
            elif suffix == ".json":
                relation = self.conn.execute(self.last_result_sql)
                rows = relation.fetchall()
                columns = [str(item[0]) for item in relation.description] if relation.description else []
                records = [dict(zip(columns, row, strict=False)) for row in rows]
                out_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
            else:
                return EngineResponse(status="error", message="Unsupported extension. Use .csv, .parquet/.pq, or .json")
        except Exception as exc:  # noqa: BLE001
            return EngineResponse(status="error", message=f"Save failed: {exc}")

        return EngineResponse(status="ok", message=f"Saved result to {out_path}")

    def completion_tokens(self) -> list[str]:
        raw_tokens = [*HELPER_COMMANDS, *SQL_KEYWORDS, self.table_name, *self.columns]
        raw_tokens.extend(_quote_ident(col) for col in self.columns if not _is_simple_ident(col))
        seen: set[str] = set()
        tokens: list[str] = []
        for token in raw_tokens:
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            tokens.append(token)
        return tokens


class SqlQueryEditor(TextArea):
    def __init__(self, text: str, token_provider: Callable[[], list[str]], **kwargs: Any) -> None:
        super().__init__(text, language="sql", tab_behavior="indent", soft_wrap=False, **kwargs)
        self._token_provider = token_provider
        self.indent_width = 4

    async def _on_key(self, event: Any) -> None:
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            if self.suggestion:
                self.insert(self.suggestion)
            else:
                self.insert(" " * self._find_columns_to_next_tab_stop())
            return
        await super()._on_key(event)

    def update_suggestion(self) -> None:
        row, col = self.cursor_location
        left_text = self.document[row][:col]
        prefix_match = (
            _HELPER_PREFIX_RE.search(left_text)
            or _QUOTED_PREFIX_RE.search(left_text)
            or _IDENT_PREFIX_RE.search(left_text)
        )
        if prefix_match is None:
            self.suggestion = ""
            return

        prefix = prefix_match.group(1)
        prefix_lower = prefix.lower()
        for token in self._token_provider():
            if not token.lower().startswith(prefix_lower):
                continue
            candidate = token
            if token.isupper() and prefix.islower():
                candidate = token.lower()
            elif token.islower() and prefix.isupper():
                candidate = token.upper()
            if candidate.lower() == prefix_lower:
                continue
            self.suggestion = candidate[len(prefix) :]
            return
        self.suggestion = ""


class SqlExplorerTui(App[None]):
    TITLE = "my-project SQL Explorer"
    SUB_TITLE = "DuckDB + Textual"

    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    #sidebar {
        width: 38;
        border: round #4f9da6;
        padding: 1;
        background: #102025;
        color: #f0f4f8;
    }

    #workspace {
        width: 1fr;
        padding: 0 1;
    }

    .section-title {
        color: #9abed8;
        text-style: bold;
        margin-top: 1;
    }

    #query_editor {
        height: 10;
        border: round #4d7ea8;
    }

    #results_table {
        height: 1fr;
        border: round #5b8f67;
    }

    #activity_log {
        height: 11;
        border: round #b18b3d;
    }
    """

    BINDINGS = [
        Binding("ctrl+enter", "run_query", "Run"),
        Binding("ctrl+j", "load_sample", "Sample"),
        Binding("ctrl+k", "clear_editor", "Clear"),
        Binding("ctrl+e", "focus_editor", "Editor"),
        Binding("ctrl+r", "focus_results", "Results"),
        Binding("ctrl+h", "show_help", "Help"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, engine: SqlExplorerEngine) -> None:
        super().__init__()
        self.engine = engine

    def _results_table(self) -> DataTable[str]:
        return cast(DataTable[str], self.query_one("#results_table", DataTable))

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Static(self.engine.schema_preview(), id="sidebar_text")
            with Vertical(id="workspace"):
                yield Static("Query", classes="section-title")
                yield SqlQueryEditor(self.engine.default_query, self.engine.completion_tokens, id="query_editor")
                yield Static("Results", id="results_header", classes="section-title")
                yield DataTable(id="results_table")
                yield Static("Activity", classes="section-title")
                yield RichLog(id="activity_log", markup=True, highlight=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self._results_table()
        table.zebra_stripes = True
        self._log("Ready. Press Ctrl+Enter to run SQL, or Ctrl+H for command help.", "info")
        boot = self.engine.run_sql(self.engine.default_query, remember=False)
        self._apply_response(boot)

    def action_run_query(self) -> None:
        editor = self.query_one("#query_editor", TextArea)
        query = editor.text
        response = self.engine.run_input(query)
        self._apply_response(response)

    def action_load_sample(self) -> None:
        editor = self.query_one("#query_editor", TextArea)
        editor.text = self.engine.default_query
        editor.focus()
        self._log("Loaded sample query.", "info")

    def action_clear_editor(self) -> None:
        editor = self.query_one("#query_editor", TextArea)
        editor.text = ""
        editor.focus()

    def action_focus_editor(self) -> None:
        self.query_one("#query_editor", TextArea).focus()

    def action_focus_results(self) -> None:
        self._results_table().focus()

    def action_show_help(self) -> None:
        self._log(self.engine.help_text(), "info")

    def _apply_response(self, response: EngineResponse) -> None:
        if response.generated_sql:
            self._log(f"Generated SQL:\n{response.generated_sql}", "info")

        if response.result is not None:
            self._render_table(response.result)

        if response.message:
            self._log(response.message, response.status)

        if response.load_query is not None:
            editor = self.query_one("#query_editor", TextArea)
            editor.text = response.load_query
            editor.focus()

        if response.clear_editor:
            self.action_clear_editor()

        if response.should_exit:
            self.exit()

        sidebar = self.query_one("#sidebar_text", Static)
        sidebar.update(self.engine.schema_preview())

    def _render_table(self, result: QueryResult) -> None:
        table = self._results_table()
        table.clear(columns=True)
        if not result.columns:
            self.query_one("#results_header", Static).update("Results")
            return

        table.add_columns(*result.columns)
        for row in result.rows:
            table.add_row(*[_format_scalar(value, self.engine.max_value_chars) for value in row])

        header = f"Results ({len(result.rows):,}/{result.total_rows:,} rows, {result.elapsed_ms:.1f} ms)"
        if result.truncated:
            header += " [truncated]"
        self.query_one("#results_header", Static).update(header)

    def _log(self, message: str, status: ResultStatus) -> None:
        logger = self.query_one("#activity_log", RichLog)
        style_prefix = {
            "ok": "[green]",
            "info": "[cyan]",
            "error": "[red]",
        }[status]
        logger.write(f"{style_prefix}{message}[/]")


def _render_console_response(console: Console, response: EngineResponse, max_value_chars: int) -> int:
    if response.generated_sql:
        console.print(Panel(response.generated_sql, title="Generated SQL", border_style="magenta"))

    if response.result is not None:
        result = response.result
        table = Table(
            title=f"Result ({len(result.rows)}/{result.total_rows} rows, {result.elapsed_ms:.1f} ms)",
            box=box.SIMPLE,
        )
        for column in result.columns:
            table.add_column(column)
        for row in result.rows:
            table.add_row(*[_format_scalar(value, max_value_chars) for value in row])
        console.print(table)

    if response.message:
        border_style = "green"
        if response.status == "error":
            border_style = "red"
        elif response.status == "info":
            border_style = "cyan"
        console.print(Panel(response.message, border_style=border_style))

    return 1 if response.status == "error" else 0


@app.command()
def main(
    data: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        resolve_path=True,
        help="CSV, TSV, or Parquet file path.",
    ),
    table_name: str = typer.Option("data", "--table", "-t", help="Logical table/view name inside DuckDB."),
    limit: int = typer.Option(100, "--limit", "-l", min=1, help="Default helper query row limit."),
    max_rows: int = typer.Option(400, "--max-rows", min=1, help="Maximum rows displayed in the result grid."),
    max_value_chars: int = typer.Option(
        160,
        "--max-value-chars",
        min=8,
        help="Maximum characters displayed per cell.",
    ),
    database: str = typer.Option(
        ":memory:",
        "--db",
        help="DuckDB database path. Use :memory: for in-memory session.",
    ),
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
    no_ui: bool = typer.Option(False, "--no-ui", help="Run once in standard terminal output mode."),
) -> None:
    if execute and query_file:
        raise typer.BadParameter("Use either --execute or --file, not both.")

    file_path = data.expanduser().resolve()
    engine = SqlExplorerEngine(
        data_path=file_path,
        table_name=table_name,
        database=database,
        default_limit=limit,
        max_rows_display=max_rows,
        max_value_chars=max_value_chars,
    )

    try:
        non_interactive_sql = execute
        if query_file is not None:
            non_interactive_sql = query_file.read_text(encoding="utf-8").strip()

        if non_interactive_sql is not None:
            response = engine.run_input(non_interactive_sql)
            exit_code = _render_console_response(Console(), response, engine.max_value_chars)
            raise typer.Exit(code=exit_code)

        if no_ui:
            response = engine.run_sql(engine.default_query, remember=False)
            exit_code = _render_console_response(Console(), response, engine.max_value_chars)
            raise typer.Exit(code=exit_code)

        SqlExplorerTui(engine).run()
    finally:
        engine.close()


if __name__ == "__main__":
    app()
