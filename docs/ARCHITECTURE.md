# Architecture

This document describes the internal architecture of AI Setup Forge.

## Overview

AI Setup Forge is a Python CLI tool that manages agent skills (`SKILL.md`) and agent definitions (`.agent.md`) for three coding tools: Claude Code, Mistral Vibe, and GitHub Copilot CLI.

The architecture follows a layered design: a CLI layer dispatches user commands to domain modules that handle discovery, installation, removal, and persistence. All modules are independent of each other except through shared types and constants.

```
User
 |
 v
cli.py          CLI layer (Click commands, Rich output)
 |
 +-- skills.py          Skill discovery & parsing
 +-- agent_defs.py      Agent definition discovery & parsing
 +-- installer.py       Skill installation (canonical + symlink)
 +-- remover.py         Skill removal
 +-- finder.py          Search (bundled + skills.sh API)
 +-- updater.py         Update checking & execution (GitHub API)
 +-- validator.py       SKILL.md validation against spec
 +-- init_skill.py      Skill template scaffolding
 +-- registry.py        SQLite registry (inventory, categories, tags)
 +-- skill_lock.py      Lock file (.skill-lock.json)
 |
 +-- source_parser.py   Parse source strings (GitHub, GitLab, local, etc.)
 +-- git_utils.py       Shallow clone with auth
 +-- agents.py          Agent configs & detection
 +-- types.py           Shared dataclasses
 +-- constants.py       Spec constraints & paths
```

## Module Descriptions

### Entry Points

| Module | Lines | Role |
|---|---|---|
| `__main__.py` | 5 | `python -m ai_setup_forge` entry point |
| `__init__.py` | 3 | Package version (`__version__`) |
| `cli.py` | 1384 | All CLI commands (Click groups + Rich tables) |

`cli.py` is the only module that imports Click and Rich. It defines three command groups:
- **Root commands**: `add`, `remove`, `list`, `find`, `check`, `update`, `init`, `validate`
- **`agents` subgroup**: `status`, `add`, `remove`, `list`, `find`, `init`
- **`registry` subgroup**: `init`, `sync`, `list`, `show`, `search`, `tag`, `untag`, `categorize`, `uncategorize`, `set-origin`, `remove`, `stats`

### Discovery & Parsing

| Module | Lines | Role |
|---|---|---|
| `skills.py` | 193 | Find and parse `SKILL.md` files from a directory tree |
| `agent_defs.py` | 416 | Find and parse `.agent.md` files, install/remove agent definitions |
| `source_parser.py` | 185 | Parse user input into `ParsedSource` (GitHub, GitLab, local, bundled, SSH, direct URL) |

**Skill discovery** follows a priority search order:
1. `skills/`, `skills/.curated/`, `skills/.experimental/`
2. `.agents/skills/`, `.claude/skills/`, `.vibe/skills/`, `.github/skills/`
3. Recursive fallback (up to depth 5, skipping `node_modules`, `.git`, etc.)

Skills are deduplicated by name (first found wins).

### Installation & Removal

| Module | Lines | Role |
|---|---|---|
| `installer.py` | 184 | Copy skill to canonical dir, create symlinks/junctions per agent |
| `remover.py` | 147 | Remove skills from agent dirs and canonical storage |
| `git_utils.py` | 127 | Shallow clone with GitHub token auth |

**Installation flow:**

```
Source (GitHub, local, bundled)
  |
  v
discover_skills()   -- find all SKILL.md files
  |
  v
install_skill()     -- for each skill:
  |
  +-- 1. Copy to .agents/skills/<name>/     (canonical)
  +-- 2. For each target agent:
         create symlink/junction/copy
         from <agent>/skills/<name>/ -> canonical
```

**Link creation strategy** (platform-aware):
1. Try symlink (Unix default)
2. Try directory junction (Windows, no admin needed)
3. Fall back to file copy

Path traversal is validated before any write operation.

### Persistence

| Module | Lines | Role |
|---|---|---|
| `registry.py` | 1044 | SQLite database for skill/agent inventory |
| `skill_lock.py` | 148 | JSON lock file for update tracking |

**Registry** (`~/.ai-setup-forge/skills_registry.db`):
- Auto-initializes on first use (lazy init)
- Tables: `skills`, `agent_definitions`, `categories`, `tags`, junction tables
- Seeded with bundled skills and default categories
- Updated as a side effect of `add`, `remove`, `validate` commands

**Lock file** (`~/.agents/.skill-lock.json`):
- Tracks installed skills with source URL, hash, timestamps
- Used by `check` and `update` to detect outdated skills
- Records last selected agents for convenience

### Search & Updates

| Module | Lines | Role |
|---|---|---|
| `finder.py` | 162 | Search bundled skills and skills.sh registry API |
| `updater.py` | 372 | Check GitHub Trees API for changes, re-install outdated skills |

**Update detection**: compares the stored `skill_folder_hash` (from the lock file) against the current GitHub tree SHA for the skill's directory. If they differ, the skill is outdated.

### Validation & Scaffolding

| Module | Lines | Role |
|---|---|---|
| `validator.py` | 222 | Validate SKILL.md frontmatter and body against the Agent Skills spec |
| `init_skill.py` | 120 | Generate SKILL.md templates with agent-specific frontmatter |

Validation checks: required fields (`name`, `description`), name format (lowercase, hyphens, max 64 chars), description length, metadata types, agent-specific field warnings, body line count.

### Configuration

| Module | Lines | Role |
|---|---|---|
| `agents.py` | 91 | Agent configs (paths, detection) for Claude Code, Mistral Vibe, Copilot CLI |
| `types.py` | 148 | All shared dataclasses (`Skill`, `AgentDefinition`, `ParsedSource`, etc.) |
| `constants.py` | 64 | Spec constraints, paths, discovery settings |

## Data Flow Diagrams

### `add bundled -c security`

```
CLI: parse args
 |
 v
source_parser.parse_source("bundled")
 |-> ParsedSource(type="bundled", local_path=<bundled_skills_dir>)
 |
 v
skills.discover_skills(bundled_dir)
 |-> [Skill, Skill, ...]   (680+ skills)
 |
 v
skills._get_category_skill_names(["security"])
 |-> {"jwt-authentication", "owasp-top-10-mitigation", ...}
 |
 v
filter by category -> 43 skills
 |
 v
agents._resolve_agents() -> ["claude-code"]
 |
 v
for each skill:
  installer.install_skill(skill, ["claude-code"])
    |-> copy to .agents/skills/<name>/
    |-> symlink .claude/skills/<name>/ -> canonical
  registry.upsert_skill(...)
  registry.mark_installed(...)
```

### `agents add bundled`

```
CLI: parse args
 |
 v
agent_defs._get_bundled_agents_dir()
 |-> <project>/agents/
 |
 v
agent_defs.discover_agent_defs(agents_dir)
 |-> [AgentDefinition, ...]   (12 agents)
 |
 v
agents._resolve_agents() -> ["claude-code"]
 |
 v
for each agent_def:
  agent_defs.install_agent_def(ad, ["claude-code"])
    |-> copy to .agents/agent-definitions/<name>.agent.md
    |-> symlink .claude/agents/<name>.agent.md -> canonical
  registry.upsert_agent_def(...)
  registry.mark_agent_installed(...)
```

## Directory Layout

### Project Structure

```
ai-setup-forge/
|-- src/ai_setup_forge/     Python package (18 modules, ~5000 lines)
|-- tests/                   Unit tests (12 files, ~2800 lines, 243 tests)
|-- skills/                  680+ bundled skills (SKILL.md per directory)
|-- agents/                  12 bundled agent definitions (.agent.md)
|-- skills-registry/         Schema, category/tag mappings (JSON + SQL)
|-- scripts/                 Import script for skills.sh
|-- docs/                    Specifications and architecture
|-- .github/workflows/       CI (GitHub Actions)
|-- pyproject.toml           Build config (hatchling)
```

### On-Disk Layout After Installation

```
project/
|-- .agents/
|   |-- skills/
|   |   |-- clean-architecture/    (canonical copy)
|   |   |   +-- SKILL.md
|   |   +-- jwt-authentication/
|   |       +-- SKILL.md
|   +-- agent-definitions/
|       +-- architect.agent.md     (canonical copy)
|
|-- .claude/
|   |-- skills/
|   |   |-- clean-architecture/    -> ../../.agents/skills/clean-architecture/
|   |   +-- jwt-authentication/    -> ../../.agents/skills/jwt-authentication/
|   +-- agents/
|       +-- architect.agent.md     -> ../../.agents/agent-definitions/architect.agent.md
|
|-- .vibe/skills/                  (same symlink pattern)
+-- .github/skills/                (same symlink pattern)
```

### Global Installation Layout

```
~/.agents/
|-- skills/
|   +-- <name>/SKILL.md            (canonical)
+-- .skill-lock.json               (lock file)

~/.claude/skills/<name>/            (symlink -> canonical)
~/.vibe/skills/<name>/              (symlink -> canonical)
~/.copilot/skills/<name>/           (symlink -> canonical)

~/.ai-setup-forge/
+-- skills_registry.db              (SQLite registry)
```

## Key Design Decisions

1. **Canonical storage**: Skills live in `.agents/skills/<name>/` with symlinks into each agent's directory. This avoids duplication and ensures a single source of truth.

2. **Platform-aware linking**: Symlinks on Unix, directory junctions on Windows (no admin), copy fallback. The user never needs to think about this.

3. **Lazy registry init**: The SQLite database auto-creates on first use. No manual setup required after install.

4. **Local imports in commands**: Heavy modules (`git_utils`, `installer`, `registry`) are imported inside CLI functions, not at module level. This keeps `--help` and `--version` fast.

5. **Side-effect registry updates**: Every `add`/`remove`/`validate` command updates the registry automatically. The user never runs `registry sync` manually.

6. **Lock file vs registry**: The lock file tracks install provenance (source URL, hash) for update detection. The registry tracks discovery and classification (categories, tags, install status). They serve different purposes.

7. **Category-based install**: The `-c` flag reads `bundled_skills_map.json` to resolve category names to skill names, then filters the discovered skills list. This avoids coupling the installer to the registry database.

## Dependencies

| Package | Purpose |
|---|---|
| `click>=8.1` | CLI framework (commands, options, groups) |
| `rich>=13.0` | Terminal output (tables, colors, progress) |
| `python-frontmatter>=1.1` | YAML frontmatter parsing for SKILL.md and .agent.md |
| `httpx>=0.27` | HTTP client (skills.sh API, GitHub API) |

Dev dependencies: `pytest`, `ruff`, `mypy`.

## Test Coverage

| Module | Test File | Tests |
|---|---|---|
| `skills.py` | `test_skills.py` | Discovery, parsing, internal skills |
| `installer.py` | `test_installer.py` | Install, symlink, copy, path validation |
| `remover.py` | `test_remover.py` | Removal from agents and canonical |
| `source_parser.py` | `test_source_parser.py` | GitHub, GitLab, local, SSH URL parsing |
| `validator.py` | `test_validator.py` | Name validation, frontmatter validation |
| `finder.py` | `test_finder.py` | Bundled search, registry API search |
| `skill_lock.py` | `test_skill_lock.py` | Lock file CRUD, atomic writes |
| `registry.py` | `test_registry.py` | SQLite CRUD, sync, stats, agent defs |
| `updater.py` | `test_updater.py` | Check updates, GitHub API, update execution |
| `agent_defs.py` | `test_agent_defs.py` | Discovery, install, removal, MCP servers |
| `agents.py` | `test_agents.py` | Agent detection |
| `cli.py` | `test_cli.py` | (empty -- planned for v0.2.0) |
