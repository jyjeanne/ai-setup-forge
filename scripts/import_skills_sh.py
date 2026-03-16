"""Import skills from skills.sh popular repos using npx skills add.

Downloads skills to a temp agent dir, then copies valid ones into skills/.
Skips skills that already exist in our bundled collection.

Usage:
    python scripts/import_skills_sh.py
    python scripts/import_skills_sh.py --dry-run
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import frontmatter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
REGISTRY_MAP = PROJECT_ROOT / "skills-registry" / "bundled_skills_map.json"

# Top repos from skills.sh (owner/repo or owner/repo@skill)
SOURCES = [
    "vercel-labs/agent-skills",
    "anthropics/skills",
    "github/awesome-copilot",
    "wshobson/agents",
    "supercent-io/skills-template",
    "neondatabase/agent-skills",
    "google-labs-code/stitch-skills",
]

# Category inference from skill name/description keywords
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "web": ["react", "next", "css", "html", "frontend", "web", "tailwind", "vue", "svelte", "vercel", "browser", "ui"],
    "testing": ["test", "jest", "playwright", "selenium", "cypress", "vitest", "spec"],
    "devops": ["docker", "kubernetes", "ci", "cd", "deploy", "terraform", "aws", "azure", "gcp", "cloud", "helm", "devops"],
    "security": ["security", "auth", "owasp", "xss", "csrf", "jwt", "encrypt", "vulnerability"],
    "architecture": ["architecture", "design-pattern", "microservice", "monolith", "ddd", "clean-architecture", "solid"],
    "database": ["database", "sql", "postgres", "mongo", "redis", "orm", "prisma", "neon", "supabase"],
    "ai-engineering": ["llm", "ai", "ml", "model", "prompt", "rag", "embedding", "openai", "anthropic"],
    "methodology": ["agile", "scrum", "code-review", "git", "workflow", "best-practice"],
    "documentation": ["doc", "readme", "changelog", "api-doc"],
    "performance": ["performance", "optimization", "bundle", "lighthouse", "cache"],
    "design": ["design", "ux", "accessibility", "a11y"],
    "mobile": ["mobile", "react-native", "ios", "android", "expo", "swift"],
}


def infer_categories(name: str, description: str) -> list[str]:
    """Infer categories from skill name and description."""
    text = f"{name} {description}".lower()
    cats = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            cats.append(cat)
    return cats[:3] if cats else ["web"]  # default to web


def infer_tags(name: str, description: str) -> list[str]:
    """Infer tags from skill name."""
    tags = []
    parts = name.split("-")
    # Use first 2-3 meaningful parts as tags
    for part in parts[:4]:
        if len(part) > 2 and part not in ("the", "and", "for", "with", "best", "practices"):
            tags.append(part)
    return tags[:4]


def download_repo_skills(source: str, work_dir: Path) -> list[Path]:
    """Download skills from a source using npx skills add."""
    # Create a fake agent dir structure so npx skills installs there
    agent_skills_dir = work_dir / ".claude" / "skills"
    agent_skills_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "npx", "skills", "add", source,
        "-a", "claude-code",
        "-s", "*",
        "--copy",
        "-y",
    ]

    print(f"  Downloading: npx skills add {source} ...")
    try:
        # Use shell=True on Windows (npx is a cmd script), list form on Unix
        import platform
        if platform.system() == "Windows":
            run_cmd: str | list[str] = " ".join(cmd)
            use_shell = True
        else:
            run_cmd = cmd
            use_shell = False

        result = subprocess.run(
            run_cmd, cwd=str(work_dir), capture_output=True, text=True,
            timeout=120, shell=use_shell,
        )
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: {source}")
        return []

    # Find all downloaded SKILL.md files
    skill_dirs = []
    if agent_skills_dir.exists():
        for skill_md in agent_skills_dir.rglob("SKILL.md"):
            skill_dirs.append(skill_md.parent)

    # Also check .agents/skills/ (some agents use this)
    alt_dir = work_dir / ".agents" / "skills"
    if alt_dir.exists():
        for skill_md in alt_dir.rglob("SKILL.md"):
            if skill_md.parent not in skill_dirs:
                skill_dirs.append(skill_md.parent)

    return skill_dirs


def import_skill(skill_dir: Path, dry_run: bool = False) -> str | None:
    """Import a single skill into our bundled skills/ folder.

    Returns the skill name if imported, None if skipped.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    try:
        post = frontmatter.load(str(skill_md))
    except Exception:
        print(f"    SKIP (parse error): {skill_dir.name}")
        return None

    name = post.get("name", "")
    description = post.get("description", "")

    if not name or not isinstance(name, str):
        print(f"    SKIP (no name): {skill_dir.name}")
        return None

    # Validate name format
    if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", name):
        print(f"    SKIP (invalid name '{name}'): {skill_dir.name}")
        return None

    # Skip if already exists
    target_dir = SKILLS_DIR / name
    if target_dir.exists():
        return None  # silent skip

    if dry_run:
        print(f"    WOULD IMPORT: {name}")
        return name

    # Copy entire skill directory
    shutil.copytree(skill_dir, target_dir)
    print(f"    IMPORTED: {name}")
    return name


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    # Load existing registry map
    with open(REGISTRY_MAP) as f:
        registry_map = json.load(f)

    existing_count = len(list(SKILLS_DIR.iterdir()))
    imported: list[str] = []

    for source in SOURCES:
        print(f"\n=== {source} ===")

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            skill_dirs = download_repo_skills(source, work_dir)
            print(f"  Found {len(skill_dirs)} skill(s)")

            for skill_dir in skill_dirs:
                name = import_skill(skill_dir, dry_run=dry_run)
                if name and name not in registry_map:
                    # Read frontmatter for category inference
                    try:
                        post = frontmatter.load(str(skill_dir / "SKILL.md"))
                        desc = post.get("description", "")
                    except Exception:
                        desc = ""

                    categories = infer_categories(name, desc)
                    tags = infer_tags(name, desc)
                    registry_map[name] = {"categories": categories, "tags": tags}
                    imported.append(name)

    if not dry_run and imported:
        # Write updated registry map
        sorted_map = dict(sorted(registry_map.items()))
        with open(REGISTRY_MAP, "w") as f:
            json.dump(sorted_map, f, indent=2, ensure_ascii=False)
            f.write("\n")

    new_count = len(list(SKILLS_DIR.iterdir()))
    print(f"\nDone: {len(imported)} new skills imported ({existing_count} -> {new_count})")
    if imported:
        print("New skills:")
        for name in sorted(imported):
            print(f"  + {name}")


if __name__ == "__main__":
    main()
