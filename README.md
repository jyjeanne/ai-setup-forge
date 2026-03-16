# AI Setup Forge

A package manager for AI agent skills and agent definitions. Install, remove, search, and update reusable instruction sets across **Claude Code**, **Mistral Vibe**, and **GitHub Copilot CLI**.

Skills are `SKILL.md` files following the open [Agent Skills specification](https://agentskills.io/specification). Agent definitions are `.agent.md` files that define custom AI agent profiles. This tool manages both.

**680+ bundled skills** across 16 categories and **12 bundled agent definitions** included out of the box. Includes popular skills from [skills.sh](https://skills.sh) (Vercel, Anthropic, GitHub, Google, and more).

## Install

### Prerequisites

- **Python 3.10+** -- [python.org](https://www.python.org/) or your system package manager
- **uv** (recommended) -- [docs.astral.sh/uv](https://docs.astral.sh/uv/)
- **git** -- required for cloning skill repos
- At least one supported coding tool: Claude Code, Mistral Vibe, or GitHub Copilot CLI

### Linux / macOS

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install ai-setup-forge as a global tool
uv tool install ai-setup-forge

# Or from source
git clone https://github.com/jyjeanne/ai-setup-forge.git
cd ai-setup-forge
uv tool install -e .
```

Skills are installed using symlinks by default. No special permissions needed.

### Windows

```powershell
# 1. Install uv (if not already installed)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Install ai-setup-forge as a global tool
uv tool install ai-setup-forge

# Or from source
git clone https://github.com/jyjeanne/ai-setup-forge.git
cd ai-setup-forge
uv tool install -e .
```

On Windows, skills are installed using directory junctions (no admin rights needed). If junctions fail, the tool automatically falls back to file copies. Use `--mode copy` to force copies.

### Verify installation

```bash
ai-setup-forge --version
ai-setup-forge agents status
```

## Quick Start

```bash
# Install skills from a GitHub repo
ai-setup-forge add owner/repo

# Install a specific skill
ai-setup-forge add owner/repo@my-skill

# Install all bundled skills
ai-setup-forge add bundled

# Install all skills in a category
ai-setup-forge add bundled -c security
ai-setup-forge add bundled -c devops -c web

# Install bundled agent definitions
ai-setup-forge agents add bundled

# Import more skills from skills.sh
python scripts/import_skills_sh.py

# Search for skills
ai-setup-forge find typescript

# List what's installed
ai-setup-forge list

# Check for updates
ai-setup-forge check
```

## Getting Started

### Step 1: Install ai-setup-forge

See the [Install](#install) section above for Linux/macOS and Windows instructions.

### Step 2: Check which coding tools are detected

```bash
ai-setup-forge agents status
```

This will show which of Claude Code, Mistral Vibe, and GitHub Copilot CLI are installed on your machine.

### Step 3: Install skills to your project

Pick one of the approaches below depending on what you need:

```bash
# Install all security skills for all detected agents
ai-setup-forge add bundled -c security -y

# Install a curated set of categories
ai-setup-forge add bundled -c web -c testing -c architecture -y

# Install a single specific skill
ai-setup-forge add bundled -s clean-architecture -y

# Install everything (all 680+ skills, all agents)
ai-setup-forge add bundled --all
```

### Step 4: Install agent definitions (optional)

Agent definitions give your coding tool specialized personas (architect, test generator, etc.):

```bash
# Install all 12 bundled agent definitions
ai-setup-forge agents add bundled -y

# Or pick specific ones
ai-setup-forge agents add bundled -s architect -s docs-agent -y
```

### Step 5: Verify installation

```bash
# List installed skills
ai-setup-forge list

# List installed agent definitions
ai-setup-forge agents list
```

### Using with Claude Code

Skills are installed to `.claude/skills/` in your project (or `~/.claude/skills/` with `-g`). Claude Code automatically discovers them. Agent definitions go to `.claude/agents/`.

```bash
# Project-level (current directory)
ai-setup-forge add bundled -c web -a claude-code -y
ai-setup-forge agents add bundled -a claude-code -y

# Global (available in all projects)
ai-setup-forge add bundled -c architecture -a claude-code -g -y
```

### Using with GitHub Copilot CLI

Skills are installed to `.github/skills/` in your project (or `~/.copilot/skills/` with `-g`). Copilot also reads from `.agents/skills/` directly.

```bash
ai-setup-forge add bundled -c testing -a github-copilot -y
ai-setup-forge agents add bundled -a github-copilot -y
```

### Using with Mistral Vibe

Skills are installed to `.vibe/skills/` in your project (or `~/.vibe/skills/` with `-g`).

```bash
ai-setup-forge add bundled -c devops -a mistral-vibe -y
ai-setup-forge agents add bundled -a mistral-vibe -y
```

### Using with all agents at once

```bash
# Install to all detected agents simultaneously
ai-setup-forge add bundled -c security -a '*' -y
ai-setup-forge agents add bundled -a '*' -y
```

## Commands

### Skills

| Command | Description |
|---|---|
| `add <source>` | Install skills from GitHub, GitLab, local directory, or bundled |
| `remove [name]` | Remove installed skills (interactive if no name given) |
| `list` | List installed skills |
| `find [query]` | Search bundled skills and skills.sh registry |
| `check` | Check globally installed skills for updates |
| `update [name]` | Update outdated skills |
| `init [name]` | Scaffold a new SKILL.md from template |
| `validate [path]` | Validate a SKILL.md against the spec |

### Agent Definitions

| Command | Description |
|---|---|
| `agents status` | Show detected coding tools (default) |
| `agents add <source>` | Install agent definitions (supports `bundled`) |
| `agents remove [name]` | Remove agent definitions |
| `agents list` | List installed agent definitions |
| `agents find [query]` | Search for agent definitions |
| `agents init [name]` | Scaffold a new .agent.md |

### Registry

A local SQLite database tracking all known skills with categories, tags, and install status.

| Command | Description |
|---|---|
| `registry list` | List all skills in the registry |
| `registry search <query>` | Search by name, description, tags |
| `registry show <name>` | Detailed info about a skill |
| `registry tag <skill> <tags...>` | Add tags to a skill |
| `registry categorize <skill> <cats...>` | Assign categories |
| `registry stats` | Registry statistics |
| `registry sync [path]` | Sync a directory into the registry |

## Supported Sources

| Source | Example |
|---|---|
| GitHub shorthand | `owner/repo` |
| GitHub with filter | `owner/repo@skill-name` |
| GitHub URL | `https://github.com/owner/repo` |
| GitLab URL | `https://gitlab.com/group/repo` |
| Local directory | `./local-skills` |
| Bundled | `bundled` |
| SSH | `git@github.com:owner/repo.git` |

## How It Works

1. Skills are copied to `.agents/skills/<name>/` (canonical location)
2. Symlinks (or junctions on Windows) are created in each agent's skills directory
3. Each agent discovers the skill through its standard path

| Agent | Project Skills Path | Global Skills Path |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Mistral Vibe | `.vibe/skills/` | `~/.vibe/skills/` |
| Copilot CLI | `.github/skills/` | `~/.copilot/skills/` |

## Common Flags

| Flag | Description |
|---|---|
| `-g, --global` | Install/list at user level instead of project |
| `-a, --agent` | Target specific agent (`claude-code`, `mistral-vibe`, `github-copilot`, `*`) |
| `-s, --skill` | Filter by skill name |
| `-c, --category` | Install all skills in a category (e.g. `security`, `devops`, `web`) |
| `-y, --yes` | Skip confirmation prompts |
| `--all` | Apply to all skills/agents |
| `--mode` | `symlink` (default) or `copy` |

## Bundled Skill Categories

| Category | Skills | Topics |
|---|---|---|
| `web` | 317 | React, Next.js, Vue, Svelte, Node.js, Express, GraphQL, CSS, Tailwind |
| `devops` | 201 | Docker, Kubernetes, Terraform, CI/CD, AWS, Azure, GCP, monitoring |
| `ai-engineering` | 169 | LLM, RAG, LangChain, prompt engineering, fine-tuning, embeddings |
| `testing` | 128 | Playwright, Selenium, Jest, Vitest, Cypress, QA planning, E2E |
| `database` | 96 | PostgreSQL, MongoDB, Redis, Prisma, Neon, Supabase, SQL optimization |
| `methodology` | 82 | Code review, git conventions, technical debt, agile, best practices |
| `design` | 63 | Software design, SOLID principles, design patterns, clean code |
| `architecture` | 59 | Clean architecture, DDD, microservices, CQRS, event-driven |
| `documentation` | 48 | API docs, ADRs, changelogs, onboarding guides, README |
| `security` | 43 | OWASP, JWT, CSRF, XSS, RBAC, secret scanning, vulnerability audit |
| `performance` | 29 | Browser performance, bundle optimization, caching, profiling |
| `marketing` | 14 | Growth strategy, positioning, retention, content |
| `product` | 13 | Lean startup, jobs-to-be-done, discovery, design sprint |
| `ux` | 9 | Usability heuristics, accessibility, responsive design |
| `mobile` | 7 | React Native, Expo, iOS, Android, push notifications |
| `refactoring` | 3 | Refactoring patterns, legacy code modernization |

## Bundled Agent Definitions

12 model-agnostic agent definitions included:

| Agent | Role |
|---|---|
| `architect` | Plans and delegates work to specialized subagents |
| `principal-software-engineer` | Engineering guidance on design, clean code, testing |
| `implementation-plan` | Generates structured implementation plans |
| `docs-agent` | Technical writer for project documentation |
| `playwright-test-generator` | Creates Playwright browser tests |
| `playwright-test-healer` | Debugs and fixes failing Playwright tests |
| `playwright-test-planner` | Creates comprehensive test plans |
| `flaky-test-hunter` | Identifies and fixes intermittent test failures |
| `test-refactor-specialist` | Improves test code quality and structure |
| `api-tester-specialist` | API testing with REST Assured, Supertest |
| `selenium-test-executor` | Runs and analyzes Selenium test suites |
| `selenium-test-specialist` | Creates Selenium tests with POM pattern |

## Importing More Skills

Use the import script to pull popular skills from [skills.sh](https://skills.sh):

```bash
# Import from top repos (Vercel, Anthropic, GitHub, Google, etc.)
python scripts/import_skills_sh.py

# Preview without importing
python scripts/import_skills_sh.py --dry-run
```

You can also add repos to the `SOURCES` list in the script, or use `npx skills` directly:

```bash
# Search skills.sh
npx skills find react

# Add a specific repo's skills
npx skills add owner/repo -a claude-code -y
```

## Development

```bash
git clone https://github.com/jyjeanne/ai-setup-forge.git
cd ai-setup-forge
uv sync
uv run pytest
uv run ruff check src/
uv run mypy src/
```

## Environment Variables

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` / `GH_TOKEN` | GitHub token for private repos |
| `SKILLS_API_URL` | Override skills.sh registry URL |
| `SKILLS_REGISTRY_PATH` | Override local registry DB path |

## License

MIT
