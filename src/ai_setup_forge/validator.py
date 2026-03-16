"""Validate SKILL.md files against the Agent Skills specification."""

from __future__ import annotations

import re
from pathlib import Path

from ai_setup_forge.constants import (
    BODY_MAX_LINES_RECOMMENDED,
    COMPATIBILITY_MAX_LENGTH,
    DESCRIPTION_MAX_LENGTH,
    NAME_MAX_LENGTH,
    SKILL_FILE_NAME,
)
from ai_setup_forge.types import ValidationResult

# Compiled pattern: lowercase a-z, digits 0-9, hyphens. No leading/trailing hyphens.
_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_CONSECUTIVE_HYPHENS_RE = re.compile(r"--")

# Known agent-specific (non-portable) frontmatter fields
_AGENT_SPECIFIC_FIELDS = {
    "disable-model-invocation": "Claude Code",
    "argument-hint": "Claude Code",
    "model": "Claude Code",
    "context": "Claude Code",
    "agent": "Claude Code",
    "hooks": "Claude Code",
    "user-invocable": "Claude Code, Mistral Vibe",
}


def validate_name(name: str) -> list[str]:
    """Validate a skill name against the Agent Skills spec. Returns a list of errors."""
    errors: list[str] = []

    if not name:
        errors.append("'name' is required and must not be empty.")
        return errors

    if len(name) > NAME_MAX_LENGTH:
        errors.append(f"'name' must be at most {NAME_MAX_LENGTH} characters (got {len(name)}).")

    if not _NAME_RE.match(name):
        if name != name.lower():
            errors.append("'name' must be lowercase (a-z, 0-9, hyphens only).")
        elif name.startswith("-") or name.endswith("-"):
            errors.append("'name' must not start or end with a hyphen.")
        else:
            errors.append(
                "'name' may only contain lowercase letters (a-z), digits (0-9), and hyphens (-)."
            )

    if _CONSECUTIVE_HYPHENS_RE.search(name):
        errors.append("'name' must not contain consecutive hyphens ('--').")

    return errors


def validate_skill_md(
    skill_dir: Path,
    frontmatter: dict[str, object],
    body: str,
) -> ValidationResult:
    """Validate a parsed SKILL.md against the Agent Skills specification.

    Args:
        skill_dir: The directory containing the SKILL.md file.
        frontmatter: Parsed YAML frontmatter as a dict.
        body: The Markdown body content (after frontmatter).

    Returns:
        ValidationResult with errors, warnings, and info messages.
    """
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    # --- name ---
    name = frontmatter.get("name")
    if name is None:
        errors.append("Missing required field: 'name'.")
    elif not isinstance(name, str):
        errors.append("'name' must be a string.")
    else:
        errors.extend(validate_name(name))
        # Check directory name matches
        dir_name = skill_dir.name
        if dir_name != name:
            warnings.append(
                f"'name' ('{name}') does not match parent directory ('{dir_name}'). "
                "The spec requires these to match."
            )

    # --- description ---
    description = frontmatter.get("description")
    if description is None:
        errors.append("Missing required field: 'description'.")
    elif not isinstance(description, str):
        errors.append("'description' must be a string.")
    elif len(description) == 0:
        errors.append("'description' must not be empty.")
    elif len(description) > DESCRIPTION_MAX_LENGTH:
        errors.append(
            f"'description' must be at most {DESCRIPTION_MAX_LENGTH} characters "
            f"(got {len(description)})."
        )

    # --- license (optional) ---
    license_val = frontmatter.get("license")
    if license_val is not None and not isinstance(license_val, str):
        errors.append("'license' must be a string.")

    # --- compatibility (optional) ---
    compat = frontmatter.get("compatibility")
    if compat is not None:
        if not isinstance(compat, str):
            errors.append("'compatibility' must be a string.")
        elif len(compat) > COMPATIBILITY_MAX_LENGTH:
            errors.append(
                f"'compatibility' must be at most {COMPATIBILITY_MAX_LENGTH} characters "
                f"(got {len(compat)})."
            )

    # --- metadata (optional) ---
    metadata = frontmatter.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            errors.append("'metadata' must be a mapping (key-value pairs).")
        else:
            for k, v in metadata.items():
                if not isinstance(k, str):
                    errors.append(f"metadata key {k!r} must be a string.")
                if not isinstance(v, str):
                    warnings.append(
                        f"metadata value for '{k}' is {type(v).__name__}, spec recommends strings."
                    )

    # --- allowed-tools (optional, experimental) ---
    allowed_tools = frontmatter.get("allowed-tools")
    if allowed_tools is not None:
        if not isinstance(allowed_tools, str):
            warnings.append("'allowed-tools' should be a space-delimited string (experimental).")
        else:
            info.append(
                f"'allowed-tools' declares {len(allowed_tools.split())} tool(s). "
                "Support varies between agents."
            )

    # --- agent-specific field warnings ---
    for field_name, agent in _AGENT_SPECIFIC_FIELDS.items():
        if field_name in frontmatter:
            warnings.append(
                f"'{field_name}' is a non-portable extension ({agent}). "
                "Other agents will ignore this field."
            )

    # --- body content info ---
    body_lines = body.count("\n") + 1 if body.strip() else 0
    if body_lines > BODY_MAX_LINES_RECOMMENDED:
        warnings.append(
            f"SKILL.md body is {body_lines} lines (recommended max: {BODY_MAX_LINES_RECOMMENDED}). "
            "Consider moving detailed content to references/ or assets/."
        )
    elif body_lines == 0:
        info.append("SKILL.md body is empty. Consider adding instructions.")
    else:
        info.append(f"SKILL.md body: {body_lines} lines.")

    # --- check for supporting directories ---
    for subdir in ("scripts", "references", "assets"):
        subdir_path = skill_dir / subdir
        if subdir_path.is_dir():
            count = sum(1 for _ in subdir_path.iterdir())
            info.append(f"Found {subdir}/ directory with {count} item(s).")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        info=info,
    )


def validate_skill_path(path: Path) -> ValidationResult:
    """Validate a skill at a given path (directory or SKILL.md file).

    Convenience wrapper that reads and parses the file, then delegates to validate_skill_md.
    """
    import frontmatter

    if path.is_file() and path.name == SKILL_FILE_NAME:
        skill_file = path
        skill_dir = path.parent
    elif path.is_dir():
        skill_file = path / SKILL_FILE_NAME
        skill_dir = path
    else:
        return ValidationResult(
            valid=False,
            errors=[f"Path '{path}' is not a valid skill directory or SKILL.md file."],
        )

    if not skill_file.exists():
        return ValidationResult(
            valid=False,
            errors=[f"No {SKILL_FILE_NAME} found at '{skill_file}'."],
        )

    try:
        post = frontmatter.load(str(skill_file))
    except Exception as e:
        return ValidationResult(
            valid=False,
            errors=[f"Failed to parse {SKILL_FILE_NAME}: {e}"],
        )

    return validate_skill_md(
        skill_dir=skill_dir,
        frontmatter=dict(post.metadata),
        body=post.content,
    )
