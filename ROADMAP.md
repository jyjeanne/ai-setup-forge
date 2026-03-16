# Roadmap

## Current State -- v0.1.0 (Beta)

AI Setup Forge is feature-complete for its core use cases: installing, removing, searching, validating, and updating agent skills and agent definitions across Claude Code, Mistral Vibe, and GitHub Copilot CLI.

### What's implemented

| Area | Status | Notes |
|---|---|---|
| Skill discovery & parsing | Done | Recursive SKILL.md discovery with frontmatter parsing |
| Multi-agent installation | Done | Canonical storage + symlink/junction/copy per agent |
| Skill removal | Done | Interactive or named, per-agent or all |
| Source parsing | Done | GitHub, GitLab, local dirs, bundled, SSH, direct URLs |
| Git clone with auth | Done | Shallow clone, GITHUB_TOKEN / GH_TOKEN / `gh auth` |
| Lock file tracking | Done | `.skill-lock.json` for update detection |
| Update checking | Done | GitHub Trees API hash comparison |
| Update execution | Done | Re-install outdated skills from stored source |
| Bundled skills (680+) | Done | Curated + imported from skills.sh (Vercel, Anthropic, GitHub, Google) |
| Category-based install | Done | `add bundled -c security` installs all skills in a category |
| Agent definitions (12) | Done | Model-agnostic `.agent.md` discovery, install, remove |
| SQLite registry | Done | Local inventory with categories, tags, search |
| SKILL.md validation | Done | Against Agent Skills spec (agentskills.io) |
| Skill scaffolding | Done | `init` command with agent-specific templates |
| skills.sh search | Done | Remote registry search via API |
| skills.sh import script | Done | Batch import from top repos via `npx skills` |
| CLI (Click + Rich) | Done | Full command set with tables, JSON output, Windows-safe |

---

## v0.2.0 -- Quality & Testing

Focus: harden the tool for public use.

- [ ] **CLI integration tests** -- `test_cli.py` is currently empty; add tests for all commands using Click's `CliRunner`
- [ ] **Windows CI** -- validate symlink/junction fallback on Windows in CI (GitHub Actions `windows-latest`)
- [ ] **Cross-platform path tests** -- ensure GitLab nested groups, Windows `C:\` paths, and SSH URLs all round-trip correctly
- [ ] **Error message audit** -- review all user-facing error messages for clarity and actionability
- [ ] **`--dry-run` flag** -- preview what `add`, `remove`, and `update` would do without making changes
- [ ] **Offline resilience** -- graceful degradation when skills.sh or GitHub API is unreachable

## v0.3.0 -- Registry Enhancements

Focus: make the local registry more useful.

- [ ] **Auto-tagging** -- parse SKILL.md content to suggest tags based on keywords (detect "Java", "Spring", "REST")
- [ ] **FTS5 full-text search** -- replace `LIKE '%query%'` with SQLite FTS5 for better relevance ranking
- [ ] **Registry export/import** -- export to JSON for sharing or backup
- [ ] **Schema migrations** -- versioned migration scripts that run automatically on DB open
- [ ] **Dependency tracking** -- track which skills reference or complement each other

## v0.4.0 -- Ecosystem

Focus: integrate with more tools and sources.

- [ ] **Cursor / Windsurf / Codex agent support** -- extend agent configs for additional coding tools
- [ ] **Private registry support** -- allow organizations to host their own skills registry
- [ ] **Skill versioning** -- semantic versioning with upgrade/downgrade support
- [ ] **Skill composition** -- allow skills to declare dependencies on other skills
- [ ] **`publish` command** -- push a local skill to skills.sh or a private registry
- [ ] **`import` command** -- integrate `scripts/import_skills_sh.py` as a first-class CLI command

## v1.0.0 -- Stable Release

- [ ] **API stability guarantee** -- freeze CLI interface and lock file format
- [ ] **Comprehensive documentation site** -- hosted docs with guides, API reference, examples
- [ ] **Plugin system** -- allow third-party extensions for new agent types or sources
- [ ] **User ratings/notes** -- annotate skills locally with personal notes or ratings
- [ ] **Telemetry (opt-in)** -- anonymous usage stats to prioritize development

---

## Non-Goals

These are explicitly out of scope:

- **Runtime execution** -- this tool manages skill files, it does not execute agent workflows
- **Agent orchestration** -- no multi-agent coordination; each agent reads skills independently
- **Skill authoring IDE** -- `init` and `validate` help, but a full authoring experience is left to editors
