# Manual Setup Guide

Step-by-step instructions for setting up a Python project with uv on Windows 11.

## 1. Check and Install uv

Use the provided script:
```powershell
python scripts/check_uv.py
```

Or manually:
```powershell
pip install uv
```

## 2. Create Virtual Environment

```powershell
uv venv
```

## 3. Activate Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If you get an execution policy error:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 4. Create pyproject.toml

Use the template script:
```powershell
python scripts/create_pyproject.py --name "your-project-name" --python-version "3.10"
```

Or manually create:
```toml
[project]
name = "your-project-name"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]
```

## 5. Install Dependencies

```powershell
uv pip install -e ".[dev]"
```

## 6. Create Directory Structure

```
project-name/
├── .venv/          # Virtual environment (don't commit)
├── src/            # Source code
│   └── __init__.py
├── tests/          # Test files
│   └── __init__.py
├── .gitignore
├── README.md
└── pyproject.toml
```

## 7. Configure .gitignore

Always exclude:
```
.venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/
```
