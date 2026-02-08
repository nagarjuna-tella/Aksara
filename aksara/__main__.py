"""
Aksara CLI entry point for `python -m aksara` execution.

This allows running aksara commands via `python -m aksara` which ensures
the correct Python interpreter is used (helpful when dealing with venvs).
"""

from aksara.cli.main import main

if __name__ == "__main__":
    main()
