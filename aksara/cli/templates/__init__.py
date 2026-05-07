"""
Aksara Project Templates (v0.5.7)

Template packs for `aksara startproject --template <name>`.

Available templates:
- basic: Default minimal project (Post model)
- blog: Full blog with Post, Comment, moderation
- crm: Customer & Deal pipeline with forecasting
- multitenant: Tenant-scoped SaaS backend
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Dict, Optional

# Template metadata
TEMPLATES = {
    "basic": {
        "name": "basic",
        "description": "Default minimal project (Post model)",
        "source": None,  # Uses scaffold.py templates
    },
    "blog": {
        "name": "blog",
        "description": "Full blog with Post, Comment, moderation",
        "source": "blog",  # Copy from examples/blog
    },
    "crm": {
        "name": "crm",
        "description": "Customer & Deal pipeline with forecasting",
        "source": "crm",  # Copy from examples/crm
    },
    "multitenant": {
        "name": "multitenant",
        "description": "Tenant-scoped SaaS backend",
        "source": "multitenant",  # Copy from examples/multitenant
    },
}


def get_available_templates() -> Dict[str, dict]:
    """Return dictionary of available templates."""
    return TEMPLATES.copy()


def get_template_info(name: str) -> Optional[dict]:
    """Get info about a specific template."""
    return TEMPLATES.get(name)


def list_templates() -> str:
    """Return formatted string of available templates."""
    lines = ["Available templates:", ""]
    for name, info in TEMPLATES.items():
        marker = "(default)" if name == "basic" else ""
        lines.append(f"  {name:<12} {info['description']} {marker}")
    return "\n".join(lines)


def get_examples_path() -> Path:
    """Locate the examples directory.

    Two layouts are supported:
      - Wheel install: examples are bundled inside the package at aksara/_examples
      - Repo dev mode: examples live at <repo_root>/examples
    """
    aksara_path = Path(__file__).parent.parent.parent  # aksara/

    # 1. Bundled location (wheel install) — see pyproject.toml force-include
    bundled = aksara_path / "_examples"
    if bundled.exists():
        return bundled

    # 2. Repo dev mode — top-level examples/ next to the aksara/ package
    return aksara_path.parent / "examples"


def copy_template_project(
    template_name: str,
    project_name: str,
    base_path: Path,
) -> Dict[Path, str]:
    """
    Copy a template project to the target directory.
    
    Args:
        template_name: Name of the template (blog, crm, multitenant)
        project_name: Name of the new project
        base_path: Base path for the new project
        
    Returns:
        Dict of files created (path -> content)
    """
    template_info = TEMPLATES.get(template_name)
    if not template_info:
        raise ValueError(f"Unknown template: {template_name}")
    
    # Basic template uses the default scaffold
    if template_info["source"] is None:
        from aksara.cli.scaffold import create_project_scaffold
        return create_project_scaffold(project_name, base_path)
    
    # Copy from examples directory
    examples_path = get_examples_path()
    source_path = examples_path / template_info["source"]
    
    if not source_path.exists():
        raise FileNotFoundError(
            f"Template source not found: {source_path}\n"
            f"Make sure the examples/{template_info['source']} directory exists."
        )
    
    project_path = base_path / project_name
    files = {}
    
    # Walk the source directory and collect files
    for root, dirs, filenames in os.walk(source_path):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        
        rel_root = Path(root).relative_to(source_path)
        
        for filename in filenames:
            # Skip .pyc files
            if filename.endswith(".pyc"):
                continue
            
            source_file = Path(root) / filename
            
            # Calculate destination path
            if str(rel_root) == ".":
                dest_file = project_path / filename
            else:
                dest_file = project_path / rel_root / filename
            
            # Read content and apply substitutions
            try:
                with open(source_file, "r") as f:
                    content = f.read()
                
                # Replace template-specific names with project name
                content = apply_project_name_substitutions(
                    content, 
                    template_name, 
                    project_name
                )
                
                files[dest_file] = content
            except UnicodeDecodeError:
                # Binary file, skip
                pass
    
    return files


def apply_project_name_substitutions(
    content: str,
    template_name: str,
    project_name: str,
) -> str:
    """
    Apply project name substitutions to template content.
    
    Replaces:
    - Template-specific names (e.g., "Blog Example" -> "MyProject")
    - Module references (e.g., "examples.blog" -> "app")
    - Relative imports (e.g., "from . import X" -> "import X")
    """
    # Title substitutions
    title_map = {
        "blog": "Blog Example",
        "crm": "CRM Example",
        "multitenant": "Multitenant Example",
    }
    
    # Database URL substitutions
    db_map = {
        "blog": "aksara_blog",
        "crm": "aksara_crm",
        "multitenant": "aksara_multitenant",
    }
    
    if template_name in title_map:
        # Replace title
        content = content.replace(title_map[template_name], project_name)
        
        # Replace database name
        content = content.replace(db_map[template_name], project_name)
        
        # Replace module paths (examples.X -> app)
        content = content.replace(f"examples.{template_name}", "app")

    # Convert relative imports to absolute imports so the generated project
    # works as a standalone app (not a sub-package).
    # `from . import X [as Y]` -> `import X [as Y]`
    content = re.sub(r'^(\s*)from \. import ', r'\1import ', content, flags=re.MULTILINE)
    # `from .module import X` -> `from module import X`
    content = re.sub(r'^(\s*)from \.(\w)', r'\1from \2', content, flags=re.MULTILINE)
    
    return content
