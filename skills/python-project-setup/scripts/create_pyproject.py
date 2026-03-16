"""Generate a pyproject.toml file for a Python project."""
import argparse
from pathlib import Path

TEMPLATE = """\
[project]
name = "{name}"
version = "{version}"
requires-python = ">={python_version}"
description = "{description}"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]

[tool.black]
line-length = 88
target-version = ['py{python_short}']

[tool.ruff]
line-length = 88
target-version = "py{python_short}"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
"""

def create_pyproject(
    name: str,
    version: str = "0.1.0",
    python_version: str = "3.10",
    description: str = ""
) -> str:
    """Create pyproject.toml content."""
    python_short = python_version.replace(".", "")
    return TEMPLATE.format(
        name=name,
        version=version,
        python_version=python_version,
        description=description,
        python_short=python_short
    )

def main():
    parser = argparse.ArgumentParser(
        description="Generate pyproject.toml file"
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Project name"
    )
    parser.add_argument(
        "--version",
        default="0.1.0",
        help="Project version (default: 0.1.0)"
    )
    parser.add_argument(
        "--python-version",
        default="3.10",
        help="Minimum Python version (default: 3.10)"
    )
    parser.add_argument(
        "--description",
        default="",
        help="Project description"
    )
    parser.add_argument(
        "--output",
        default="pyproject.toml",
        help="Output file (default: pyproject.toml)"
    )
    
    args = parser.parse_args()
    
    content = create_pyproject(
        name=args.name,
        version=args.version,
        python_version=args.python_version,
        description=args.description
    )
    
    output_path = Path(args.output)
    if output_path.exists():
        print(f"{args.output} already exists!")
        return 1
    
    output_path.write_text(content)
    print(f"Created {args.output}")
    return 0

if __name__ == "__main__":
    exit(main())
