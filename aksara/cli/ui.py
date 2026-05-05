"""
CLI presentation helpers for the Aksara command line.

Provides a semantic UI facade with plain-text and Rich-backed renderers.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
import os
import sys
from typing import Any, Iterator, Literal

import click


OutputMode = Literal["auto", "plain", "rich"]


@dataclass(slots=True)
class CLIUIConfig:
    """Resolved runtime output settings for the CLI."""

    mode: OutputMode = "auto"
    quiet: bool = False
    no_color: bool = False
    force_color: bool = False
    unicode: bool = True
    is_tty: bool = False
    is_ci: bool = False


def _is_ci_environment(env: dict[str, str]) -> bool:
    """Return True when the process appears to be running in CI."""

    ci_keys = (
        "CI",
        "GITHUB_ACTIONS",
        "BUILDKITE",
        "TF_BUILD",
        "JENKINS_URL",
        "CIRCLECI",
    )
    return any(env.get(key) for key in ci_keys)


def resolve_ui_config(
    *,
    quiet: bool = False,
    plain: bool = False,
    no_color: bool = False,
    force_color: bool = False,
) -> CLIUIConfig:
    """Resolve CLI output settings from flags and environment variables."""

    env = os.environ
    term = env.get("TERM", "")
    mode_override = env.get("AKSARA_CLI_MODE", "auto").strip().lower() or "auto"

    if mode_override not in {"auto", "plain", "rich"}:
        mode_override = "auto"

    if plain:
        requested_mode: OutputMode = "plain"
    else:
        requested_mode = mode_override  # type: ignore[assignment]

    is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)()) and bool(
        getattr(sys.stderr, "isatty", lambda: False)()
    )
    is_ci = _is_ci_environment(env)
    no_color_enabled = no_color or bool(env.get("NO_COLOR"))
    force_color_enabled = force_color or bool(env.get("FORCE_COLOR"))
    unicode_enabled = term.lower() != "dumb"

    rich_allowed = (
        term.lower() != "dumb"
        and not no_color_enabled
        and (force_color_enabled or (is_tty and not is_ci))
    )
    resolved_mode: OutputMode = "rich" if rich_allowed else "plain"

    if quiet or requested_mode == "plain":
        resolved_mode = "plain"
    elif requested_mode == "rich" and (rich_allowed or force_color_enabled):
        resolved_mode = "rich"

    return CLIUIConfig(
        mode=resolved_mode,
        quiet=quiet,
        no_color=no_color_enabled,
        force_color=force_color_enabled,
        unicode=unicode_enabled and not plain,
        is_tty=is_tty,
        is_ci=is_ci,
    )


class _PlainProgress:
    """No-op progress updater for plain mode."""

    def advance(self, step: int = 1, description: str | None = None) -> None:
        """Advance the progress state."""

        return None


class PlainRenderer:
    """Plain-text renderer that avoids ANSI and motion."""

    def __init__(self, config: CLIUIConfig):
        self.config = config

    def line(self, message: str = "", *, err: bool = False, nl: bool = True) -> None:
        """Write a plain text line."""

        click.echo(message, err=err, nl=nl)

    @contextmanager
    def status(self, label: str, *, animate: bool = True) -> Iterator[None]:
        """Emit a static step line in plain mode."""

        if not self.config.quiet:
            self.line(f"  > {label}...")
        yield

    @contextmanager
    def progress(self, total: int, label: str) -> Iterator[_PlainProgress]:
        """Emit a static progress heading in plain mode."""

        if not self.config.quiet:
            self.line(f"  > {label} ({total} total)")
        yield _PlainProgress()

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        """Render a simple aligned table."""

        widths = [len(header) for header in headers]
        for row in rows:
            for index, value in enumerate(row):
                widths[index] = max(widths[index], len(str(value)))

        header_line = "  " + "  ".join(
            header.ljust(widths[index]) for index, header in enumerate(headers)
        )
        self.line(header_line)
        self.line("  " + "  ".join("-" * width for width in widths))
        for row in rows:
            self.line(
                "  "
                + "  ".join(
                    str(value).ljust(widths[index])
                    for index, value in enumerate(row)
                )
            )


class RichProgressUpdater:
    """Rich-backed progress updater."""

    def __init__(self, progress: Any, task_id: int):
        self._progress = progress
        self._task_id = task_id

    def advance(self, step: int = 1, description: str | None = None) -> None:
        """Advance the tracked progress task."""

        kwargs: dict[str, Any] = {"advance": step}
        if description is not None:
            kwargs["description"] = description
        self._progress.update(self._task_id, **kwargs)


class RichRenderer:
    """Rich-backed renderer for interactive terminals."""

    def __init__(self, config: CLIUIConfig):
        from rich.console import Console

        self.config = config
        self.console = Console(
            force_terminal=config.force_color,
            no_color=config.no_color,
            emoji=config.unicode,
            highlight=False,
            soft_wrap=True,
        )

    def line(self, message: str = "", *, err: bool = False, nl: bool = True) -> None:
        """Write a styled line using Click for compatibility."""

        click.echo(message, err=err, nl=nl)

    @contextmanager
    def status(self, label: str, *, animate: bool = True) -> Iterator[None]:
        """Show a Rich spinner while the enclosed operation runs."""

        if self.config.quiet or not animate:
            yield
            return

        with self.console.status(label, spinner="dots"):
            yield

    @contextmanager
    def progress(self, total: int, label: str) -> Iterator[RichProgressUpdater]:
        """Render a Rich progress bar for countable work."""

        if self.config.quiet:
            yield RichProgressUpdater(_NullProgressShim(), 0)
            return

        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        )

        with progress:
            task_id = progress.add_task(label, total=total)
            yield RichProgressUpdater(progress, task_id)

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        """Render a Rich table."""

        from rich import box
        from rich.table import Table

        table = Table(box=box.SIMPLE_HEAD)
        for header in headers:
            table.add_column(header)
        for row in rows:
            table.add_row(*[str(value) for value in row])
        self.console.print(table)


class _NullProgressShim:
    """Fallback object that matches the Rich Progress update API."""

    def update(self, task_id: int, **kwargs: Any) -> None:
        """Ignore updates."""

        return None


class CliUI:
    """Semantic CLI UI facade used by command handlers."""

    def __init__(self, config: CLIUIConfig, renderer: PlainRenderer | RichRenderer):
        self.config = config
        self.renderer = renderer

    @property
    def is_rich(self) -> bool:
        """Return True when Rich rendering is active."""

        return self.config.mode == "rich"

    def blank(self) -> None:
        """Emit a blank line unless quiet mode is enabled."""

        if self.config.quiet:
            return
        self.renderer.line("")

    def text(
        self,
        message: str = "",
        *,
        err: bool = False,
        nl: bool = True,
        quiet_sensitive: bool = True,
    ) -> None:
        """Emit a raw line through the active renderer."""

        if self.config.quiet and quiet_sensitive and not err:
            return
        self.renderer.line(message, err=err, nl=nl)

    def separator(self, width: int = 40) -> None:
        """Render a low-emphasis separator line."""

        if self.config.quiet:
            return
        token = "─" if self.config.unicode else "-"
        line = token * width
        if self.is_rich and not self.config.no_color:
            self.renderer.line(click.style(f"  {line}", fg="bright_black"))
            return
        self.renderer.line(f"  {line}")

    def aksara_banner(self, version: str, subtitle: str | None = None) -> None:
        """Render the common Aksara banner."""

        if self.config.quiet:
            return

        self.blank()
        symbol = self._symbol("brand")
        if self.is_rich and not self.config.no_color:
            brand = f"{click.style(symbol, fg='yellow')} {click.style('Aksara', bold=True)} {version}"
        else:
            prefix = f"{symbol} " if symbol else ""
            brand = f"{prefix}Aksara {version}".strip()
        self.renderer.line(f"  {brand}")
        if subtitle:
            line = click.style(f"  {subtitle}", fg="bright_black") if self.is_rich and not self.config.no_color else f"  {subtitle}"
            self.renderer.line(line)
        self.blank()

    def section(self, title: str) -> None:
        """Render a section title."""

        if self.config.quiet:
            return
        text = click.style(title, bold=True) if self.is_rich and not self.config.no_color else title
        self.renderer.line(f"  {text}")

    def info(self, message: str) -> None:
        """Render an informational line."""

        self._emit("info", message)

    def success(self, message: str) -> None:
        """Render a success line."""

        self._emit("success", message)

    def warning(self, message: str) -> None:
        """Render a warning line."""

        self._emit("warning", message)

    def error(self, message: str, *, err: bool = True) -> None:
        """Render an error line."""

        self._emit("error", message, err=err)

    def dim(self, message: str) -> None:
        """Render a low-emphasis line."""

        if self.config.quiet:
            return
        if self.is_rich and not self.config.no_color:
            self.renderer.line(click.style(f"  {message}", fg="bright_black"))
            return
        self.renderer.line(f"  {message}")

    def bullet(self, message: str) -> None:
        """Render a bullet line."""

        if self.config.quiet:
            return
        self.renderer.line(f"  - {message}")

    def command(self, message: str) -> None:
        """Render a command suggestion line."""

        if self.config.quiet:
            return
        if self.is_rich and not self.config.no_color:
            self.renderer.line(f"    {click.style(message, fg='cyan')}")
            return
        self.renderer.line(f"    {message}")

    def key_value(self, label: str, value: str) -> None:
        """Render a simple key/value line."""

        if self.config.quiet:
            return
        formatted_label = label
        if self.is_rich and not self.config.no_color:
            formatted_label = click.style(label, fg="cyan")
        self.renderer.line(f"  {formatted_label:<14} {value}")

    def next_steps(self, lines: list[str], *, title: str = "Next steps") -> None:
        """Render a next-steps block."""

        if self.config.quiet:
            return
        self.blank()
        self.section(title)
        self.blank()
        for line in lines:
            self.command(line)

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        """Render a table using the active renderer."""

        if self.config.quiet:
            return
        self.renderer.table(headers, rows)

    @contextmanager
    def status(self, label: str, *, animate: bool = True) -> Iterator[None]:
        """Render a long-running status block."""

        with self.renderer.status(label, animate=animate):
            yield

    def progress(self, total: int, label: str):
        """Return a progress context manager for countable work."""

        return self.renderer.progress(total, label)

    def print_json(self, payload: Any) -> None:
        """Emit JSON output to stdout without additional formatting."""

        import json

        click.echo(json.dumps(payload, indent=2, default=str))

    def _emit(self, kind: str, message: str, *, err: bool = False) -> None:
        """Render a message with a semantic status prefix."""

        if self.config.quiet and kind not in {"error", "warning"}:
            return

        symbol = self._symbol(kind)
        if self.is_rich and not self.config.no_color:
            color = self._color(kind)
            prefix = click.style(symbol, fg=color) if symbol else ""
        else:
            prefix = symbol

        spacer = " " if prefix else ""
        self.renderer.line(f"  {prefix}{spacer}{message}", err=err)

    def _color(self, kind: str) -> str:
        """Return the color name for a semantic output kind."""

        colors = {
            "brand": "yellow",
            "info": "cyan",
            "success": "green",
            "warning": "yellow",
            "error": "red",
        }
        return colors.get(kind, "white")

    def _symbol(self, kind: str) -> str:
        """Return the preferred symbol for a semantic output kind."""

        if not self.config.unicode or self.config.mode == "plain":
            return {
                "brand": "",
                "info": "i",
                "success": "OK",
                "warning": "!",
                "error": "X",
            }.get(kind, "")

        return {
            "brand": "⚡",
            "info": "ℹ",
            "success": "✓",
            "warning": "⚠",
            "error": "✗",
        }.get(kind, "")


def build_ui(config: CLIUIConfig) -> CliUI:
    """Create the appropriate UI facade for the current environment."""

    if config.mode == "rich":
        try:
            return CliUI(config, RichRenderer(config))
        except Exception:
            fallback = replace(config, mode="plain")
            return CliUI(fallback, PlainRenderer(fallback))
    return CliUI(config, PlainRenderer(config))


def get_ui() -> CliUI:
    """Return the UI object stored in the active Click context when available."""

    ctx = click.get_current_context(silent=True)
    if ctx is not None and isinstance(ctx.obj, dict) and "ui" in ctx.obj:
        return ctx.obj["ui"]
    return build_ui(resolve_ui_config())


__all__ = [
    "CLIUIConfig",
    "CliUI",
    "OutputMode",
    "build_ui",
    "get_ui",
    "resolve_ui_config",
]