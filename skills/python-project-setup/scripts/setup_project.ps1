<#
.SYNOPSIS
    Sets up a new Python project with uv and best practices.
.PARAMETER ProjectName
    Name of the project to create.
.PARAMETER PythonVersion
    Minimum Python version (default: 3.10).
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectName,
    
    [Parameter(Mandatory=$false)]
    [string]$PythonVersion = "3.10"
)

Write-Output "Setting up Python project: {0}" -f $ProjectName

# Create project directory
if (Test-Path $ProjectName) {
    Write-Warning "Directory {0} already exists!" -f $ProjectName
    exit 1
}

New-Item -ItemType Directory -Path $ProjectName | Out-Null
Set-Location $ProjectName

# Create directory structure
Write-Output "Creating directory structure..."
New-Item -ItemType Directory -Path "src" | Out-Null
New-Item -ItemType Directory -Path "tests" | Out-Null
New-Item -ItemType File -Path "src\__init__.py" | Out-Null
New-Item -ItemType File -Path "tests\__init__.py" | Out-Null

# Create pyproject.toml
Write-Output "Creating pyproject.toml..."
$pyprojectContent = @"
[project]
name = "$ProjectName"
version = "0.1.0"
requires-python = ">=$PythonVersion"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]
"@
Set-Content -Path "pyproject.toml" -Value $pyprojectContent

# Create .gitignore
Write-Output "Creating .gitignore..."
$gitignoreContent = @"
# Virtual environment
.venv/
venv/

# Python
__pycache__/
*.py[cod]
*`$py.class
*.so

# Testing
.pytest_cache/
.coverage
htmlcov/

# Linting
.ruff_cache/

# Distribution
dist/
build/
*.egg-info/
"@
Set-Content -Path ".gitignore" -Value $gitignoreContent

# Create README.md
Write-Output "Creating README.md..."
$readmeContent = @"
# $ProjectName

## Setup

1. Create virtual environment:
``````powershell
uv venv
``````

2. Activate virtual environment:
``````powershell
.\.venv\Scripts\Activate.ps1
``````

3. Install dependencies:
``````powershell
uv pip install -e ".[dev]"
``````

## Development

Run tests:
``````powershell
pytest
``````

Format code:
``````powershell
black .
``````

Lint code:
``````powershell
ruff check .
``````
"@
Set-Content -Path "README.md" -Value $readmeContent

# Create virtual environment
Write-Output "Creating virtual environment with uv..."
uv venv

Write-Output ""
Write-Output "Project setup complete!"
Write-Output ""
Write-Output "Next steps:"
Write-Output "1. cd {0}" -f $ProjectName
Write-Output "2. .\.venv\Scripts\Activate.ps1"
Write-Output "3. uv pip install -e `".[dev]`""
