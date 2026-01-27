# Extending the CLI

Create custom commands for your project.

---

## Overview

Extend Aksara's CLI with custom commands:

- **Project commands** — Specific to your project
- **Reusable commands** — Packaged for distribution
- **Management commands** — Admin tasks

---

## Quick Start

### Create a Command

```python
# myapp/commands/greet.py
from aksara.cli import Command, argument, option

class GreetCommand(Command):
    """Greet a user."""
    
    name = "greet"
    
    @argument("name", help="Name to greet")
    @option("--excited", "-e", is_flag=True, help="Add excitement")
    async def handle(self, name: str, excited: bool = False):
        greeting = f"Hello, {name}"
        if excited:
            greeting += "!"
        self.output(greeting)
```

### Register Command

```python
# myapp/__init__.py
from aksara.cli import register_command
from .commands.greet import GreetCommand

register_command(GreetCommand)
```

### Use Command

```bash
aksara greet World --excited
# Hello, World!
```

---

## Command Structure

### Basic Command

```python
from aksara.cli import Command

class MyCommand(Command):
    """Command description shown in --help."""
    
    name = "mycommand"  # Command name
    
    async def handle(self):
        """Command logic goes here."""
        self.output("Hello from my command!")
```

### With Arguments

```python
from aksara.cli import Command, argument

class ProcessCommand(Command):
    name = "process"
    
    @argument("file", help="File to process")
    @argument("output", help="Output location")
    async def handle(self, file: str, output: str):
        self.output(f"Processing {file} -> {output}")
```

### With Options

```python
from aksara.cli import Command, option

class ExportCommand(Command):
    name = "export"
    
    @option("--format", "-f", default="json", help="Output format")
    @option("--verbose", "-v", is_flag=True, help="Verbose output")
    @option("--limit", "-l", type=int, default=100, help="Max records")
    async def handle(self, format: str, verbose: bool, limit: int):
        if verbose:
            self.output(f"Exporting {limit} records as {format}")
```

### Combined

```python
from aksara.cli import Command, argument, option

class MigrateDataCommand(Command):
    name = "migrate-data"
    
    @argument("source", help="Source database")
    @argument("target", help="Target database")
    @option("--dry-run", is_flag=True, help="Preview only")
    @option("--batch-size", type=int, default=1000)
    async def handle(
        self,
        source: str,
        target: str,
        dry_run: bool,
        batch_size: int
    ):
        ...
```

---

## Arguments

### Required Arguments

```python
@argument("name", help="User name")
async def handle(self, name: str):
    ...
```

### Optional Arguments

```python
@argument("name", default="World", help="User name")
async def handle(self, name: str = "World"):
    ...
```

### Multiple Values

```python
@argument("files", nargs=-1, help="Files to process")
async def handle(self, files: tuple[str, ...]):
    for file in files:
        ...
```

### Type Validation

```python
@argument("count", type=int, help="Number of items")
async def handle(self, count: int):
    ...
```

---

## Options

### Flag Options

```python
@option("--verbose", "-v", is_flag=True)
async def handle(self, verbose: bool):
    if verbose:
        ...
```

### Value Options

```python
@option("--output", "-o", default="output.txt")
async def handle(self, output: str):
    ...
```

### Choice Options

```python
@option("--format", type=click.Choice(["json", "csv", "xml"]))
async def handle(self, format: str):
    ...
```

### Multiple Values

```python
@option("--tag", "-t", multiple=True)
async def handle(self, tag: tuple[str, ...]):
    for t in tag:
        ...
```

### Environment Variables

```python
@option("--api-key", envvar="API_KEY")
async def handle(self, api_key: str):
    ...
```

---

## Output

### Standard Output

```python
async def handle(self):
    self.output("Normal message")
    self.success("Success message")  # Green
    self.warning("Warning message")  # Yellow
    self.error("Error message")      # Red
```

### Formatted Output

```python
async def handle(self):
    # Table
    self.table(
        headers=["Name", "Email"],
        rows=[
            ["John", "john@example.com"],
            ["Jane", "jane@example.com"],
        ]
    )
    
    # JSON
    self.json({"status": "ok", "count": 42})
    
    # Progress bar
    with self.progress("Processing", total=100) as bar:
        for i in range(100):
            bar.update(1)
```

### Prompts

```python
async def handle(self):
    # Text input
    name = self.prompt("Enter your name")
    
    # Password
    password = self.prompt("Password", hide_input=True)
    
    # Confirmation
    if self.confirm("Are you sure?"):
        ...
    
    # Choice
    color = self.choice("Pick a color", ["red", "blue", "green"])
```

---

## Accessing Application

### Database Access

```python
from myapp.models import User

class ListUsersCommand(Command):
    name = "list-users"
    
    async def handle(self):
        users = await User.objects.all()
        
        rows = [[u.name, u.email] for u in users]
        self.table(["Name", "Email"], rows)
```

### Settings Access

```python
from aksara.conf import settings

class ShowConfigCommand(Command):
    name = "show-config"
    
    async def handle(self):
        self.output(f"Debug: {settings.DEBUG}")
        self.output(f"Database: {settings.DATABASE_URL}")
```

### App Context

```python
class MyCommand(Command):
    name = "mycommand"
    
    async def handle(self):
        # Access app instance
        app = self.app
        
        # Access registry
        models = self.registry.get_models()
```

---

## Command Groups

### Create a Group

```python
from aksara.cli import CommandGroup

class DataCommands(CommandGroup):
    """Data management commands."""
    
    name = "data"

class ExportCommand(Command):
    group = DataCommands
    name = "export"
    
    async def handle(self):
        ...

class ImportCommand(Command):
    group = DataCommands
    name = "import"
    
    async def handle(self):
        ...
```

Usage:
```bash
aksara data export
aksara data import
```

---

## Testing Commands

### Test Command Output

```python
from aksara.testing import CommandTestCase

class TestGreetCommand(CommandTestCase):
    async def test_greet(self):
        result = await self.invoke("greet", ["World"])
        
        assert result.exit_code == 0
        assert "Hello, World" in result.output
    
    async def test_greet_excited(self):
        result = await self.invoke("greet", ["World", "--excited"])
        
        assert "Hello, World!" in result.output
```

### Test with Mocks

```python
from unittest.mock import patch

class TestExportCommand(CommandTestCase):
    @patch("myapp.services.export_data")
    async def test_export(self, mock_export):
        mock_export.return_value = {"count": 100}
        
        result = await self.invoke("export", ["--format", "json"])
        
        assert result.exit_code == 0
        mock_export.assert_called_once()
```

---

## Distribution

### Package Commands

```python
# setup.py or pyproject.toml
[project.entry-points."aksara.commands"]
mycommand = "mypackage.commands:MyCommand"
```

### Auto-Discovery

Commands in `{app}/commands/` are auto-discovered:

```
myapp/
├── commands/
│   ├── __init__.py
│   ├── export.py      # ExportCommand
│   ├── import_.py     # ImportCommand
│   └── sync.py        # SyncCommand
```

---

## Examples

### Data Export Command

```python
from aksara.cli import Command, option
from myapp.models import User
import json

class ExportUsersCommand(Command):
    """Export users to file."""
    
    name = "export-users"
    
    @option("--output", "-o", default="users.json")
    @option("--format", "-f", type=click.Choice(["json", "csv"]))
    @option("--active-only", is_flag=True)
    async def handle(self, output: str, format: str, active_only: bool):
        query = User.objects
        if active_only:
            query = query.filter(is_active=True)
        
        users = await query.all()
        
        if format == "json":
            data = [{"id": str(u.id), "email": u.email} for u in users]
            with open(output, "w") as f:
                json.dump(data, f, indent=2)
        else:
            # CSV export
            ...
        
        self.success(f"Exported {len(users)} users to {output}")
```

### Database Cleanup Command

```python
from aksara.cli import Command, option
from datetime import datetime, timedelta
from myapp.models import Session

class CleanupSessionsCommand(Command):
    """Remove expired sessions."""
    
    name = "cleanup-sessions"
    
    @option("--days", "-d", type=int, default=30)
    @option("--dry-run", is_flag=True)
    async def handle(self, days: int, dry_run: bool):
        cutoff = datetime.now() - timedelta(days=days)
        
        expired = await Session.objects.filter(
            last_activity__lt=cutoff
        ).count()
        
        if dry_run:
            self.output(f"Would delete {expired} sessions")
        else:
            if self.confirm(f"Delete {expired} sessions?"):
                await Session.objects.filter(
                    last_activity__lt=cutoff
                ).delete()
                self.success(f"Deleted {expired} sessions")
```

### Sync Command

```python
from aksara.cli import Command, option

class SyncProductsCommand(Command):
    """Sync products from external API."""
    
    name = "sync-products"
    
    @option("--full", is_flag=True, help="Full sync")
    async def handle(self, full: bool):
        with self.progress("Syncing products") as bar:
            products = await fetch_products()
            bar.total = len(products)
            
            for product in products:
                await sync_product(product)
                bar.update(1)
        
        self.success("Sync complete")
```

---

## Related Documentation

- [CLI Overview](index.md)
- [Commands](commands.md)
- [Dev Tools](dev-tools.md)
