# Skills Registry - Local Database Specification

## Overview

The **Skills Registry** is a local SQLite database that acts as an inventory of all **skills** and **agent definitions** known to the current user's machine. It catalogs them with rich metadata: **category**, **origin**, **technical stack**, **installation status**, and **validation status**.

The registry is **auto-populated with bundled skills and agent definitions on first use** — no manual setup required. All bundled entries start as `installed = 0` (available but not installed). Skills-manager commands (`add`, `remove`, `validate`, `agents add`, `agents remove`) automatically update the registry as a side effect.

---

## Goals

1. **Inventory**: Maintain a local catalog of all available skills with searchable metadata.
2. **Classification**: Organize skills by category, origin, and technical stack.
3. **Status tracking**: Know which skills are installed, for which agents, and whether they passed validation.
4. **Offline-first**: No network required — the database is a local SQLite file.
5. **Zero setup**: Registry auto-initializes and syncs bundled skills on first use of any ai-setup-forge command.
6. **CLI-driven**: Browse and manage the registry via `ai-setup-forge registry` subcommands.

---

## Database Location

```
~/.ai-setup-forge/
└── skills_registry.db
```

The registry is **always user-level** (one per machine), stored at `~/.ai-setup-forge/skills_registry.db`. It is not project-scoped — it tracks all skills the user has ever discovered or installed, regardless of which project they came from.

**Path resolution:**

```python
def get_registry_db_path() -> Path:
    return Path.home() / ".ai-setup-forge" / "skills_registry.db"
```

**Override:** The `SKILLS_REGISTRY_PATH` environment variable overrides the default path (useful for testing).

---

## Lifecycle: Auto-Initialization

The registry uses **lazy initialization**: the database is created automatically on first access by any ai-setup-forge command. There is no required manual setup step.

**On first access (any command):**

1. Check if `~/.ai-setup-forge/skills_registry.db` exists.
2. If not: create directory, create DB with schema, seed categories, sync bundled skills.
3. All bundled skills are inserted with `installed = 0` and `origin = 'bundled'`.

**On subsequent access:**

1. Open existing DB.
2. Optionally check schema version for migrations.

This means that after `pip install ai-setup-forge` (or `uv tool install`), running `ai-setup-forge registry list` immediately shows all 52+ bundled skills — none installed yet.

---

## SQLite Schema

### Entity-Relationship Overview

```
skills ──< skill_categories  >── categories
skills ──< skill_tags         >── tags
skills ──< skill_agents       >── (agent names)
```

A skill can belong to multiple categories, have multiple tags, and be installed for multiple agents.

### Tables

#### `skills` — Core skill inventory

```sql
CREATE TABLE IF NOT EXISTS skills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    description   TEXT    NOT NULL DEFAULT '',
    origin        TEXT    NOT NULL DEFAULT 'unknown'
                         CHECK (origin IN ('bundled', 'github', 'gitlab', 'website', 'homemade', 'unknown')),
    source_url    TEXT    DEFAULT NULL,
    -- e.g. 'https://github.com/owner/repo', NULL for bundled/homemade
    author        TEXT    DEFAULT NULL,
    version       TEXT    DEFAULT NULL,
    license       TEXT    DEFAULT NULL,
    installed     INTEGER NOT NULL DEFAULT 0 CHECK (installed IN (0, 1)),
    -- 0 = not installed (available in catalog only), 1 = installed on disk
    validated     INTEGER NOT NULL DEFAULT 0 CHECK (validated IN (0, 1)),
    -- 0 = not validated or failed, 1 = passed validation
    skill_path    TEXT    DEFAULT NULL,
    -- absolute path to the skill source directory (bundled or cloned)
    installed_at  TEXT    DEFAULT NULL,
    -- ISO 8601 timestamp of when the skill was installed (NULL if never installed)
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
```

#### `categories` — Skill categories

```sql
CREATE TABLE IF NOT EXISTS categories (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL UNIQUE,
    label TEXT    DEFAULT NULL
    -- human-readable label, e.g. 'Web Development'
);
```

#### `skill_categories` — Many-to-many: skills <-> categories

```sql
CREATE TABLE IF NOT EXISTS skill_categories (
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (skill_id, category_id)
);
```

#### `tags` — Technical stack and topic tags

```sql
CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE
);
```

#### `skill_tags` — Many-to-many: skills <-> tags

```sql
CREATE TABLE IF NOT EXISTS skill_tags (
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (skill_id, tag_id)
);
```

#### `skill_agents` — Which agents a skill is installed for

```sql
CREATE TABLE IF NOT EXISTS skill_agents (
    skill_id   INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    agent_name TEXT    NOT NULL,
    -- e.g. 'claude-code', 'mistral-vibe', 'github-copilot'
    scope      TEXT    NOT NULL DEFAULT 'project' CHECK (scope IN ('project', 'global')),
    PRIMARY KEY (skill_id, agent_name, scope)
);
```

This table answers: "For which agents is this skill currently installed, and at which scope?"

#### `registry_meta` — Schema version and metadata

```sql
CREATE TABLE IF NOT EXISTS registry_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO registry_meta (key, value) VALUES ('schema_version', '1');
INSERT OR IGNORE INTO registry_meta (key, value)
    VALUES ('created_at', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
```

### Triggers

```sql
-- Auto-update updated_at on any row change
CREATE TRIGGER IF NOT EXISTS trg_skills_updated_at
    AFTER UPDATE ON skills
    FOR EACH ROW
BEGIN
    UPDATE skills SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = OLD.id;
END;
```

### Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_skills_origin     ON skills(origin);
CREATE INDEX IF NOT EXISTS idx_skills_installed  ON skills(installed);
CREATE INDEX IF NOT EXISTS idx_skills_validated  ON skills(validated);
CREATE INDEX IF NOT EXISTS idx_tags_name         ON tags(name);
CREATE INDEX IF NOT EXISTS idx_categories_name   ON categories(name);
CREATE INDEX IF NOT EXISTS idx_skill_agents_name ON skill_agents(agent_name);
```

---

## Seed Data

### Default Categories

Pre-populated on database creation:

| Name | Label |
|---|---|
| `architecture` | Software Architecture |
| `devops` | DevOps & Infrastructure |
| `web` | Web Development |
| `testing` | Testing & QA |
| `design` | Software Design |
| `marketing` | Marketing & Growth |
| `product` | Product Management |
| `database` | Database & Data |
| `security` | Security |
| `ux` | UX & UI Design |
| `methodology` | Methodology & Process |
| `performance` | Performance Optimization |
| `documentation` | Documentation |
| `refactoring` | Refactoring & Code Quality |

### Bundled Skills Mapping

The mapping of bundled skills to categories and tags is stored in a data file that the sync logic reads:

```
skills-registry/
├── schema.sql                # DDL (tracked in git)
├── bundled_skills_map.json   # category/tag mapping for skills (tracked in git)
└── bundled_agents_map.json   # category/tag mapping for agent definitions (tracked in git)
```

**`bundled_skills_map.json` format:**

```json
{
  "rest-api-design": {
    "categories": ["architecture", "web"],
    "tags": ["rest-api", "openapi"]
  },
  "clean-architecture": {
    "categories": ["architecture", "design"],
    "tags": ["solid", "hexagonal"]
  }
}
```

The sync logic:
1. Discovers skills from `skills/` via `discover_skills()`.
2. Inserts each into `skills` table with `origin='bundled'`, `installed=0`.
3. Looks up the skill name in `bundled_skills_map.json` to apply categories and tags.
4. Skills not in the map get no categories/tags (user can add later via CLI).

**Complete bundled skills mapping:**

| Skill | Categories | Tags |
|---|---|---|
| `rest-api-design` | architecture, web | rest-api, openapi |
| `clean-architecture` | architecture, design | solid, hexagonal |
| `clean-code` | design, refactoring | solid, naming |
| `code-review` | methodology, testing | review |
| `debugging` | methodology | debugging |
| `documentation` | documentation | docs |
| `domain-driven-design` | architecture, design | ddd |
| `java-refactoring` | refactoring | java |
| `microservice-spec` | architecture, devops | microservices |
| `performance-optimization` | performance | profiling |
| `pragmatic-programmer` | methodology, design | best-practices |
| `refactoring-patterns` | refactoring, design | patterns |
| `release-it` | devops, architecture | resilience, deployment |
| `software-design-philosophy` | design | simplicity |
| `spring-boot-scaffold` | web | java, spring |
| `sql-jpa` | database | java, sql, jpa |
| `system-design` | architecture | distributed-systems |
| `unit-testing` | testing | tdd, junit |
| `find-skills` | methodology | ai-setup-forge |
| `blue-ocean-strategy` | marketing, product | strategy |
| `contagious` | marketing | viral, word-of-mouth |
| `continuous-discovery` | product, methodology | user-research |
| `cro-methodology` | marketing, web | conversion |
| `crossing-the-chasm` | marketing, product | adoption |
| `design-everyday-things` | ux, design | usability |
| `design-sprint` | product, methodology | sprint, prototype |
| `drive-motivation` | methodology, product | motivation |
| `high-perf-browser` | web, performance | browser, networking |
| `hooked-ux` | ux, product | engagement, habits |
| `hundred-million-offers` | marketing | pricing, offers |
| `improve-retention` | product, marketing | retention |
| `influence-psychology` | marketing | persuasion |
| `inspired-product` | product | product-management |
| `ios-hig-design` | ux, design | ios, mobile |
| `jobs-to-be-done` | product, methodology | jtbd |
| `lean-startup` | product, methodology | mvp, pivot |
| `lean-ux` | ux, methodology | lean |
| `made-to-stick` | marketing | messaging |
| `microinteractions` | ux, web | animations |
| `mom-test` | product, methodology | user-research, interviews |
| `negotiation` | methodology | negotiation |
| `obviously-awesome` | marketing, product | positioning |
| `one-page-marketing` | marketing | planning |
| `predictable-revenue` | marketing | sales |
| `refactoring-ui` | ux, web | ui, css |
| `scorecard-marketing` | marketing | measurement |
| `storybrand-messaging` | marketing | branding, messaging |
| `ddia-systems` | architecture, database | distributed-systems |
| `top-design` | ux, design | design-thinking |
| `traction-eos` | product, methodology | traction |
| `ux-heuristics` | ux | usability, heuristics |
| `web-typography` | web, ux | typography, css |

---

## Integration with Existing Commands

This is the most critical section. The registry must be updated as a **side effect** of existing ai-setup-forge commands so the inventory stays in sync without requiring users to run separate `registry sync` commands.

### `add` command → registry update

When `ai-setup-forge add <source>` installs a skill:

1. **Ensure registry is initialized** (lazy init).
2. **Upsert the skill** into the `skills` table:
   - `name` from the discovered `Skill.name`.
   - `description` from `Skill.description`.
   - `origin` derived from `ParsedSource.type`:
     - `"bundled"` → `"bundled"`
     - `"github"` → `"github"`
     - `"gitlab"` → `"gitlab"`
     - `"local"` → `"homemade"`
     - `"git"` → `"github"` (most git URLs are GitHub)
     - `"direct-url"` → `"website"`
   - `source_url` from `ParsedSource.url`.
   - `author`, `version`, `license` extracted from `Skill.frontmatter.metadata` if present.
   - `skill_path` set to the canonical install path (`.agents/skills/<name>/`).
3. **Set `installed = 1`** and `installed_at` to current timestamp.
4. **Update `skill_agents`**: insert a row for each agent the skill was installed to, with the scope (`project` or `global`).

**Example flow:**

```
ai-setup-forge add owner/repo -a claude-code mistral-vibe

Registry effect:
  skills:        INSERT/UPDATE "my-skill", origin=github, installed=1, installed_at=now
  skill_agents:  INSERT (my-skill, claude-code, project)
                 INSERT (my-skill, mistral-vibe, project)
```

### `remove` command → registry update

When `ai-setup-forge remove <skill>` removes a skill:

1. **Ensure registry is initialized.**
2. **Delete rows from `skill_agents`** matching the removed agents and scope.
3. **Check if any `skill_agents` rows remain** for this skill.
4. **If no agents remain**: set `installed = 0`, clear `installed_at`.
5. **If agents remain** (e.g., removed from `claude-code` but still installed for `mistral-vibe`): keep `installed = 1`.

**Example flow:**

```
ai-setup-forge remove my-skill -a claude-code

Registry effect:
  skill_agents:  DELETE (my-skill, claude-code, project)
  skills:        installed stays 1 (still installed for mistral-vibe)

ai-setup-forge remove my-skill    # removes from all agents

Registry effect:
  skill_agents:  DELETE all rows for my-skill
  skills:        installed = 0, installed_at = NULL
```

### `validate` command → registry update

When `ai-setup-forge validate <path>` is run:

1. **Ensure registry is initialized.**
2. Parse the skill name from the SKILL.md.
3. If the skill exists in the registry:
   - Set `validated = 1` if validation passed.
   - Set `validated = 0` if validation failed.
4. If the skill does NOT exist in the registry: no update (validate is about checking, not registering).

### `init` command → registry update

When `ai-setup-forge init <name>` creates a new skill:

1. **Ensure registry is initialized.**
2. Insert the skill into the registry with:
   - `origin = 'homemade'`
   - `installed = 0`
   - `validated = 0`
   - `skill_path` set to the created directory.

### `find` command → registry enrichment

When `ai-setup-forge find <query>` searches for skills:

1. **Local results**: Query the registry first (by name, description, tags, categories). These results appear instantly, no network needed.
2. **Remote results**: Query skills.sh registry API as before.
3. Merge results. Registry results show `[local]` tag; remote results show `[skills.sh]` tag.
4. Registry results include the `installed` flag so users see which they already have.

### `list` command → registry enrichment

When `ai-setup-forge list` shows installed skills:

1. Existing behavior: scan canonical + agent directories on disk.
2. **Enrichment**: look up each found skill in the registry to show categories, tags, origin alongside the existing output.

### Summary: which commands write to the registry

| Command | Registry Write | What Changes |
|---|---|---|
| `add` | Yes | upsert skill, `installed=1`, insert `skill_agents` |
| `remove` | Yes | delete `skill_agents`, maybe set `installed=0` |
| `validate` | Yes | set `validated` flag |
| `init` | Yes | insert skill with `origin=homemade` |
| `find` | Read only | queries registry for local matches |
| `list` | Read only | enriches output with registry metadata |
| `registry *` | Yes | direct registry management |

---

## CLI Commands

All registry commands are under the `ai-setup-forge registry` subcommand group.

### `registry init`

Force (re-)initialize the registry database. Normally not needed since auto-init handles this.

```bash
ai-setup-forge registry init              # create DB + seed + sync bundled (if not exists)
ai-setup-forge registry init --force       # drop and recreate from scratch
```

**Behavior:**
1. If DB exists and `--force` not set: print "Registry already initialized" and exit.
2. If `--force`: drop all tables, recreate schema, re-seed categories, re-sync bundled skills.
3. Create `~/.ai-setup-forge/` directory if needed.
4. Create all tables, seed categories.
5. Sync bundled skills with `installed = 0`.
6. Apply category/tag mapping from `bundled_skills_map.json`.

### `registry sync`

Scan a skills directory and populate the registry with discovered skills.

```bash
ai-setup-forge registry sync                           # re-sync bundled skills/ folder
ai-setup-forge registry sync ./my-skills               # scan a custom directory
ai-setup-forge registry sync --origin homemade ./path  # override origin
ai-setup-forge registry sync --validate                 # also validate each skill
```

**Options:**

| Flag | Description |
|---|---|
| `--origin` | Override origin for scanned skills (default: auto-detect from path) |
| `--validate` | Run validation on each skill and update `validated` field |

**Behavior:**
1. Discover all skills in the target directory (reuse `discover_skills()`).
2. For each skill:
   - If already in DB (by name): update `description`, `skill_path`, `author`, `version`, `license`, `updated_at`. Do NOT change `installed` or `origin` (user may have overridden).
   - If new: insert with `origin`, `description`, `skill_path`, `installed=0`.
   - Extract `author`, `version`, `license` from frontmatter `metadata` dict.
3. Auto-detect origin: if path is under bundled `skills/` → `bundled`; otherwise → `unknown`.
4. Apply category/tag mapping from `bundled_skills_map.json` if syncing bundled skills.
5. If `--validate`: run `validate_skill_path()` on each and set `validated` flag.

### `registry list`

List skills in the registry with optional filters.

```bash
ai-setup-forge registry list                          # all skills
ai-setup-forge registry list --category architecture  # by category
ai-setup-forge registry list --tag java               # by tech stack
ai-setup-forge registry list --origin bundled          # by origin
ai-setup-forge registry list --installed               # installed only
ai-setup-forge registry list --not-installed            # not installed only
ai-setup-forge registry list --validated                # validated only
ai-setup-forge registry list --format json              # JSON output
```

**Options:**

| Flag | Description |
|---|---|
| `--category` | Filter by category name (repeatable) |
| `--tag` | Filter by tag name (repeatable) |
| `--origin` | Filter by origin |
| `--installed` | Show only installed skills |
| `--not-installed` | Show only not-installed skills |
| `--validated` | Show only validated skills |
| `--format` | Output format: `table` (default), `json` |

**Output:** Rich table with columns: Name, Categories, Tags, Origin, Installed, Validated.

### `registry show <name>`

Show detailed information about a specific skill.

```bash
ai-setup-forge registry show clean-architecture
```

**Output:**
```
Name:         clean-architecture
Description:  Structure software around the Dependency Rule...
Categories:   architecture, design
Tags:         solid, hexagonal
Origin:       bundled
Author:       wondelai
Version:      1.0.0
License:      MIT
Installed:    Yes
  Agents:     claude-code (project), mistral-vibe (project)
Validated:    Yes
Path:         /path/to/skills/clean-architecture
Installed at: 2026-03-13T10:00:00Z
Created:      2026-03-13T10:00:00Z
Updated:      2026-03-13T14:30:00Z
```

### `registry tag <skill> <tags...>`

Add tags to a skill. Creates tags that don't exist yet.

```bash
ai-setup-forge registry tag spring-boot-scaffold java spring rest-api
ai-setup-forge registry tag clean-code python javascript
```

### `registry untag <skill> <tags...>`

Remove tags from a skill.

```bash
ai-setup-forge registry untag clean-code naming
```

### `registry categorize <skill> <categories...>`

Assign categories to a skill. Creates categories that don't exist yet.

```bash
ai-setup-forge registry categorize spring-boot-scaffold web devops
```

### `registry uncategorize <skill> <categories...>`

Remove categories from a skill.

```bash
ai-setup-forge registry uncategorize spring-boot-scaffold devops
```

### `registry set-origin <skill> <origin>`

Update the origin of a skill.

```bash
ai-setup-forge registry set-origin my-custom-skill homemade
ai-setup-forge registry set-origin imported-skill github
```

Valid origins: `bundled`, `github`, `gitlab`, `website`, `homemade`, `unknown`.

### `registry remove <skill>`

Remove a skill entry from the registry entirely (deletes from DB, does NOT uninstall from disk).

```bash
ai-setup-forge registry remove old-unused-skill
ai-setup-forge registry remove old-skill --force   # no confirmation
```

Use `ai-setup-forge remove` to uninstall from disk. Use `ai-setup-forge registry remove` to forget a skill from the catalog.

### `registry stats`

Show registry statistics.

```bash
ai-setup-forge registry stats
```

**Output:**
```
Skills Registry Statistics
  Total skills:      52
  Installed:         12
  Not installed:     40
  Validated:         48

  By origin:
    bundled:         50
    github:           1
    homemade:          1

  By category:
    architecture:     8
    marketing:       12
    product:          9
    ux:               8
    methodology:     11
    ...

  Top tags:
    java:             3
    spring:           1
    ddd:              1
    ...
```

### `registry search <query>`

Search skills in the registry by name, description, tags, or categories.

```bash
ai-setup-forge registry search "api"
ai-setup-forge registry search "java"
ai-setup-forge registry search "marketing"
```

**Behavior:** Search across `name`, `description`, tag names, and category names using `LIKE '%query%'`. Returns matching skills sorted by name.

---

## Module Structure

```
src/ai_setup_forge/
├── registry.py          # Database operations (init, CRUD, queries)
└── ...

skills-registry/
├── schema.sql               # DDL script (tracked in git)
├── bundled_skills_map.json  # category/tag mapping for bundled skills (tracked in git)
└── bundled_agents_map.json  # category/tag mapping for bundled agent definitions (tracked in git)
```

The actual `skills_registry.db` lives at `~/.ai-setup-forge/skills_registry.db` (gitignored, user-local).

### `registry.py` — Key Functions

```python
# Lazy init (called by every command that needs registry)
def ensure_registry(db_path: Path | None = None) -> sqlite3.Connection:
    """Open the registry, creating and seeding it if it doesn't exist."""

# Database lifecycle
def init_db(db_path: Path, force: bool = False) -> None: ...
def get_connection(db_path: Path) -> sqlite3.Connection: ...
def get_registry_db_path() -> Path: ...

# Sync
def sync_skills(conn, source_dir: Path, origin: str = "auto", validate: bool = False) -> SyncResult: ...
def sync_bundled_skills(conn) -> SyncResult: ...

# CRUD
def upsert_skill(conn, name, description, origin, **kwargs) -> int: ...
def get_skill(conn, name) -> dict | None: ...
def remove_skill_entry(conn, name) -> bool: ...
def list_skills(conn, *, category=None, tag=None, origin=None, installed=None, validated=None) -> list[dict]: ...
def search_skills(conn, query: str) -> list[dict]: ...

# Install tracking (called by add/remove commands)
def mark_installed(conn, skill_name: str, agents: list[str], scope: str) -> None: ...
def mark_uninstalled(conn, skill_name: str, agents: list[str] | None, scope: str) -> None: ...
def set_validated(conn, skill_name: str, valid: bool) -> None: ...

# Classification
def add_tags(conn, skill_name: str, tags: list[str]) -> None: ...
def remove_tags(conn, skill_name: str, tags: list[str]) -> None: ...
def add_categories(conn, skill_name: str, categories: list[str]) -> None: ...
def remove_categories(conn, skill_name: str, categories: list[str]) -> None: ...
def set_origin(conn, skill_name: str, origin: str) -> None: ...

# Stats
def get_stats(conn) -> dict: ...
```

### `SyncResult` dataclass

```python
@dataclass
class SyncResult:
    added: int
    updated: int
    errors: list[str]
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `SKILLS_REGISTRY_PATH` | Override registry DB path (default: `~/.ai-setup-forge/skills_registry.db`) |

---

## Design Decisions

1. **Lazy auto-init**: The registry creates itself on first use. No `registry init` required. This ensures bundled skills are immediately available after install.
2. **User-level, not project-level**: The registry is a machine-wide inventory at `~/.ai-setup-forge/`. Skills can be installed at project or global scope, but the catalog is always user-level.
3. **SQLite over JSON**: The lock file (`.skill-lock.json`) tracks install provenance. The registry is a richer catalog with multi-column filtering, many-to-many relationships, and full-text search — SQLite is the right tool.
4. **Mapping file for bundled skills**: `bundled_skills_map.json` is a versioned data file. Adding or reclassifying bundled skills means editing JSON, not code.
5. **`installed` is derived from `skill_agents`**: A skill is `installed=1` when it has at least one `skill_agents` row. The `installed` column is a denormalized flag for fast filtering; the `skill_agents` table is the source of truth for which agents.
6. **Commands as registry writers**: Every command that changes skill state on disk also updates the registry. The user never needs to manually sync after `add`/`remove`.
7. **`updated_at` trigger**: A SQLite trigger auto-updates `updated_at` on any row change, so callers don't need to remember.
8. **Separate from lock file**: The registry tracks discovery and classification. The lock file tracks install provenance (source URL, hash) for update detection. They serve different purposes.

---

## Future Considerations

1. **Auto-tagging**: Parse SKILL.md body content to suggest tags based on keywords (detect "Java", "Spring", "REST").
2. **Export/import**: Export registry to JSON for sharing or backup.
3. **Rating/notes**: Allow users to rate or annotate skills locally.
4. **Dependency tracking**: Track which skills reference or complement each other (e.g., `clean-architecture` → `domain-driven-design`).
5. **Schema migrations**: When schema version changes, run migration scripts automatically on DB open.
6. **FTS5 full-text search**: Replace `LIKE` queries with SQLite FTS5 for better search performance and relevance ranking.
