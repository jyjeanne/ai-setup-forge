# AI Setup Forge - Python Project Specification

## Overview

**AI Setup Forge** is a Python CLI tool that manages, installs, and removes agent skills across three coding tools: **Claude Code**, **Mistral Vibe**, and **Copilot CLI**. It is inspired by [vercel-labs/skills](./sample-projects/skills-main/) (a Node.js/TypeScript project) and reimplements its core functionality in Python, scoped to the three target agents.

Skills are reusable instruction sets defined in `SKILL.md` files (Markdown with YAML frontmatter) that extend a coding agent's capabilities. They follow the open [Agent Skills specification](https://agentskills.io/specification). This tool acts as the package manager for those skills.

---

## Agent Skills Specification (agentskills.io)

This section documents the **official open standard** that all three target agents implement. The specification defines the portable, cross-agent skill format. Agent-specific extensions are documented in the Target Agents section below.

**Reference:** <https://agentskills.io/specification>
**Validation tool:** [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) (`skills-ref validate ./my-skill`)

### Directory Structure

A skill is a directory containing, at minimum, a `SKILL.md` file:

```
skill-name/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
├── assets/           # Optional: templates, resources
└── ...               # Any additional files or directories
```

**Optional directories:**
- `scripts/` - Executable code agents can run. Should be self-contained, include error messages, and handle edge cases. Supported languages depend on agent implementation.
- `references/` - Additional documentation loaded on demand (e.g. `REFERENCE.md`, domain-specific files). Keep individual files focused for efficient context use.
- `assets/` - Static resources: templates, images, data files, schemas.

### SKILL.md Format

The `SKILL.md` file **must** contain YAML frontmatter (between `---` markers) followed by Markdown content.

#### Frontmatter Fields (Official Spec)

| Field | Required | Type | Constraints |
|---|---|---|---|
| `name` | **Yes** | string | 1-64 chars. Lowercase `a-z`, digits, hyphens only. No leading/trailing/consecutive hyphens. **Must match parent directory name.** |
| `description` | **Yes** | string | 1-1024 chars. Should describe what the skill does AND when to use it. Include keywords for agent discovery. |
| `license` | No | string | License name or reference to a bundled license file. |
| `compatibility` | No | string | 1-500 chars. Environment requirements (target product, system packages, network access). Most skills don't need this. |
| `metadata` | No | map\<string, string\> | Arbitrary key-value pairs for additional properties. Use unique key names to avoid conflicts. |
| `allowed-tools` | No | string | Space-delimited list of pre-approved tools. **Experimental** - support varies between agents. |

#### `name` Validation Rules

- 1-64 characters
- Unicode lowercase alphanumeric (`a-z`, `0-9`) and hyphens (`-`) only
- Must **not** start or end with a hyphen
- Must **not** contain consecutive hyphens (`--`)
- Must **match the parent directory name** (e.g., `my-skill/SKILL.md` must have `name: my-skill`)

```yaml
# Valid
name: pdf-processing
name: data-analysis
name: code-review

# Invalid
name: PDF-Processing     # uppercase not allowed
name: -pdf               # cannot start with hyphen
name: pdf--processing    # consecutive hyphens not allowed
```

#### `description` Best Practices

Should describe both **what** the skill does and **when** to use it. Include specific keywords for agent discovery.

```yaml
# Good - describes what AND when, includes keywords
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.

# Poor - too vague for agent discovery
description: Helps with PDFs.
```

#### `allowed-tools` Format

Space-delimited list. Tool name syntax is agent-specific:

```yaml
allowed-tools: Bash(git:*) Bash(jq:*) Read
```

#### Body Content

The Markdown body after frontmatter contains skill instructions. No format restrictions. Recommended sections:
- Step-by-step instructions
- Examples of inputs and outputs
- Common edge cases

Keep `SKILL.md` **under 500 lines**. Move detailed reference material to separate files.

### Progressive Disclosure (Context Efficiency)

Skills are loaded in three tiers:

1. **Metadata** (~100 tokens): `name` and `description` loaded at startup for all skills
2. **Instructions** (< 5000 tokens recommended): Full `SKILL.md` body loaded when skill is activated
3. **Resources** (as needed): Files in `scripts/`, `references/`, `assets/` loaded only when required

This is critical for the `init` command: generated templates should encourage this pattern.

### File References

When referencing other files in a skill, use relative paths from the skill root:

```markdown
See [the reference guide](references/REFERENCE.md) for details.
Run the extraction script: scripts/extract.py
```

Keep file references **one level deep** from `SKILL.md`. Avoid deeply nested reference chains.

---

## Target Agents - Detailed Reference

Each agent has its own skills ecosystem with specific paths, frontmatter fields, and behaviors. The table below is a summary; the subsections that follow contain the authoritative details gathered from each tool's official documentation.

| Agent | CLI Name | Project Skills Path | Global Skills Path |
|---|---|---|---|
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| Mistral Vibe | `mistral-vibe` | `.vibe/skills/` | `~/.vibe/skills/` |
| Copilot CLI | `github-copilot` | `.github/skills/` + `.agents/skills/` | `~/.copilot/skills/` |

### Claude Code

**Documentation:** <https://code.claude.com/docs/en/skills>

**Skill format:** A directory containing `SKILL.md` (required) plus optional supporting files (templates, examples, scripts). Keep `SKILL.md` under 500 lines; move reference material to separate files.

**Discovery paths (project-level):**
- `.claude/skills/<skill-name>/SKILL.md`
- Also discovers from nested `.claude/skills/` in subdirectories (monorepo support)
- Also discovers from directories added via `--add-dir`

**Discovery paths (personal/global):**
- `~/.claude/skills/<skill-name>/SKILL.md`

**Priority order:** Enterprise > Personal > Project. Plugin skills use `plugin-name:skill-name` namespace.

**Supported frontmatter fields:**

| Field | Required | Description |
|---|---|---|
| `name` | No | Display name. If omitted, uses directory name. Lowercase letters, numbers, hyphens, max 64 chars. |
| `description` | Recommended | What the skill does. Claude uses this to decide when to apply the skill. If omitted, uses first paragraph of content. |
| `argument-hint` | No | Hint for autocomplete (e.g. `[issue-number]`). |
| `disable-model-invocation` | No | `true` to prevent Claude from auto-loading; user must invoke via `/name`. Default: `false`. |
| `user-invocable` | No | `false` to hide from `/` menu (background knowledge only). Default: `true`. |
| `allowed-tools` | No | Tools Claude can use without asking permission when this skill is active. |
| `model` | No | Model to use when this skill is active. |
| `context` | No | Set to `fork` to run in a forked subagent. |
| `agent` | No | Subagent type when `context: fork` (e.g. `Explore`, `Plan`, `general-purpose`). |
| `hooks` | No | Hooks scoped to this skill's lifecycle. |

**Special features:**
- **String substitutions:** `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_SKILL_DIR}`.
- **Dynamic context injection:** `` !`command` `` syntax runs shell commands before content is sent to Claude.
- **Extended thinking:** Include the word "ultrathink" in skill content to enable.
- **Character budget:** Skill descriptions consume 2% of context window (~16,000 chars fallback). Check with `/context`.
- **Commands merged into skills:** `.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both create `/deploy`.

### Mistral Vibe

**Documentation:** <https://docs.mistral.ai/mistral-vibe/agents-skills#skills>

**Skill format:** A directory containing `SKILL.md` with YAML frontmatter.

**Discovery paths (in order):**
1. Global: `~/.vibe/skills/`
2. Project-level: `.vibe/skills/` in project root
3. Custom paths: configured via `skill_paths` in `config.toml`

**Custom path configuration (`config.toml`):**
```toml
skill_paths = ["/path/to/custom/skills"]
```

**Supported frontmatter fields:**

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Skill identifier. |
| `description` | Yes | Human-readable description. |
| `license` | No | License type (e.g. `MIT`). |
| `compatibility` | No | Compatibility requirements (e.g. `Python 3.12+`). |
| `user-invocable` | No | Whether user can invoke directly. |
| `allowed-tools` | No | List of tools the skill is permitted to use. |

**Skill enable/disable (pattern matching in `config.toml`):**
```toml
enabled_skills = ["code-review", "test-*"]
disabled_skills = ["experimental-*"]
```
Supports exact names, glob patterns (`test-*`), and regex with `re:` prefix.

**Note:** Vibe follows the Agent Skills specification. No built-in CLI commands for skill management (this tool fills that gap).

### Copilot CLI (GitHub Copilot)

**Documentation:** <https://docs.github.com/en/copilot/concepts/agents/about-agent-skills>

**Skill format:** A directory containing `SKILL.md` with YAML frontmatter, plus optional supplementary resources.

**Discovery paths (precedence order, first-found-wins):**
1. `.github/skills/<skill-name>/SKILL.md`
2. `.agents/skills/<skill-name>/SKILL.md`
3. `.claude/skills/<skill-name>/SKILL.md` (cross-tool compatibility)
4. Inherited from parent directories (monorepo support)
5. `~/.copilot/skills/<skill-name>/SKILL.md` (personal, Copilot CLI only)
6. `~/.claude/skills/<skill-name>/SKILL.md` (personal, cross-tool)
7. Plugin skill directories (via `plugin.json` `skills` field)
8. Custom directories via `COPILOT_SKILLS_DIRS` environment variable

**Supported frontmatter fields:**

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Unique identifier. Lowercase with hyphens. |
| `description` | Yes | What the skill does; used by Copilot to decide relevance. |
| `license` | No | License description. |

**Built-in CLI skill management commands:**
- `/skills list` - List available skills
- `/skills info` - View skill details
- `/skills add` - Add alternative skill storage location
- `/skills reload` - Reload skills during session
- `/skills remove SKILL-DIRECTORY` - Remove directly-added skills

**Deduplication:** By `name` field, first-found-wins.

**Plugin manifest (`plugin.json`):**
```json
{
  "skills": ["skills/", "extra-skills/"]
}
```

**Environment variable:** `COPILOT_SKILLS_DIRS` for additional custom skill directories.

**Note:** The Copilot Coding Agent (headless, GitHub-hosted) and Copilot CLI share the same skill file format. Copilot CLI adds interactive `/skills` commands and explicit `/skill-name` invocation.

---

## SKILL.md Frontmatter - Cross-Agent Compatibility Matrix

When generating, installing, or validating skills, the tool must understand which frontmatter fields are defined by the **official Agent Skills spec** (portable), and which are **agent-specific extensions**.

### Official Spec Fields (Portable)

These fields are defined by [agentskills.io/specification](https://agentskills.io/specification) and should work across all compliant agents.

| Field | Claude Code | Mistral Vibe | Copilot CLI | Spec Constraints |
|---|---|---|---|---|
| `name` | Yes (optional, uses dir name) | Yes (required) | Yes (required) | 1-64 chars, `a-z0-9-`, must match dir name |
| `description` | Yes (recommended) | Yes (required) | Yes (required) | 1-1024 chars, non-empty |
| `license` | Ignored | Yes | Yes | Free-form string |
| `compatibility` | Ignored | Yes | Ignored | Max 500 chars |
| `metadata` | Yes | Unknown | Unknown | Map\<string, string\> |
| `allowed-tools` | Yes | Yes | No | Space-delimited. **Experimental.** |

### Agent-Specific Extensions (Non-Portable)

These fields are extensions by individual agents, not part of the official spec. The tool should preserve them during install but warn during validation.

| Field | Agent | Description |
|---|---|---|
| `user-invocable` | Claude Code, Mistral Vibe | Hide from manual invocation menu |
| `disable-model-invocation` | Claude Code | Prevent auto-loading by model |
| `argument-hint` | Claude Code | Autocomplete hint (e.g. `[issue-number]`) |
| `model` | Claude Code | Model override for this skill |
| `context` | Claude Code | `fork` to run in isolated subagent |
| `agent` | Claude Code | Subagent type (`Explore`, `Plan`, etc.) |
| `hooks` | Claude Code | Lifecycle hooks scoped to skill |
| `metadata.internal` | skills CLI ecosystem | Hide from public discovery |

---

## Architecture

### Project Structure

```
skill-library/
├── src/
│   └── ai_setup_forge/
│       ├── __init__.py
│       ├── __main__.py          # Entry point (python -m ai_setup_forge)
│       ├── cli.py               # CLI argument parsing and command dispatch
│       ├── agents.py            # Agent configs (paths, detection)
│       ├── skills.py            # SKILL.md discovery and parsing
│       ├── installer.py         # Install logic (copy, symlink, junctions)
│       ├── remover.py           # Remove logic + list installed skills
│       ├── finder.py            # Search bundled skills and skills.sh registry
│       ├── registry.py          # Skills & agents registry (SQLite local database)
│       ├── agent_defs.py        # Agent definition discovery, install, remove
│       ├── init_skill.py        # Scaffold new SKILL.md templates
│       ├── validator.py         # Validate SKILL.md against Agent Skills spec
│       ├── source_parser.py     # Parse source strings (GitHub, GitLab, local, bundled, URL)
│       ├── git_utils.py         # Git clone operations
│       ├── skill_lock.py        # Lock file (.skill-lock.json) management
│       ├── constants.py         # Shared constants
│       └── types.py             # Dataclasses and type definitions
├── skills/                      # Bundled skills shipped with the package
│   └── find-skills/
│       └── SKILL.md
├── agents/                      # Bundled agent definitions shipped with the package
│   ├── playwright-test-generator.agent.md
│   ├── docs-agent.agent.md
│   └── ...                      # 12 agent definitions total
├── skills-registry/             # Registry data files (tracked in git)
│   ├── schema.sql               # SQLite DDL script
│   ├── bundled_skills_map.json  # Category/tag mapping for bundled skills
│   └── bundled_agents_map.json  # Category/tag mapping for bundled agents
├── tests/
│   ├── test_agents.py
│   ├── test_skills.py
│   ├── test_source_parser.py
│   ├── test_validator.py
│   ├── test_installer.py
│   ├── test_remover.py
│   ├── test_skill_lock.py
│   ├── test_finder.py
│   ├── test_registry.py
│   └── test_agent_defs.py
├── pyproject.toml               # Project metadata, dependencies, scripts
├── README.md
└── docs/
    ├── SKILLS_MANAGER.md        # Full specification
    ├── SPEC_SKILLS_REGISTRY.md  # Detailed registry specification
    ├── AGENTS.md                # Agent file format conventions
    ├── AGENT_TEMPLATE.md        # Template for new agent definitions
    └── AGENT_SAMPLE.md          # Minimal agent definition example
```

### Key Design Decisions

1. **Python 3.10+** - Uses `match` statements, dataclasses, `pathlib`, and type hints.
2. **uv for project management** - Uses [uv](https://docs.astral.sh/uv/) for dependency management, virtual environments, and tool installation. Dev dependencies use PEP 735 `[dependency-groups]`.
3. **Minimal dependencies** - `python-frontmatter` (YAML + Markdown parsing), `click` (CLI framework), `rich` (terminal UI/colors). Git operations via subprocess calls to `git` (no `gitpython` dependency).
4. **Canonical install location** - Skills are always copied to `.agents/skills/<skill-name>/` first, then symlinked (or copied) into each target agent's skills directory. This mirrors the reference project's architecture.
5. **Cross-platform** - Uses `pathlib.Path` throughout. On Windows, creates junctions instead of symlinks (no admin required).
6. **Local skills registry** - SQLite database at `~/.ai-setup-forge/skills_registry.db` catalogs all known skills with categories, tags, origin, and install status. Auto-initialized on first use with bundled skills (`installed=0`). Updated as a side effect of `add`/`remove`/`validate`/`init` commands.

---

## Data Models

### `AgentConfig`

```python
@dataclass
class AgentConfig:
    name: str                    # e.g. "claude-code"
    display_name: str            # e.g. "Claude Code"
    skills_dir: str              # project-level relative path, e.g. ".claude/skills"
    alt_skills_dirs: list[str]   # additional project-level paths the agent reads from
    global_skills_dir: Path      # absolute path to global skills
    detect_installed: Callable   # check if agent is present on system
```

### `Skill`

```python
@dataclass
class Skill:
    name: str
    description: str
    path: Path                   # directory containing SKILL.md
    raw_content: str | None = None
    metadata: dict | None = None
    frontmatter: dict | None = None  # full parsed frontmatter (all fields)
```

### `ParsedSource`

```python
@dataclass
class ParsedSource:
    type: Literal["github", "gitlab", "git", "local", "direct-url", "bundled"]
    url: str
    subpath: str | None = None
    local_path: Path | None = None
    ref: str | None = None
    skill_filter: str | None = None
```

### `SkillLockEntry`

```python
@dataclass
class SkillLockEntry:
    source: str                  # e.g. "owner/repo"
    source_type: str             # e.g. "github", "local"
    source_url: str              # original install URL
    skill_path: str | None       # subpath within repo
    skill_folder_hash: str       # SHA for change detection
    installed_at: str            # ISO timestamp
    updated_at: str              # ISO timestamp
```

### `InstalledSkill`

```python
@dataclass
class InstalledSkill:
    name: str
    description: str
    path: Path
    canonical_path: Path
    scope: Literal["project", "global"]
    agents: list[str]
```

### `SyncResult`

```python
@dataclass
class SyncResult:
    added: int
    updated: int
    errors: list[str]
```

---

## Skills Registry (Local Database)

The Skills Registry is a local SQLite database at `~/.ai-setup-forge/skills_registry.db` that acts as a **user-level inventory** of all skills known to the machine. It is always user-scoped (not project-scoped).

> **Detailed specification:** [SPEC_SKILLS_REGISTRY.md](./SPEC_SKILLS_REGISTRY.md)

### Key Principles

1. **Auto-populated on first use**: The registry auto-initializes and syncs all bundled skills on first access by any ai-setup-forge command. No manual `registry init` required.
2. **All bundled skills start as `installed = 0`**: After install, the user has a full catalog of 52+ skills — none installed yet. Users browse and selectively install what they need.
3. **Existing commands update the registry**: `add` sets `installed=1`, `remove` sets `installed=0`, `validate` sets the `validated` flag, `init` registers new homemade skills. The registry stays in sync without manual intervention.

### Database Schema (Summary)

| Table | Purpose |
|---|---|
| `skills` | Core skill inventory: name, description, origin, installed, validated, etc. |
| `categories` | Classification buckets (architecture, devops, web, testing, etc.) |
| `tags` | Technical stack / topic labels (java, python, spring, ddd, etc.) |
| `skill_categories` | Many-to-many: skills <-> categories |
| `skill_tags` | Many-to-many: skills <-> tags |
| `skill_agents` | Which coding tools a skill is installed for, at which scope |
| `agent_definitions` | Agent definition inventory: name, description, origin, category, model, etc. |
| `agent_def_tags` | Many-to-many: agent definitions <-> tags |
| `agent_def_coding_agents` | Which coding tools an agent definition is installed for |
| `registry_meta` | Schema version, creation timestamp |

**Origin values:** `bundled`, `github`, `gitlab`, `website`, `homemade`, `unknown`.

**Origin derivation from `ParsedSource.type`:**

| ParsedSource.type | Registry origin |
|---|---|
| `bundled` | `bundled` |
| `github` | `github` |
| `gitlab` | `gitlab` |
| `local` | `homemade` |
| `git` | `github` |
| `direct-url` | `website` |

### Data Files

```
skills-registry/
├── schema.sql               # SQLite DDL (tables, indexes, triggers, seed data)
└── bundled_skills_map.json  # Category/tag mapping for bundled skills
```

`bundled_skills_map.json` maps each bundled skill name to its categories and tags:

```json
{
  "clean-architecture": {
    "categories": ["architecture", "design"],
    "tags": ["solid", "hexagonal"]
  }
}
```

This is a versioned data file — reclassifying skills means editing JSON, not code.

### How Commands Update the Registry

| Command | Registry Effect |
|---|---|
| `add` | Upsert skill → `installed=1`, `installed_at=now`; insert `skill_agents` rows for each target agent+scope |
| `remove` | Delete `skill_agents` rows; set `installed=0` only when no agents remain |
| `validate` | Set `validated=1` if passed, `validated=0` if failed |
| `init` | Insert skill with `origin=homemade`, `installed=0` |
| `find` | Read: query registry for local matches before querying skills.sh |
| `list` | Read: enrich output with categories, tags, origin from registry |
| `agents add` | Upsert agent def → `installed=1`; insert `agent_def_coding_agents` rows |
| `agents remove` | Delete `agent_def_coding_agents` rows; set `installed=0` when no coding tools remain |
| `agents init` | Insert agent def with `origin=homemade` |
| `agents find` | Read: query agent definitions in registry |

### Registry CLI Commands

All under `ai-setup-forge registry` subcommand group:

| Command | Description |
|---|---|
| `registry init [--force]` | Force (re-)initialize the registry. Normally not needed. |
| `registry sync [path] [--origin] [--validate]` | Scan a skills directory and populate the registry |
| `registry list [--category] [--tag] [--origin] [--installed] [--not-installed] [--validated] [--format]` | List skills with filters |
| `registry show <name>` | Show detailed info for a skill |
| `registry search <query>` | Full-text search across name, description, tags, categories |
| `registry tag <skill> <tags...>` | Add tags to a skill |
| `registry untag <skill> <tags...>` | Remove tags from a skill |
| `registry categorize <skill> <categories...>` | Assign categories to a skill |
| `registry uncategorize <skill> <categories...>` | Remove categories from a skill |
| `registry set-origin <skill> <origin>` | Update origin of a skill |
| `registry remove <skill>` | Remove a skill entry from the registry (does NOT uninstall from disk) |
| `registry stats` | Show statistics (total, installed, by origin, by category, top tags) |

---

## Bundled Skills

The AI Setup Forge ships with a curated set of skills in the `skills/` directory at the project root. These bundled skills are available for installation via the special `bundled` source keyword.

**Bundled skills directory:** `<package-root>/skills/`

```
skills/
└── find-skills/
    └── SKILL.md
```

Users can install bundled skills with:

```bash
ai-setup-forge add bundled                        # discover and install from bundled skills
ai-setup-forge add bundled -s find-skills          # install specific bundled skill
ai-setup-forge add bundled --all                   # install all bundled skills to all agents
```

**How it works:**

1. The `bundled` source keyword resolves to the `skills/` directory via `__file__` traversal (dev/editable installs use `<project-root>/skills/`; installed packages use `<package-dir>/bundled_skills/` which is force-included by hatchling).
2. Skills are discovered using the standard discovery logic.
3. Installation follows the same canonical copy + symlink flow as any other source.

This allows the project to ship ready-to-use skills (like `find-skills`) without requiring users to clone a remote repository.

> **Note:** `bundled` is a reserved source keyword. If you have a local directory named `bundled`, use `./bundled` to install from it.

---

## Agent Definitions

In addition to **skills** (`SKILL.md`), the AI Setup Forge also manages **agent definitions** — custom AI agent profiles defined as `.agent.md` files. These are reusable agent configurations that can be installed into coding tools alongside skills.

> **External references:**
> - [agents.md specification](https://agents.md/) — The `AGENTS.md` file convention (plain Markdown, no frontmatter, auto-discovered by 30+ coding tools)
> - [GitHub Copilot custom agents](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents) — The `.agent.md` file format with YAML frontmatter

### Two Complementary Formats

| Format | File | Purpose | Frontmatter |
|---|---|---|---|
| **AGENTS.md** | `AGENTS.md` (root or subdirectory) | Project-level context for any AI coding agent. Plain Markdown, no schema. Auto-discovered by Claude Code, Copilot, Cursor, Codex, etc. | None |
| **Agent definition** | `<name>.agent.md` (in `agents/` directory) | Custom AI agent profile with identity, tools, capabilities, and instructions. YAML frontmatter + Markdown body. | Required |

The AI Setup Forge manages the second format: `.agent.md` agent definitions.

### Bundled Agent Definitions

The project ships agent definitions in the `agents/` directory at the project root:

```
agents/
├── api-tester-specialist.agent.md
├── architect.agent.md
├── docs-agent.agent.md
├── flaky-test-hunter.agent.md
├── implementation-plan.agent.md
├── playwright-test-generator.agent.md
├── playwright-test-healer.agent.md
├── playwright-test-planner.agent.md
├── principal-software-engineer.agent.md
├── selenium-test-executor.agent.md
├── selenium-test-specialist.agent.md
└── test-refactor-specialist.agent.md
```

### `.agent.md` File Format

An agent definition is a single Markdown file with YAML frontmatter:

```yaml
---
name: playwright-test-generator
description: 'Use this agent when you need to create automated browser tests using Playwright Test.'
model: 'Claude Opus 4.6'
tools: ['read', 'edit', 'search', 'execute', 'playwright-test']
---

You are an expert at generating Playwright tests...

## Core Responsibilities
...
```

#### Frontmatter Fields (Cross-Tool Specification)

The `.agent.md` format is shared across GitHub Copilot, Claude Code, and other coding tools. The table below documents every known field and which tools support it.

| Field | Required | Type | Description | Copilot | Claude Code | Mistral Vibe |
|---|---|---|---|---|---|---|
| `name` | No* | string | Agent identifier. Used for deduplication (filename used if omitted). | ✓ | ✓ | ✓ |
| `description` | **Yes** | string | What the agent does and when to use it. Used for automatic agent selection. | ✓ | ✓ | ✓ |
| `model` | No | string | Preferred AI model (e.g. `Claude Opus 4.6`, `Auto`). | ✓ | ✓ | ✓ |
| `tools` | No | list[string] \| string | Tools the agent can use. Defaults to all tools if omitted. Use `[]` to disable all. | ✓ | ✓ | ? |
| `target` | No | string | Environment context: `vscode` or `github-copilot`. Defaults to both if unset. | ✓ | — | — |
| `disable-model-invocation` | No | boolean | Prevents automatic agent selection; requires manual invocation when `true`. Default `false`. | ✓ | — | — |
| `user-invocable` | No | boolean | Controls whether agent appears in manual selection. Default `true`. | ✓ | ✓ | ? |
| `mcp-servers` | No | object | MCP server configuration for additional tool access. | ✓ (coding agent) | ✓ | ? |
| `metadata` | No | object | Custom annotation data (name/value pairs). | ✓ (coding agent) | — | — |
| `handoffs` | No | list[object] | Other agents this agent can delegate to. Each has `label`, `agent`, `prompt`. | VS Code only | — | — |
| `version` | No | string | Semantic version (e.g. `1.0.0`). | — | — | — |
| `category` | No | string | Agent category (e.g. `testing`, `orchestrator`, `documentation`). Custom field for registry. | — | — | — |
| `capabilities` | No | list[string] | What the agent can do (for discovery and matching). Custom field. | — | — | — |
| `scope` | No | object | `includes` and `excludes` boundaries. Custom field. | — | — | — |
| `decision-autonomy` | No | object | `level` (`guided`, `autonomous`) + `examples`. Custom field. | — | — | — |

> \* `name` is technically optional — if omitted, the filename (minus `.agent.md` extension) is used as the identifier. AI Setup Forge always requires a name for registry purposes and will derive it from the filename if missing.

> **Body limit:** Maximum 30,000 characters for the Markdown body content below frontmatter (GitHub Copilot constraint).

> **Deduplication:** Configuration file names (minus `.md` or `.agent.md` extension) are used for deduplication. Lowest level (repository > organization > enterprise) takes precedence.

#### Tool Aliases

Tools specified in the `tools` frontmatter field are cross-tool compatible. All names are **case-insensitive**.

| Primary Alias | Compatible Aliases | Description |
|---|---|---|
| `execute` | `shell`, `Bash`, `powershell` | Execute OS-appropriate shell commands |
| `read` | `Read`, `NotebookRead` | Read file contents |
| `edit` | `Edit`, `MultiEdit`, `Write`, `NotebookEdit` | Edit/write files |
| `search` | `Grep`, `Glob` | Search for files or text in files |
| `agent` | `custom-agent`, `Task` | Invoke other custom agents |
| `web` | `WebSearch`, `WebFetch` | Fetch URLs and web search |
| `todo` | `TodoWrite` | Create/manage task lists (VS Code only) |

MCP server tools use namespace syntax: `server-name/tool-name` or `server-name/*`.

**Out-of-the-box MCP servers (GitHub Copilot coding agent):**

| Server | Available Tools | Notes |
|---|---|---|
| `github` | All read-only tools | Token scoped to source repository |
| `playwright` | All playwright tools | Configured for localhost only |

#### MCP Server Configuration

```yaml
mcp-servers:
  custom-mcp:
    type: 'local'          # 'stdio' in Claude Code/VS Code maps to 'local'
    command: 'some-command'
    args: ['--arg1', '--arg2']
    tools: ["*"]
    env:
      ENV_VAR: ${{ secrets.MY_SECRET }}
```

Environment variable syntax:
- `$VAR_NAME` or `${VAR_NAME}` — direct reference
- `${VAR_NAME:-default}` — with default value
- `${{ secrets.VAR_NAME }}` — GitHub Copilot secrets (coding agent only)
- `${{ vars.VAR_NAME }}` — GitHub Copilot variables (coding agent only)

#### Body Content

The Markdown body contains the agent's instructions. Recommended structure (from `docs/AGENT_TEMPLATE.md`):

```markdown
You are an expert [role] for this project.

## Persona
- You specialize in [domain]
- You understand [context] and translate that into [output]

## Project knowledge
- **Tech Stack:** [technologies]
- **File Structure:** [relevant paths]

## Tools you can use
- **Build:** `command` (description)
- **Test:** `command` (description)

## Standards
Follow these rules for all code you write:
[Naming conventions, code style examples...]

## Boundaries
- Always: [what to always do]
- Ask first: [what requires confirmation]
- Never: [hard constraints]
```

**Complexity levels:** Agent definitions range from minimal (name + description + a few paragraphs) to advanced (multi-agent orchestration with handoffs, MCP servers, and scoped autonomy). See `docs/AGENT_SAMPLE.md` for a minimal example and `agents/api-tester-specialist.agent.md` for an advanced example.

### Agent Installation Paths

Agent definitions are installed to the coding tools' agent directories:

| Coding Tool | Project Path | Global Path |
|---|---|---|
| GitHub Copilot | `.github/agents/` | `~/.copilot/agents/` |
| Claude Code | `.claude/agents/` | `~/.claude/agents/` |
| Mistral Vibe | `.vibe/agents/` | `~/.vibe/agents/` |

**Installation flow:**

1. Copy `.agent.md` file to canonical location: `.agents/agent-definitions/<name>.agent.md`
2. Copy or symlink to each target coding tool's agent directory.

> **Note:** Unlike skills (which are directories containing `SKILL.md`), agent definitions are single files (`<name>.agent.md`).

### Agent Registry

Agent definitions are tracked in the same SQLite registry as skills, in a separate `agent_definitions` table:

```sql
CREATE TABLE IF NOT EXISTS agent_definitions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    description   TEXT    NOT NULL DEFAULT '',
    origin        TEXT    NOT NULL DEFAULT 'unknown'
                         CHECK (origin IN ('bundled', 'github', 'gitlab', 'website', 'homemade', 'unknown')),
    source_url    TEXT    DEFAULT NULL,
    version       TEXT    DEFAULT NULL,
    category      TEXT    DEFAULT NULL,
    model         TEXT    DEFAULT NULL,
    tools         TEXT    DEFAULT NULL,   -- JSON array of tool names, NULL = all tools
    target        TEXT    DEFAULT NULL,   -- 'vscode', 'github-copilot', or NULL (both)
    installed     INTEGER NOT NULL DEFAULT 0 CHECK (installed IN (0, 1)),
    agent_path    TEXT    DEFAULT NULL,
    installed_at  TEXT    DEFAULT NULL,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS agent_def_tags (
    agent_def_id INTEGER NOT NULL REFERENCES agent_definitions(id) ON DELETE CASCADE,
    tag_id       INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (agent_def_id, tag_id)
);

CREATE TABLE IF NOT EXISTS agent_def_coding_agents (
    agent_def_id     INTEGER NOT NULL REFERENCES agent_definitions(id) ON DELETE CASCADE,
    coding_agent_name TEXT    NOT NULL,
    scope             TEXT    NOT NULL DEFAULT 'project' CHECK (scope IN ('project', 'global')),
    PRIMARY KEY (agent_def_id, coding_agent_name, scope)
);
```

**Auto-populated on first use:** All bundled agent definitions from `agents/` are registered with `installed=0`, just like bundled skills.

**Bundled agent definitions mapping** is stored in `skills-registry/bundled_agents_map.json`:

```json
{
  "playwright-test-generator": {
    "category": "testing",
    "tags": ["playwright", "test-generation", "browser-testing"]
  },
  "api-tester-specialist": {
    "category": "testing",
    "tags": ["api", "rest-assured", "supertest"]
  }
}
```

---

## CLI Commands

Entry point: `ai-setup-forge` (or `python -m ai_setup_forge`)

### `add <source>`

Install skills from a source into target agent(s).

```bash
ai-setup-forge add owner/repo
ai-setup-forge add https://github.com/owner/repo
ai-setup-forge add ./local-skills
ai-setup-forge add bundled                           # install from bundled skills
ai-setup-forge add https://github.com/owner/repo/tree/main/skills/my-skill
```

**Options:**

| Flag | Description |
|---|---|
| `-g, --global` | Install to user directory instead of project |
| `-a, --agent <name>` | Target specific agents (repeatable). Values: `claude-code`, `mistral-vibe`, `github-copilot`, or `*` for all |
| `-s, --skill <name>` | Install specific skills by name (repeatable). Use `*` for all |
| `-y, --yes` | Skip confirmation prompts |
| `--all` | Install all skills to all agents without prompts |
| `--mode <symlink\|copy>` | Force install mode (default: `symlink`) |

**Behavior:**

1. Parse the source string into `ParsedSource`.
2. If remote: clone the repo (shallow, depth=1) to a temp directory.
3. Discover `SKILL.md` files in the cloned/local directory.
4. Prompt user to select skills (if not specified via `--skill`).
5. Detect installed agents or use `--agent` filter.
6. For each skill x agent combination:
   - Copy skill to canonical location: `.agents/skills/<skill-name>/`
   - Create symlink from agent skills dir to canonical location.
   - If symlink fails (e.g., permissions), fall back to copy.
7. **Update skills registry**: upsert skill with `installed=1`, origin derived from source type, insert `skill_agents` rows for each agent+scope.
8. Update `.skill-lock.json` (global installs only).
9. Clean up temp directories.

### `list` (alias: `ls`)

List all installed skills.

```bash
ai-setup-forge list
ai-setup-forge list -g
ai-setup-forge list -a claude-code
```

**Options:**

| Flag | Description |
|---|---|
| `-g, --global` | List global skills (default: project) |
| `-a, --agent <name>` | Filter by specific agents |

**Output:** Skill name, path, which agents it's installed for, plus categories, tags, and origin from the skills registry (when available).

### `remove` (alias: `rm`)

Remove installed skills.

```bash
ai-setup-forge remove                    # interactive selection
ai-setup-forge remove my-skill           # by name
ai-setup-forge remove --all              # remove all
ai-setup-forge remove -a claude-code my-skill
```

**Options:**

| Flag | Description |
|---|---|
| `-g, --global` | Remove from global scope |
| `-a, --agent <name>` | Remove from specific agents only |
| `-y, --yes` | Skip confirmation |
| `--all` | Remove all skills from all agents |

**Behavior:**

1. Scan canonical + agent-specific directories for installed skills.
2. Prompt user to select (if no skill names given and not `--all`).
3. For each selected skill:
   - Remove symlinks/directories from each target agent.
   - Remove canonical copy.
   - **Update skills registry**: delete `skill_agents` rows; set `installed=0` when no agents remain.
   - Update lock file (global only).

### `find [query]` (alias: `search`)

Search for skills from two sources: bundled skills and the skills.sh registry.

```bash
ai-setup-forge find                    # list bundled skills
ai-setup-forge find typescript         # search skills.sh + bundled
ai-setup-forge find --registry react   # search skills.sh only
ai-setup-forge find --bundled          # list bundled only
```

**Options:**

| Flag | Description |
|---|---|
| `--registry` | Search skills.sh registry only |
| `--bundled` | Show bundled skills only |

**Behavior:**

1. **With query:** Search the local skills registry first (by name, description, tags, categories — instant, offline), then the skills.sh remote API (`https://skills.sh/api/search?q={query}&limit=10`). Display combined results with source tag (`[local]`, `[bundled]`, or `[skills.sh]`). Registry results include `installed` status.
2. **Without query:** List all skills in the local registry (bundled and any previously discovered).
3. Display results with name, description, source, install count (remote), installed status (local), and install command.
4. Results from skills.sh include a link to the skill page at `https://skills.sh/{slug}`.

**skills.sh Registry API:**

| Detail | Value |
|---|---|
| Base URL | `https://skills.sh` (override via `SKILLS_API_URL` env var) |
| Search endpoint | `GET /api/search?q={query}&limit=10` |
| Response format | `{"skills": [{"id": "owner/repo/skill", "name": "skill-name", "source": "owner/repo", "installs": 12345}]}` |
| Error handling | Timeout after 10s, return empty results on failure |

### `check`

Check if installed skills have updates.

```bash
ai-setup-forge check
```

**Behavior:**

1. Read `.skill-lock.json`.
2. For each GitHub-sourced skill, fetch the current tree SHA via GitHub API.
3. Compare with stored `skill_folder_hash`.
4. Report which skills have updates available.

### `update`

Update all installed skills to latest versions.

```bash
ai-setup-forge update
```

**Behavior:**

1. Run `check` logic to find outdated skills.
2. Re-install each outdated skill using its stored `source_url`.

### `init [name]`

Create a new SKILL.md template following the Agent Skills specification.

```bash
ai-setup-forge init
ai-setup-forge init my-skill
ai-setup-forge init my-skill --agent claude-code
```

**Options:**

| Flag | Description |
|---|---|
| `-a, --agent <name>` | Generate agent-specific frontmatter fields |

**Behavior:**

1. Validate the name against the official spec rules (1-64 chars, lowercase + hyphens, no leading/trailing/consecutive hyphens).
2. If name given: create `<name>/SKILL.md` in current directory. The directory name must match the `name` field (spec requirement).
3. If no name: create `SKILL.md` in current directory, using the directory's basename as the skill name.
4. Template includes:
   - Required frontmatter: `name`, `description` (with placeholder text encouraging good descriptions per spec).
   - Optional sections: `license`, `compatibility`, `metadata` (commented out).
   - Agent-specific fields when `--agent` is used (e.g. `allowed-tools` for Claude Code/Mistral Vibe, `context: fork` for Claude Code).
   - Recommended body structure: "When to use", "Instructions" (step-by-step), with a note to keep under 500 lines.
5. Optionally scaffold `scripts/`, `references/`, `assets/` directories.
6. **Update skills registry**: insert the new skill with `origin=homemade`, `installed=0`.

### `validate [path]`

Validate a SKILL.md file against the Agent Skills specification.

```bash
ai-setup-forge validate ./my-skill
ai-setup-forge validate .
```

**Behavior:**

1. Parse the `SKILL.md` at the given path.
2. Check all spec rules:
   - `name` is present, 1-64 chars, valid characters, no consecutive hyphens, matches directory name.
   - `description` is present, 1-1024 chars, non-empty.
   - `compatibility` is max 500 chars (if present).
   - `metadata` values are strings (if present).
   - `allowed-tools` is space-delimited (if present).
3. Report warnings for non-portable agent-specific fields.
4. Report info for progressive disclosure (body length, file reference depth).

5. **Update skills registry**: if the skill exists in the registry, set `validated=1` (passed) or `validated=0` (failed).

This mirrors the functionality of [`skills-ref validate`](https://github.com/agentskills/agentskills/tree/main/skills-ref).

### `agents status`

Show detected coding tools and their status (replaces the previous top-level `agents` command).

```bash
ai-setup-forge agents status
```

### `agents add <source>`

Install agent definitions (`.agent.md` files) from a source into target coding tools.

```bash
ai-setup-forge agents add bundled                                # install from bundled agents/
ai-setup-forge agents add bundled -s playwright-test-generator    # specific agent definition
ai-setup-forge agents add ./my-agents                             # from local directory
ai-setup-forge agents add owner/repo                              # from GitHub repo
ai-setup-forge agents add bundled --all                            # all agents to all coding tools
```

**Options:**

| Flag | Description |
|---|---|
| `-g, --global` | Install to user directory instead of project |
| `-a, --agent <name>` | Target specific coding tools (`claude-code`, `mistral-vibe`, `github-copilot`, `*`) |
| `-s, --select <name>` | Install specific agent definition by name |
| `-y, --yes` | Skip confirmation prompts |
| `--all` | Install all agent definitions to all coding tools |

**Behavior:**

1. Parse source (same `parse_source()` as skills).
2. Discover `.agent.md` files in the source directory.
3. For each agent definition × coding tool:
   - Copy to canonical location: `.agents/agent-definitions/<name>.agent.md`
   - Copy to coding tool's agent directory (e.g. `.github/agents/<name>.agent.md`)
4. **Update agents registry**: upsert agent definition, `installed=1`, insert `agent_def_coding_agents` rows.

### `agents remove`

Remove installed agent definitions.

```bash
ai-setup-forge agents remove                                # interactive selection
ai-setup-forge agents remove playwright-test-generator      # by name
ai-setup-forge agents remove --all                           # remove all
ai-setup-forge agents remove -a claude-code docs-agent      # from specific coding tool
```

**Options:**

| Flag | Description |
|---|---|
| `-g, --global` | Remove from global scope |
| `-a, --agent <name>` | Remove from specific coding tools only |
| `-y, --yes` | Skip confirmation |
| `--all` | Remove all agent definitions |

### `agents list`

List installed agent definitions.

```bash
ai-setup-forge agents list                  # project-level
ai-setup-forge agents list -g               # global
ai-setup-forge agents list -a claude-code   # filter by coding tool
```

### `agents find [query]`

Search agent definitions in the registry.

```bash
ai-setup-forge agents find                   # list all registered agent definitions
ai-setup-forge agents find playwright        # search by name/description/tags
ai-setup-forge agents find --category testing
ai-setup-forge agents find --tag selenium
```

### `agents init [name]`

Create a new agent definition from the template.

```bash
ai-setup-forge agents init my-agent
```

Creates `<name>.agent.md` using the template from `docs/AGENT_TEMPLATE.md`. Registers the new agent in the registry with `origin=homemade`.

### `agents registry`

Manage agent definitions in the registry (mirrors `registry` subcommands for skills).

```bash
ai-setup-forge agents registry list                          # all agent definitions
ai-setup-forge agents registry list --category testing       # filter by category
ai-setup-forge agents registry list --installed               # installed only
ai-setup-forge agents registry show playwright-test-generator
ai-setup-forge agents registry tag docs-agent documentation markdown
ai-setup-forge agents registry stats
ai-setup-forge agents registry sync                           # re-sync bundled agents/
```

---

## Source Parsing

The `source_parser.py` module converts user input into a `ParsedSource`. Supported formats:

| Input Format | Resolved Type |
|---|---|
| `bundled` | `bundled` (built-in skills shipped with the package) |
| `./local/path` | `local` |
| `/absolute/path` | `local` |
| `C:\windows\path` | `local` |
| `owner/repo` | `github` (shorthand) |
| `owner/repo/path/to/skill` | `github` (with subpath) |
| `owner/repo@skill-name` | `github` (with skill filter) |
| `https://github.com/owner/repo` | `github` |
| `https://github.com/owner/repo/tree/branch/path` | `github` (with ref + subpath) |
| `https://gitlab.com/owner/repo` | `gitlab` |
| `https://gitlab.com/group/subgroup/repo` | `gitlab` (nested groups) |
| `git@github.com:owner/repo.git` | `git` |
| `https://example.com/path/SKILL.md` | `direct-url` |

---

## Skill Discovery

When processing a source directory, skills are discovered in this order:

1. Check if root directory has `SKILL.md` (single-skill repo).
2. Search priority directories:
   - `skills/`, `skills/.curated/`, `skills/.experimental/`, `skills/.system/`
   - `.agents/skills/`, `.claude/skills/`, `.vibe/skills/`, `.github/skills/`
3. If nothing found, recursive search (max depth 5), skipping `node_modules`, `.git`, `dist`, `build`, `__pycache__`, `.venv`, `venv`.

A valid skill requires a `SKILL.md` with YAML frontmatter containing both `name` and `description` per the [Agent Skills spec](#agent-skills-specification-agentskillsio):

```markdown
---
name: my-skill
description: What this skill does and when to use it.
---

# Instructions for the agent...
```

**Validation during discovery:**
- `name` must be present, 1-64 chars, lowercase + hyphens, no consecutive hyphens.
- `description` must be present, 1-1024 chars.
- `name` should match the parent directory name (spec requirement). Mismatches trigger a warning but do not prevent installation.
- Skills with `metadata.internal: true` are hidden unless `INSTALL_INTERNAL_SKILLS=1` is set.

---

## Lock File

**Path:** `~/.agents/.skill-lock.json`

**Schema:**

```json
{
  "version": 1,
  "skills": {
    "skill-name": {
      "source": "owner/repo",
      "source_type": "github",
      "source_url": "https://github.com/owner/repo.git",
      "skill_path": "skills/skill-name/SKILL.md",
      "skill_folder_hash": "<sha>",
      "installed_at": "2026-03-13T10:00:00Z",
      "updated_at": "2026-03-13T10:00:00Z"
    }
  },
  "last_selected_agents": ["claude-code", "mistral-vibe"]
}
```

The lock file tracks globally installed skills for update checking. Project-level installs are not tracked in the lock file. `last_selected_agents` remembers the user's previous agent selection for convenience.

---

## Installation Flow

```
User runs: ai-setup-forge add owner/repo -a claude-code mistral-vibe

  1. Parse source → ParsedSource(type="github", url="https://github.com/owner/repo.git")
  2. Ensure registry initialized (lazy init on first use)
  3. Clone repo (shallow) → /tmp/skills-XXXX/
  4. Discover skills → [Skill(name="foo"), Skill(name="bar")]
  5. User selects or --skill filter → [Skill(name="foo")]
  6. For skill "foo", agent "claude-code":
     a. Copy /tmp/.../foo/ → .agents/skills/foo/
     b. Symlink .claude/skills/foo → .agents/skills/foo/
  7. For skill "foo", agent "mistral-vibe":
     a. (canonical already exists)
     b. Symlink .vibe/skills/foo → .agents/skills/foo/
  8. Registry: upsert "foo" → installed=1, origin=github, source_url=...
     Insert skill_agents: (foo, claude-code, project), (foo, mistral-vibe, project)
  9. Cleanup /tmp/skills-XXXX/
```

**Copilot CLI special case:** Copilot CLI reads from both `.github/skills/` and `.agents/skills/` at project level. Since the canonical location is already `.agents/skills/`, a project-level install for `github-copilot` does not need an additional symlink (the skill is already discoverable). For global installs, a symlink from `~/.copilot/skills/` to the canonical `~/.agents/skills/` directory is created.

---

## Agent Detection

Each agent is detected by checking for the presence of its config directory:

| Agent | Detection Logic |
|---|---|
| Claude Code | `~/.claude` exists, or `CLAUDE_CONFIG_DIR` env var is set |
| Mistral Vibe | `~/.vibe` exists, or `config.toml` with Vibe config found |
| Copilot CLI | `~/.copilot` exists, or `.github/` in project, or `gh copilot` is available |

If no agents are detected, the CLI prompts the user to select which agents to install for.

---

## Security Considerations

- **Skill name validation**: Names are validated against the official spec: 1-64 chars, lowercase `a-z` + digits + hyphens, no leading/trailing/consecutive hyphens, must match directory name. `sanitize_name()` enforces this for installation; `validate_name()` reports errors for `init`/`validate`.
- **Path traversal prevention**: Sanitized skill names prevent directory traversal. All non-alphanumeric characters are replaced with hyphens, leading/trailing dots/hyphens are stripped.
- **Path validation**: All computed paths are validated to be within expected base directories before any file operations.
- **Temp directory cleanup**: Cloned repos are cleaned up after install, with validation that the path is within `tempfile.gettempdir()`.
- **Git clone timeout**: 60-second timeout on clone operations.
- **No arbitrary code execution**: Skills are Markdown files only; no scripts are executed during installation.
- **Private repos**: Support authenticated cloning via `GITHUB_TOKEN` / `GH_TOKEN` / `gh auth token`. Detect auth errors and provide clear guidance.

---

## Environment Variables

| Variable | Description |
|---|---|
| `INSTALL_INTERNAL_SKILLS` | Set to `1` to show/install internal skills |
| `GITHUB_TOKEN` / `GH_TOKEN` | GitHub API token for higher rate limits and private repos |
| `SKILLS_API_URL` | Override skills.sh registry base URL (default: `https://skills.sh`) |
| `SKILLS_REGISTRY_PATH` | Override local registry DB path (default: `~/.ai-setup-forge/skills_registry.db`) |
| `CLAUDE_CONFIG_DIR` | Override Claude Code config directory (default: `~/.claude`) |
| `COPILOT_SKILLS_DIRS` | Additional skill directories for Copilot CLI |

---

## Dependencies

| Package | Purpose |
|---|---|
| `click` >= 8.1 | CLI framework (commands, options, groups, prompts) |
| `rich` >= 13.0 | Terminal formatting, colors, spinners, tables, interactive prompts |
| `python-frontmatter` >= 1.1 | Parse SKILL.md files (YAML frontmatter + Markdown body). Wraps `pyyaml` internally. |
| `httpx` >= 0.27 | Async HTTP client for GitHub API calls, direct-URL fetching, and registry queries |

> **Note:** `pyyaml` is listed as a transitive dependency of `python-frontmatter`, not a direct dependency. Do not list both.

**Dev dependencies:**

| Package | Purpose |
|---|---|
| `pytest` >= 8.0 | Test runner |
| `ruff` >= 0.4 | Linting and formatting |
| `mypy` >= 1.10 | Static type checking |

---

## Differences from Reference Project

| Aspect | Reference (Node.js) | This Project (Python) |
|---|---|---|
| Language | TypeScript / Node.js | Python 3.10+ |
| Agents supported | 35+ agents | 3 agents (Claude Code, Mistral Vibe, Copilot CLI) |
| Package manager | npm/pnpm | uv / pyproject.toml |
| CLI framework | Manual argv parsing | `click` |
| Terminal UI | `@clack/prompts` + `picocolors` | `rich` |
| Git operations | `simple-git` (npm) | `subprocess` calling `git` directly |
| HTTP client | Native `fetch` | `httpx` |
| Frontmatter parsing | `gray-matter` (npm) | `python-frontmatter` |
| Remote providers | Mintlify, HuggingFace, Well-known | GitHub, GitLab, local, direct-URL only |
| Telemetry | Yes (anonymous) | No |
| Plugin manifest | `.claude-plugin/marketplace.json` | Not supported (future consideration) |
| Lock file version | v3 | v1 (simplified) |
| Skill catalog | No local catalog | SQLite registry at `~/.ai-setup-forge/` with categories, tags, origin |
| Agent definitions | Not managed | `.agent.md` install/remove/registry alongside skills |
| Agent-specific paths | Copilot uses `.agents/skills/` | Copilot uses `.github/skills/` (primary) + `.agents/skills/` (fallback) |

---

## Implementation Phases

### Phase 1 - Core Foundation (Complete)
- Project scaffolding (`pyproject.toml`, package structure, ruff/mypy config)
- `types.py` - Data models (all dataclasses)
- `constants.py` - Shared constants (spec constraints: name max 64 chars, description max 1024, etc.)
- `agents.py` - Agent configs and detection for 3 target agents (with correct paths from official docs)
- `skills.py` - SKILL.md parsing (via `python-frontmatter`) and discovery
- `validator.py` - Validate SKILL.md against Agent Skills spec (name rules, description length, directory name match, etc.)
- `source_parser.py` - Source string parsing (GitHub, GitLab, local, bundled, direct-URL, SSH)
- `init_skill.py` - Scaffold new skill templates (with agent-specific frontmatter)
- Unit tests for above modules

### Phase 2 - Install & Remove (Complete)
- `git_utils.py` - Git clone via subprocess with timeout, auth error detection
- `installer.py` - Full install logic (copy, symlink/junction, path validation, canonical architecture)
- `remover.py` - Remove logic + list installed skills (symlinks, directories, lock file cleanup)
- `skill_lock.py` - Lock file read/write/update
- `cli.py` - CLI entry point with `add`, `remove`, `list` commands
- Bundled skills support (`skills/` directory, `bundled` source keyword)
- Integration tests

### Phase 3 - Find & Registry (Complete)
- `finder.py` - Search bundled skills and skills.sh registry (Complete)
- CLI command: `find` (Complete)
- `registry.py` - Skills & agents registry SQLite database (Complete)
  - Lazy auto-init: create DB, seed categories, sync bundled skills + agent definitions on first use
  - `bundled_skills_map.json` + `bundled_agents_map.json` for category/tag classification
  - `ensure_registry()` called by all commands that need the registry
  - Skills CRUD: `upsert_skill`, `get_skill`, `remove_skill_entry`, `mark_installed`, `mark_uninstalled`, `set_validated`
  - Agent defs CRUD: `upsert_agent_def`, `get_agent_def`, `mark_agent_installed`, `mark_agent_uninstalled`
  - Queries: `list_skills`, `list_agent_defs`, `search_skills`, `search_agent_defs`, `get_stats`
  - Classification: `add_tags`, `remove_tags`, `add_categories`, `remove_categories`, `add_agent_def_tags`, `remove_agent_def_tags`
  - Origin derivation: `derive_origin()` maps `ParsedSource.type` to registry origin
  - Sync: `sync_bundled_skills()`, `sync_bundled_agents()`, `sync_skills_from_dir()`
- CLI commands (Complete):
  - `registry init [--force]` — create/recreate registry DB
  - `registry sync [path] [--origin] [--validate]` — sync skills from directory
  - `registry list [--category] [--tag] [--origin] [--installed] [--not-installed] [--validated] [--format]`
  - `registry show <name>` — detailed skill info
  - `registry search <query>` — search skills by name/description/tags/categories
  - `registry tag/untag <skill> <tags...>` — manage skill tags
  - `registry categorize/uncategorize <skill> <categories...>` — manage categories
  - `registry set-origin <skill> <origin>` — update skill origin
  - `registry remove <skill> [--force]` — remove from registry (not disk)
  - `registry stats` — show statistics
- Integration hooks in existing commands (Complete):
  - `add` → upsert skill + mark installed with proper connection management
  - `remove` → mark uninstalled with proper connection management
  - `validate` → set validated flag with proper connection management
  - `init` → insert with `origin=homemade` with proper connection management
- Tests: `test_registry.py` — 44 tests covering all registry functions

### Phase 4 - Agent Definitions Management (Complete)
- `agent_defs.py` - Agent definition discovery, install, remove (Complete)
  - `discover_agent_defs()` — scan directory for `.agent.md` files with optional name filter
  - `parse_agent_md()` — parse single `.agent.md` file into `AgentDefinition` dataclass
  - `install_agent_def()` — copy to canonical `.agents/agent-definitions/` + symlink/copy to coding tools
  - `find_installed_agent_defs()` — discover installed agent definitions across coding tools
  - `remove_agent_def()` — remove from coding tools + canonical (preserves canonical if agent-filtered)
  - `create_agent_template()` — create new `.agent.md` from `docs/AGENT_TEMPLATE.md`
- `types.py` — Added `AgentDefinition` dataclass, `agents_dir`/`global_agents_dir` to `AgentConfig`
- `constants.py` — Added `AGENT_DEFS_SUBDIR`, `CANONICAL_AGENT_DEFS_DIR`
- `agents.py` — Updated `AGENTS` config with agent definition paths per coding tool
- CLI `agents` command group (Complete, backward-compatible):
  - `agents` (no subcommand) → shows `agents status` (backward compatible)
  - `agents status` — show detected coding tools and their status
  - `agents add <source>` — install agent definitions from bundled/local/GitHub
  - `agents remove [names...]` — remove installed agent definitions (interactive or by name)
  - `agents list` — list installed agent definitions
  - `agents find [query]` — search agent definitions in registry
  - `agents init [name]` — create new agent definition from template
- Registry integration: all commands use proper connection management (open/try/finally close)
- Tests: `test_agent_defs.py` — 22 tests covering discovery, install, remove, find, init, bundled

### Phase 5 - Update & Check (Complete)
- `updater.py` - Check for updates and update installed skills (Complete)
  - `check_for_updates()` — read lock file, compare stored hash with GitHub Trees API / commit SHA
  - `update_skill()` — re-install a skill from its stored source URL
  - `_parse_github_url()` — extract owner/repo from GitHub URLs (HTTPS, SSH, shorthand)
  - `_get_tree_sha()` — fetch tree SHA via GitHub Trees API for path-level change detection
  - `_get_latest_commit_sha()` — fallback: compare latest commit SHA when tree API fails
  - `_get_github_token()` — resolve token from GITHUB_TOKEN/GH_TOKEN/gh CLI
  - `_api_get()` — centralized GitHub API helper returning `(status_code, parsed_json)`, handles JSON decode errors
  - `_describe_api_error()` — maps HTTP status codes to human-readable messages (401, 403, 404, 429, 500+, network)
  - `SkillUpdateInfo`, `CheckResult` dataclasses for structured results
- CLI `check` command — shows table of skills with updates, errors, and up-to-date counts
- CLI `update [skills...]` command — re-installs outdated skills from stored source URLs
  - `--yes` flag to skip confirmation
  - `-a/--agent` to target specific agents
  - Optional skill name arguments to update specific skills only
  - Correctly filters only outdated skills (not all skills) and reports already up-to-date ones
- Bug fixes:
  - Registry `upsert_agent_def()` — `tools` and `target` columns now use `excluded.*` directly instead of `COALESCE`, allowing NULL to clear previously set values
  - `_commit=False` parameter pattern — all registry write functions support deferred commit for bulk operations
- Tests: `test_updater.py` — 18 tests covering URL parsing, check logic, mocked API calls, API error descriptions
- Tests: `test_registry.py` — added `_commit=False` rollback tests, tools/target clearing tests
- Tests: `test_agent_defs.py` — added mcp_servers parsing tests

### Phase 6 - Polish (Complete)
- Lock file robustness
  - Type validation: `skills` must be dict, `last_selected_agents` must be list — invalid types reset to defaults
  - Atomic writes: `write_lock()` writes to `.tmp` file then renames for crash safety
  - Proper `OSError` propagation with temp file cleanup on failure
- Installer hardening
  - Target existence validation before creating symlinks/junctions
  - `InstallError` raised with clear message if target directory missing
- Init skill error handling
  - `mkdir` and `write_text` wrapped in try/except with user-friendly error message
- Git utils improvements
  - Better error messages when stderr is empty (`unknown error` instead of blank)
  - URL included in error messages for context
- Cross-platform installer tests
  - Symlink → copy fallback on non-Windows
  - Windows junction fallback (mocked `sys.platform` + `subprocess.run`)
  - Junction failure → copy fallback
  - Existing symlink/directory replacement
- Bundled skills validation — fixed 9 SKILL.md files (YAML parse errors, name/directory mismatches)
- PyPI publishing ready
  - `pyproject.toml` enriched with classifiers, keywords, project URLs
  - Bundled agents included in wheel via `force-include`
  - `uv build` produces valid `.whl` and `.tar.gz`
  - Publish with: `uv publish`
- Test coverage: 243 tests
  - `update_skill()` — 8 tests covering all error/success paths
  - `search_agent_defs()` — 6 tests covering search by name/description/category/tag
  - Lock file type validation, atomic writes
  - `_create_link` target validation, symlink/junction/copy fallbacks
  - `_commit=False` rollback, tools/target clearing, mcp_servers parsing, API error descriptions

---

## Open Questions / Future Considerations

1. **Vibe `config.toml` integration**: Should the tool update Vibe's `skill_paths` in `config.toml` when installing to a custom location? Or only install to standard paths?
2. **Copilot plugin manifest**: Should the tool generate/update `plugin.json` for plugin-distributed skills?
3. **Claude Code plugin marketplace**: The `.claude-plugin/marketplace.json` format is used for plugin distribution. Should this be supported?
4. **Cross-agent skill validation**: When a skill uses agent-specific frontmatter (e.g. `context: fork` for Claude Code), should the tool warn when installing to an agent that doesn't support that field? (Current design: yes, as a warning during `validate`, not blocking during `add`.)
5. ~~**Skills registry integration**~~: Resolved — integrated via `GET /api/search?q={query}&limit=10`. See `find` command documentation.
6. **Name-directory mismatch resolution**: The spec requires `name` to match the parent directory name. During `add`, if a skill has `name: foo` but lives in `bar/SKILL.md`, should the tool rename the directory to `foo/` or warn and use the existing name?
7. **`allowed-tools` portability**: The spec marks this as experimental. Tool name syntax differs between agents (e.g. Claude Code uses `Bash(git:*)` while Vibe uses `read_file`). Should the tool attempt to translate tool names between agents, or just pass them through?
8. **Progressive disclosure guidance**: Should `validate` warn when `SKILL.md` body exceeds 500 lines or ~5000 tokens, per the spec recommendation?
