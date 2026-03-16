-- Skills Registry - SQLite Schema v1
-- Local inventory of skills and agent definitions for ai-setup-forge
-- Location: ~/.ai-setup-forge/skills_registry.db

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- Core tables
-- ============================================================

-- Skills: the main inventory table
CREATE TABLE IF NOT EXISTS skills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    description   TEXT    NOT NULL DEFAULT '',
    origin        TEXT    NOT NULL DEFAULT 'unknown'
                         CHECK (origin IN ('bundled', 'github', 'gitlab', 'website', 'homemade', 'unknown')),
    source_url    TEXT    DEFAULT NULL,
    author        TEXT    DEFAULT NULL,
    version       TEXT    DEFAULT NULL,
    license       TEXT    DEFAULT NULL,
    installed     INTEGER NOT NULL DEFAULT 0 CHECK (installed IN (0, 1)),
    validated     INTEGER NOT NULL DEFAULT 0 CHECK (validated IN (0, 1)),
    skill_path    TEXT    DEFAULT NULL,
    installed_at  TEXT    DEFAULT NULL,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Categories: classification buckets
CREATE TABLE IF NOT EXISTS categories (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL UNIQUE,
    label TEXT    DEFAULT NULL
);

-- Tags: technical stack and topic labels
CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE
);

-- ============================================================
-- Junction tables (many-to-many)
-- ============================================================

CREATE TABLE IF NOT EXISTS skill_categories (
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (skill_id, category_id)
);

CREATE TABLE IF NOT EXISTS skill_tags (
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (skill_id, tag_id)
);

-- Which agents a skill is installed for
CREATE TABLE IF NOT EXISTS skill_agents (
    skill_id   INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    agent_name TEXT    NOT NULL,
    scope      TEXT    NOT NULL DEFAULT 'project' CHECK (scope IN ('project', 'global')),
    PRIMARY KEY (skill_id, agent_name, scope)
);

-- ============================================================
-- Agent definition tables
-- ============================================================

-- Agent definitions: .agent.md file inventory
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

-- Which coding tools an agent definition is installed for
CREATE TABLE IF NOT EXISTS agent_def_coding_agents (
    agent_def_id      INTEGER NOT NULL REFERENCES agent_definitions(id) ON DELETE CASCADE,
    coding_agent_name TEXT    NOT NULL,
    scope             TEXT    NOT NULL DEFAULT 'project' CHECK (scope IN ('project', 'global')),
    PRIMARY KEY (agent_def_id, coding_agent_name, scope)
);

-- ============================================================
-- Metadata
-- ============================================================

CREATE TABLE IF NOT EXISTS registry_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO registry_meta (key, value) VALUES ('schema_version', '1');
INSERT OR IGNORE INTO registry_meta (key, value)
    VALUES ('created_at', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));

-- ============================================================
-- Triggers
-- ============================================================

-- Auto-update updated_at on any row change
CREATE TRIGGER IF NOT EXISTS trg_skills_updated_at
    AFTER UPDATE ON skills
    FOR EACH ROW
BEGIN
    UPDATE skills SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = OLD.id;
END;

-- Auto-update updated_at on agent_definitions changes
CREATE TRIGGER IF NOT EXISTS trg_agent_defs_updated_at
    AFTER UPDATE ON agent_definitions
    FOR EACH ROW
BEGIN
    UPDATE agent_definitions SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = OLD.id;
END;

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_skills_origin     ON skills(origin);
CREATE INDEX IF NOT EXISTS idx_skills_installed  ON skills(installed);
CREATE INDEX IF NOT EXISTS idx_skills_validated  ON skills(validated);
CREATE INDEX IF NOT EXISTS idx_tags_name         ON tags(name);
CREATE INDEX IF NOT EXISTS idx_categories_name   ON categories(name);
CREATE INDEX IF NOT EXISTS idx_skill_agents_name ON skill_agents(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_defs_origin    ON agent_definitions(origin);
CREATE INDEX IF NOT EXISTS idx_agent_defs_installed ON agent_definitions(installed);
CREATE INDEX IF NOT EXISTS idx_agent_defs_category  ON agent_definitions(category);
CREATE INDEX IF NOT EXISTS idx_agent_def_coding_agents_name ON agent_def_coding_agents(coding_agent_name);

-- ============================================================
-- Seed: default categories
-- ============================================================

INSERT OR IGNORE INTO categories (name, label) VALUES
    ('ai-engineering', 'AI & Machine Learning'),
    ('architecture',   'Software Architecture'),
    ('devops',         'DevOps & Infrastructure'),
    ('web',            'Web Development'),
    ('testing',        'Testing & QA'),
    ('design',         'Software Design'),
    ('marketing',      'Marketing & Growth'),
    ('product',        'Product Management'),
    ('database',       'Database & Data'),
    ('security',       'Security'),
    ('ux',             'UX & UI Design'),
    ('methodology',    'Methodology & Process'),
    ('performance',    'Performance Optimization'),
    ('documentation',  'Documentation'),
    ('refactoring',    'Refactoring & Code Quality'),
    ('orchestrator',   'Orchestration & Planning'),
    ('specialized',    'Specialized Agent');
