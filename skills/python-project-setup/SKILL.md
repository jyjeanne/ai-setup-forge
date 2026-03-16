---
name: python-project-setup
description: Sets up a new Python project with uv, virtual environment, and best practices for Windows 11. Triggers on "create Python project", "set up Python environment", "new Python app", "initialize Python repo", or questions about uv, pyproject.toml, virtual environments on Windows.
license: MIT - see LICENSE.txt
---

# Python Project Setup with uv

## Quick Setup (Recommended)

```powershell
.\scripts\setup_project.ps1 -ProjectName "my-project"
```

This creates a complete project with virtual environment, pyproject.toml, .gitignore, and README.

## Scripts Reference

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup_project.ps1` | Full automated setup | `.\scripts\setup_project.ps1 -ProjectName "name"` |
| `check_uv.py` | Install uv if missing | `python scripts/check_uv.py` |
| `create_pyproject.py` | Generate pyproject.toml | `python scripts/create_pyproject.py --name "name"` |

## Manual Setup

For step-by-step instructions, see `references/manual-setup.md`.

## Output Structure

```
project-name/
├── .venv/
├── src/__init__.py
├── tests/__init__.py
├── .gitignore
├── README.md
└── pyproject.toml
```

## Next Steps After Setup

```powershell
cd my-project
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
```
