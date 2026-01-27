"""
Aksara Shell Utilities

Interactive shell helpers for async development.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")


def arun(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run an async coroutine synchronously in the shell.
    
    This is a convenience wrapper for asyncio.run() that works
    well in interactive environments like IPython and the standard
    Python REPL.
    
    Usage in Aksara shell:
        >>> from aksara.shell import arun
        >>> users = arun(User.objects.all())
        >>> user = arun(User.objects.get(id=1))
        >>> arun(user.delete())
    
    Args:
        coro: An async coroutine to execute
        
    Returns:
        The result of the coroutine
        
    Raises:
        RuntimeError: If called from within an async context
    """
    try:
        # Check if we're in an existing event loop
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(coro)
    
    # We're in an async context - try to use nest_asyncio if available
    try:
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except ImportError:
        # IPython/Jupyter have their own async support
        try:
            import IPython
            shell = IPython.get_ipython()
            if shell is not None and hasattr(shell, 'run_cell_async'):
                # Let IPython handle it
                return loop.run_until_complete(coro)
        except ImportError:
            pass
        
        raise RuntimeError(
            "Cannot run async code within an existing event loop. "
            "Either install nest_asyncio (`pip install nest_asyncio`) "
            "or use `await` directly in an async context."
        )


def load_models_from_apps(apps: list[str]) -> dict[str, type]:
    """
    Load all models from configured apps.
    
    Discovers models by importing {app}.models module for each app
    in the apps list.
    
    Args:
        apps: List of app names to import models from
        
    Returns:
        Dictionary mapping model names to model classes
    """
    from aksara.registry import ModelRegistry
    
    models_dict = {}
    
    # First, try to import models from each app
    for app in apps:
        try:
            # Import {app}.models to trigger model registration
            import importlib
            models_module = importlib.import_module(f"{app}.models")
        except ImportError:
            # App doesn't have a models module, skip
            pass
    
    # Now get all registered models
    # ModelRegistry.all() returns dict of name -> model class
    for name, model_cls in ModelRegistry.all().items():
        models_dict[name] = model_cls
    
    return models_dict


def build_shell_namespace(
    database_url: str | None = None,
    load_models: bool = True,
) -> dict[str, Any]:
    """
    Build a namespace dictionary for the interactive shell.
    
    Creates a namespace with commonly used Aksara imports and
    optionally connects to the database and loads models.
    
    Args:
        database_url: Database URL to connect to
        load_models: Whether to load and include models in namespace
        
    Returns:
        Dictionary namespace for the shell
    """
    from aksara import (
        Model, fields, Database, ModelRegistry,
        settings, configure, DoesNotExist, MultipleObjectsReturned,
    )
    
    namespace: dict[str, Any] = {
        # Core imports
        "Model": Model,
        "fields": fields,
        "Database": Database,
        "ModelRegistry": ModelRegistry,
        # Configuration
        "settings": settings,
        "configure": configure,
        # Exceptions
        "DoesNotExist": DoesNotExist,
        "MultipleObjectsReturned": MultipleObjectsReturned,
        # Async helper
        "arun": arun,
    }
    
    # Add database connection if URL provided
    if database_url:
        db = Database(database_url)
        namespace["db"] = db
    
    # Load models from configured apps
    if load_models:
        try:
            models = load_models_from_apps(settings.apps)
            namespace.update(models)
            namespace["_loaded_models"] = list(models.keys())
        except Exception:
            namespace["_loaded_models"] = []
    
    return namespace


def get_shell_banner(namespace: dict[str, Any]) -> str:
    """
    Generate a welcome banner for the Aksara shell.
    
    Args:
        namespace: The shell namespace (to show loaded models)
        
    Returns:
        Banner string
    """
    from aksara import __version__
    
    lines = [
        "",
        f"  \033[33m⚡\033[0m \033[1mAksara Shell\033[0m v{__version__}",
        "",
        "  Available objects:",
        "    • Model, fields, Database, ModelRegistry",
        "    • settings, configure",
        "    • arun() - run async code: arun(User.objects.all())",
    ]
    
    # Show database status
    if "db" in namespace:
        lines.append("    • db - Database connection")
    
    # Show loaded models
    loaded_models = namespace.get("_loaded_models", [])
    if loaded_models:
        model_list = ", ".join(sorted(loaded_models)[:5])
        if len(loaded_models) > 5:
            model_list += f", ... ({len(loaded_models)} total)"
        lines.append(f"    • Models: {model_list}")
    
    lines.extend([
        "",
        "  \033[90mTip: Use arun() to run async queries\033[0m",
        "  \033[90mExample: users = arun(User.objects.all())\033[0m",
        "",
    ])
    
    return "\n".join(lines)


def start_ipython_shell(namespace: dict[str, Any], banner: str) -> None:
    """
    Start an IPython shell with the given namespace.
    
    Args:
        namespace: Variables to inject into the shell
        banner: Welcome banner to display
        
    Raises:
        ImportError: If IPython is not installed
    """
    from IPython import start_ipython
    from IPython.terminal.prompts import Prompts, Token
    from traitlets.config import Config
    
    # Custom prompts for Aksara
    class AksaraPrompts(Prompts):
        def in_prompt_tokens(self, cli=None):
            return [(Token.Prompt, "aksara> ")]
        
        def out_prompt_tokens(self):
            return [(Token.OutPrompt, "")]
    
    # Configure IPython
    config = Config()
    config.TerminalInteractiveShell.prompts_class = AksaraPrompts
    config.TerminalInteractiveShell.banner1 = banner
    config.TerminalInteractiveShell.confirm_exit = False
    
    # Enable async support
    config.InteractiveShell.autoawait = True
    
    start_ipython(
        argv=[],
        user_ns=namespace,
        config=config,
    )


def start_standard_shell(namespace: dict[str, Any], banner: str) -> None:
    """
    Start a standard Python shell with the given namespace.
    
    Falls back to code.interact when IPython is not available.
    
    Args:
        namespace: Variables to inject into the shell
        banner: Welcome banner to display
    """
    import code
    import readline
    import rlcompleter
    
    # Enable tab completion
    readline.set_completer(rlcompleter.Completer(namespace).complete)
    readline.parse_and_bind("tab: complete")
    
    # Start interactive console
    console = code.InteractiveConsole(locals=namespace)
    console.interact(banner=banner, exitmsg="")


def run_shell(
    database_url: str | None = None,
    use_ipython: bool = True,
) -> None:
    """
    Run the Aksara interactive shell.
    
    Starts an interactive Python shell with Aksara imports pre-loaded,
    database connection ready, and async helpers available.
    
    Args:
        database_url: Database URL to connect to (optional)
        use_ipython: Whether to use IPython if available (default: True)
    """
    # Build the namespace
    namespace = build_shell_namespace(database_url=database_url)
    banner = get_shell_banner(namespace)
    
    # Try IPython first if enabled
    if use_ipython:
        try:
            start_ipython_shell(namespace, banner)
            return
        except ImportError:
            # IPython not installed, fall back to standard shell
            pass
    
    # Fall back to standard Python shell
    start_standard_shell(namespace, banner)


__all__ = [
    "arun",
    "load_models_from_apps",
    "build_shell_namespace",
    "get_shell_banner",
    "start_ipython_shell",
    "start_standard_shell",
    "run_shell",
]
