"""CLI entry point for ai-setup-forge."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ai_setup_forge import __version__
from ai_setup_forge.agents import AGENTS, detect_installed_agents, get_all_agent_names
from ai_setup_forge.validator import validate_skill_path

console = Console()

AGENT_NAMES = get_all_agent_names()

VALID_ORIGINS = ("bundled", "github", "gitlab", "website", "homemade", "unknown")


@click.group()
@click.version_option(version=__version__, prog_name="ai-setup-forge")
def cli() -> None:
    """Manage agent skills and definitions for Claude Code, Mistral Vibe, and Copilot CLI."""


def _resolve_agents(agents: tuple[str, ...], yes: bool) -> list[str]:
    """Resolve agent selection from CLI flags, detection, or prompt."""
    if agents:
        if "*" in agents:
            return list(AGENTS.keys())
        unknown = [a for a in agents if a not in AGENTS]
        if unknown:
            console.print(f"[red]Unknown agent(s): {', '.join(unknown)}[/]")
            console.print(f"[dim]Available: {', '.join(AGENTS.keys())}[/]")
            raise SystemExit(1)
        return list(agents)

    # Auto-detect
    detected = detect_installed_agents()
    if detected:
        if yes:
            return detected
        console.print(f"[dim]Detected agents:[/] {', '.join(detected)}")
        if click.confirm("Install for these agents?", default=True):
            return detected

    # Fallback: prompt
    console.print("[dim]Available agents:[/]")
    for i, name in enumerate(AGENT_NAMES, 1):
        config = AGENTS[name]
        console.print(f"  {i}. {config.display_name} ({name})")

    choices = click.prompt(
        "Select agents (comma-separated numbers or names)",
        default="1,2,3",
    )
    selected = []
    for part in choices.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(AGENT_NAMES):
                selected.append(AGENT_NAMES[idx])
        elif part in AGENTS:
            selected.append(part)

    return selected or list(AGENTS.keys())



# =========================================================================
# Skill commands
# =========================================================================

@cli.command()
@click.argument("source", required=True)
@click.option("-g", "--global", "is_global", is_flag=True, help="Install to user directory.")
@click.option(
    "-a", "--agent", "agents", multiple=True,
    help="Target agents (claude-code, mistral-vibe, github-copilot, or *).",
)
@click.option("-s", "--skill", "skills", multiple=True, help="Specific skills to install.")
@click.option("-c", "--category", "categories", multiple=True, help="Install all skills in a category (e.g. security, devops, web).")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompts.")
@click.option("--all", "install_all", is_flag=True, help="Install all skills to all agents.")
@click.option(
    "--mode", type=click.Choice(["symlink", "copy"]), default="symlink",
    help="Installation mode.",
)
def add(
    source: str,
    is_global: bool,
    agents: tuple[str, ...],
    skills: tuple[str, ...],
    categories: tuple[str, ...],
    yes: bool,
    install_all: bool,
    mode: str,
) -> None:
    """Install skills from a source."""
    from ai_setup_forge.git_utils import GitError, cleanup_clone, shallow_clone
    from ai_setup_forge.installer import install_skill
    from ai_setup_forge.registry import derive_origin, ensure_registry, mark_installed, upsert_skill
    from ai_setup_forge.skill_lock import add_skill_entry
    from ai_setup_forge.skills import discover_skills, filter_skills
    from ai_setup_forge.source_parser import parse_source

    # 1. Parse source
    parsed = parse_source(source)
    console.print(f"[dim]Source:[/] {parsed.type} -> {parsed.url}")

    # 2. Get the skill directory
    clone_dir = None
    skill_source_dir: Path | None = None
    if parsed.type in ("local", "bundled"):
        skill_source_dir = parsed.local_path
        if parsed.type == "bundled" and skill_source_dir and skill_source_dir.is_dir():
            console.print(f"[dim]Bundled skills dir:[/] {skill_source_dir}")
    elif parsed.type == "direct-url":
        console.print("[yellow]Direct URL install not yet supported.[/]")
        raise SystemExit(1)
    else:
        # Clone remote repo
        with console.status("[bold]Cloning repository..."):
            try:
                clone_dir = shallow_clone(parsed.url, ref=parsed.ref)
            except GitError as e:
                console.print(f"[red]Error:[/] {e}")
                raise SystemExit(1)
        skill_source_dir = clone_dir

    try:
        # Validate source directory exists
        if not skill_source_dir or not skill_source_dir.is_dir():
            console.print(f"[red]Error:[/] Directory not found: {parsed.url}")
            raise SystemExit(1)

        # 3. Discover skills
        discovered = discover_skills(
            skill_source_dir,
            subpath=parsed.subpath,
            full_depth=True,
        )

        if not discovered:
            console.print("[yellow]No skills found in source.[/]")
            raise SystemExit(1)

        # 4. Filter by category (using bundled_skills_map.json)
        if categories:
            from ai_setup_forge.skills import _get_category_skill_names
            cat_names = _get_category_skill_names(list(categories))
            if not cat_names:
                console.print(f"[yellow]No skills found for category: {', '.join(categories)}[/]")
                raise SystemExit(1)
            discovered = [s for s in discovered if s.name in cat_names]
            if not discovered:
                console.print(f"[yellow]No matching skills found for category: {', '.join(categories)}[/]")
                raise SystemExit(1)
            console.print(f"[dim]Category filter:[/] {', '.join(categories)} ({len(discovered)} skills)")

        # 5. Filter by skill name
        if parsed.skill_filter:
            discovered = filter_skills(discovered, [parsed.skill_filter])
        elif skills:
            if "*" not in skills:
                discovered = filter_skills(discovered, list(skills))

        if not discovered:
            console.print("[yellow]No matching skills found.[/]")
            raise SystemExit(1)

        # 5. Show discovered skills and confirm
        console.print(f"\n[bold]Found {len(discovered)} skill(s):[/]")
        for s in discovered:
            console.print(f"  * [cyan]{s.name}[/] - {s.description}")

        if not yes and not install_all:
            if not click.confirm("\nInstall these skills?", default=True):
                console.print("[dim]Cancelled.[/]")
                return

        # 6. Resolve agents
        if install_all:
            target_agents = list(AGENTS.keys())
        else:
            target_agents = _resolve_agents(agents, yes)

        if not target_agents:
            console.print("[yellow]No agents selected.[/]")
            return

        console.print(f"\n[dim]Installing for:[/] {', '.join(target_agents)}")

        # 7. Install each skill
        scope = "global" if is_global else "project"
        origin = derive_origin(parsed.type)

        for skill in discovered:
            console.print(f"\n[bold]Installing {skill.name}...[/]")
            results = install_skill(skill, target_agents, is_global=is_global, mode=mode)

            for r in results:
                agent = r["agent"]
                status = r["status"]
                if status == "ok":
                    method = r.get("method", "")
                    console.print(f"  [green]OK[/] {agent} ({method}) -> {r['path']}")
                elif status == "error":
                    console.print(f"  [red]FAIL[/] {agent}: {r.get('message', 'unknown error')}")

            # 8. Update registry
            try:
                conn = ensure_registry()
                try:
                    upsert_skill(
                        conn, name=skill.name, description=skill.description,
                        origin=origin, source_url=parsed.url,
                    )
                    mark_installed(conn, skill.name, target_agents, scope, parsed.url, origin)
                finally:
                    conn.close()
            except Exception as exc:
                console.print(f"[dim]Registry warning: {exc}[/]")

            # Update lock file for global installs
            if is_global:
                add_skill_entry(
                    skill_name=skill.name,
                    source=source,
                    source_type=parsed.type,
                    source_url=parsed.url,
                    skill_path=parsed.subpath,
                )

        console.print(f"\n[green]Done![/] Skills installed ({scope} scope).")

    finally:
        # 9. Cleanup
        if clone_dir:
            cleanup_clone(clone_dir)


@cli.command(name="list")
@click.option("-g", "--global", "is_global", is_flag=True, help="List global skills.")
@click.option("-a", "--agent", "agents", multiple=True, help="Filter by agent.")
def list_skills(is_global: bool, agents: tuple[str, ...]) -> None:
    """List installed skills."""
    from ai_setup_forge.remover import find_installed_skills

    agent_filter = list(agents) if agents else None
    installed = find_installed_skills(is_global=is_global, agent_names=agent_filter)

    if not installed:
        scope = "global" if is_global else "project"
        console.print(f"[dim]No {scope} skills installed.[/]")
        return

    table = Table(title="Installed Skills")
    table.add_column("Skill", style="cyan")
    table.add_column("Agents", style="dim")

    for name, skill_agents in sorted(installed.items()):
        table.add_row(name, ", ".join(skill_agents) if skill_agents else "[dim]canonical only[/]")

    console.print(table)


@cli.command()
@click.argument("skills", nargs=-1)
@click.option("-g", "--global", "is_global", is_flag=True, help="Remove from global scope.")
@click.option("-a", "--agent", "agents", multiple=True, help="Remove from specific agents.")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
@click.option("--all", "remove_all", is_flag=True, help="Remove all skills.")
def remove(
    skills: tuple[str, ...],
    is_global: bool,
    agents: tuple[str, ...],
    yes: bool,
    remove_all: bool,
) -> None:
    """Remove installed skills."""
    from ai_setup_forge.registry import ensure_registry, mark_uninstalled
    from ai_setup_forge.remover import find_installed_skills, remove_skill
    from ai_setup_forge.skill_lock import remove_skill_entry

    agent_filter = list(agents) if agents else None

    # Find what's installed
    installed = find_installed_skills(is_global=is_global, agent_names=agent_filter)

    if not installed:
        console.print("[dim]No skills found to remove.[/]")
        return

    # Determine which skills to remove
    if remove_all:
        to_remove = list(installed.keys())
    elif skills:
        to_remove = [s for s in skills if s in installed]
        not_found = [s for s in skills if s not in installed]
        if not_found:
            console.print(f"[yellow]Not found:[/] {', '.join(not_found)}")
        if not to_remove:
            console.print("[dim]Nothing to remove.[/]")
            return
    else:
        # Interactive selection
        console.print("[bold]Installed skills:[/]")
        skill_names = sorted(installed.keys())
        for i, name in enumerate(skill_names, 1):
            skill_agents = installed[name]
            agents_str = f" ({', '.join(skill_agents)})" if skill_agents else ""
            console.print(f"  {i}. [cyan]{name}[/]{agents_str}")

        choices = click.prompt(
            "Select skills to remove (comma-separated numbers or names)",
        )
        to_remove = []
        for part in choices.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(skill_names):
                    to_remove.append(skill_names[idx])
            elif part in installed:
                to_remove.append(part)

    if not to_remove:
        console.print("[dim]Nothing selected.[/]")
        return

    # Confirm
    console.print(f"\n[bold]Will remove:[/] {', '.join(to_remove)}")
    if not yes and not click.confirm("Continue?", default=True):
        console.print("[dim]Cancelled.[/]")
        return

    scope = "global" if is_global else "project"

    # Remove
    for skill_name in to_remove:
        results = remove_skill(
            skill_name,
            agent_names=agent_filter,
            is_global=is_global,
        )
        if results:
            for r in results:
                console.print(f"  [red]FAIL[/] Removed {skill_name} from {r['agent']}")
        else:
            console.print(f"  [dim]{skill_name}: nothing to remove[/]")

        # Update registry
        try:
            conn = ensure_registry()
            try:
                mark_uninstalled(conn, skill_name, agent_filter, scope)
            finally:
                conn.close()
        except Exception as exc:
            console.print(f"[dim]Registry warning: {exc}[/]")

        # Update lock file for global removes
        if is_global:
            remove_skill_entry(skill_name)

    console.print(f"\n[green]Done![/] Removed {len(to_remove)} skill(s).")


@cli.command()
@click.argument("query", required=False)
@click.option("--registry", "remote", is_flag=True, help="Search skills.sh registry only.")
@click.option("--bundled", "bundled_only", is_flag=True, help="Show bundled skills only.")
def find(query: str | None, remote: bool, bundled_only: bool) -> None:
    """Search for skills from bundled library and skills.sh registry."""
    from ai_setup_forge.finder import search_all, search_bundled, search_registry

    if remote and bundled_only:
        console.print("[red]Cannot use --registry and --bundled together.[/]")
        raise SystemExit(1)

    # Determine which sources to search
    if remote:
        if not query:
            console.print("[yellow]--registry requires a search query.[/]")
            raise SystemExit(1)
        with console.status("[bold]Searching skills.sh..."):
            results = search_registry(query)
    elif bundled_only:
        results = search_bundled(query)
    else:
        if query:
            with console.status("[bold]Searching..."):
                results = search_all(query)
        else:
            results = search_all(None)

    if not results:
        if query:
            console.print(f"[dim]No skills found for \"{query}\".[/]")
        else:
            console.print("[dim]No bundled skills available.[/]")
        return

    # Display results
    table = Table(title="Skills" if not query else f"Results for \"{query}\"")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="dim", max_width=50)
    table.add_column("Source", style="dim")
    table.add_column("Installs", justify="right", style="dim")
    table.add_column("Install Command", style="green")

    for r in results:
        origin_tag = f"[bold magenta]{r.origin}[/]" if r.origin == "bundled" else r.source
        installs_str = f"{r.installs:,}" if r.installs > 0 else ""
        desc = r.description[:80] + "..." if len(r.description) > 80 else r.description
        table.add_row(r.name, desc, origin_tag, installs_str, r.install_cmd)

    console.print(table)

    # Show skills.sh links for registry results
    registry_results = [r for r in results if r.origin == "registry" and r.slug]
    if registry_results:
        console.print(f"\n[dim]Browse at:[/] https://skills.sh/")


@cli.command()
def check() -> None:
    """Check if installed skills have updates available."""
    from ai_setup_forge.updater import check_for_updates

    with console.status("[bold]Checking for updates..."):
        result = check_for_updates()

    if not result.skills:
        console.print("[dim]No globally installed skills to check (lock file empty).[/]")
        console.print("[dim]Only globally installed skills (add -g) are tracked for updates.[/]")
        return

    if result.outdated:
        table = Table(title=f"Updates Available ({len(result.outdated)})")
        table.add_column("Skill", style="cyan")
        table.add_column("Source", style="dim")
        table.add_column("Current", style="dim")
        table.add_column("Remote", style="dim")

        for s in result.outdated:
            table.add_row(
                s.name,
                s.source_url,
                s.current_hash[:12] if s.current_hash else "-",
                s.remote_hash[:12] if s.remote_hash else "-",
            )
        console.print(table)
        console.print(f"\nRun [bold]ai-setup-forge update[/] to update all.")
    else:
        console.print("[green]All skills are up to date.[/]")

    if result.up_to_date:
        console.print(f"[dim]{len(result.up_to_date)} skill(s) up to date.[/]")

    if result.errors:
        console.print(f"\n[yellow]{len(result.errors)} skill(s) could not be checked:[/]")
        for s in result.errors:
            console.print(f"  [dim]{s.name}:[/] {s.error}")


@cli.command()
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
@click.option("-a", "--agent", "agents", multiple=True, help="Target specific agents.")
@click.argument("skills", nargs=-1)
def update(yes: bool, agents: tuple[str, ...], skills: tuple[str, ...]) -> None:
    """Update installed skills to latest versions."""
    from ai_setup_forge.updater import check_for_updates, update_skill

    # Check for updates first
    with console.status("[bold]Checking for updates..."):
        result = check_for_updates()

    if not result.skills:
        console.print("[dim]No globally installed skills to update.[/]")
        return

    # Filter to specific skills if requested
    if skills:
        requested = set(skills)
        to_update = [s for s in result.outdated if s.name in requested]
        not_found = requested - {s.name for s in result.skills}
        if not_found:
            console.print(f"[yellow]Not found in lock file:[/] {', '.join(not_found)}")
        up_to_date = requested - not_found - {s.name for s in to_update}
        if up_to_date:
            console.print(f"[dim]Already up to date:[/] {', '.join(up_to_date)}")
    else:
        to_update = result.outdated

    if not to_update:
        console.print("[green]All skills are up to date.[/]")
        return

    console.print(f"\n[bold]Will update {len(to_update)} skill(s):[/]")
    for s in to_update:
        console.print(f"  * [cyan]{s.name}[/] ({s.source_url})")

    if not yes:
        if not click.confirm("\nContinue?", default=True):
            console.print("[dim]Cancelled.[/]")
            return

    agent_names = list(agents) if agents else None
    success = 0
    failed = 0

    for info in to_update:
        console.print(f"\n[bold]Updating {info.name}...[/]")
        result_dict = update_skill(info.name, agent_names=agent_names)

        if result_dict["status"] == "ok":
            install_results = result_dict.get("install_results", [])
            for r in install_results:
                if r.get("status") == "ok":
                    console.print(f"  [green]OK[/] {r['agent']} -> {r['path']}")
            success += 1
        else:
            console.print(f"  [red]FAIL[/] {result_dict.get('message', 'unknown error')}")
            failed += 1

    console.print(f"\n[green]Done![/] {success} updated, {failed} failed.")


@cli.command()
@click.argument("name", required=False)
@click.option("-a", "--agent", help="Generate agent-specific frontmatter.")
def init(name: str | None, agent: str | None) -> None:
    """Create a new SKILL.md template."""
    from ai_setup_forge.init_skill import create_skill_template
    from ai_setup_forge.registry import ensure_registry, upsert_skill

    result_path = create_skill_template(name=name, agent=agent)

    # Register in registry as homemade
    if result_path:
        skill_name = name or result_path.parent.name
        try:
            conn = ensure_registry()
            try:
                upsert_skill(conn, skill_name, "", "homemade", skill_path=str(result_path.parent))
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            console.print(f"[dim]Registry warning: {exc}[/]")


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def validate(path: str) -> None:
    """Validate a SKILL.md against the Agent Skills specification."""
    from ai_setup_forge.registry import ensure_registry, set_validated
    from ai_setup_forge.skills import parse_skill_md

    result = validate_skill_path(Path(path))

    if result.errors:
        for err in result.errors:
            console.print(f"  [red]ERROR[/]  {err}")

    if result.warnings:
        for warn in result.warnings:
            console.print(f"  [yellow]WARN[/]   {warn}")

    if result.info:
        for info_msg in result.info:
            console.print(f"  [dim]INFO[/]   {info_msg}")

    if result.valid:
        console.print("\n[green]Skill is valid.[/]")
    else:
        console.print(f"\n[red]Validation failed with {len(result.errors)} error(s).[/]")
        raise SystemExit(1)

    # Update registry validated flag
    target = Path(path)
    skill_dir = target if target.is_dir() else target.parent
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        skill = parse_skill_md(skill_md)
        if skill:
            try:
                conn = ensure_registry()
                try:
                    set_validated(conn, skill.name, result.valid)
                finally:
                    conn.close()
            except Exception as exc:
                console.print(f"[dim]Registry warning: {exc}[/]")


@cli.group(invoke_without_command=True)
@click.pass_context
def agents(ctx: click.Context) -> None:
    """Manage agent definitions (.agent.md files)."""
    if ctx.invoked_subcommand is None:
        # Default: show status (backward compatible)
        ctx.invoke(agents_status)


@agents.command(name="status")
def agents_status() -> None:
    """Show detected coding tools and their status."""
    detected = detect_installed_agents()

    table = Table(title="Coding Tools")
    table.add_column("Agent", style="cyan")
    table.add_column("CLI Name", style="dim")
    table.add_column("Status")
    table.add_column("Skills Path", style="dim")
    table.add_column("Agents Path", style="dim")
    table.add_column("Global Skills", style="dim")

    for name, config in AGENTS.items():
        status = "[green]detected[/]" if name in detected else "[dim]not found[/]"
        table.add_row(
            config.display_name,
            config.name,
            status,
            config.skills_dir,
            config.agents_dir,
            str(config.global_skills_dir),
        )

    console.print(table)


@agents.command(name="add")
@click.argument("source", required=True)
@click.option("-g", "--global", "is_global", is_flag=True, help="Install to user directory.")
@click.option(
    "-a", "--agent", "coding_agents", multiple=True,
    help="Target coding tools (claude-code, mistral-vibe, github-copilot, or *).",
)
@click.option("-s", "--select", "selections", multiple=True, help="Specific agent definitions to install.")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompts.")
@click.option("--all", "install_all", is_flag=True, help="Install all agent definitions to all coding tools.")
@click.option(
    "--mode", type=click.Choice(["symlink", "copy"]), default="symlink",
    help="Installation mode.",
)
def agents_add(
    source: str,
    is_global: bool,
    coding_agents: tuple[str, ...],
    selections: tuple[str, ...],
    yes: bool,
    install_all: bool,
    mode: str,
) -> None:
    """Install agent definitions from a source."""
    from ai_setup_forge.agent_defs import (
        _get_bundled_agents_dir,
        discover_agent_defs,
        install_agent_def,
    )
    from ai_setup_forge.git_utils import GitError, cleanup_clone, shallow_clone
    from ai_setup_forge.registry import (
        derive_origin,
        ensure_registry,
        mark_agent_installed,
        upsert_agent_def,
    )
    from ai_setup_forge.source_parser import parse_source

    # 1. Parse source
    parsed = parse_source(source)
    console.print(f"[dim]Source:[/] {parsed.type} -> {parsed.url}")

    # 2. Get the agent definitions directory
    clone_dir = None
    source_dir: Path | None = None

    if parsed.type == "bundled":
        source_dir = _get_bundled_agents_dir()
        console.print(f"[dim]Bundled agents dir:[/] {source_dir}")
    elif parsed.type == "local":
        source_dir = parsed.local_path
    elif parsed.type == "direct-url":
        console.print("[yellow]Direct URL install not yet supported.[/]")
        raise SystemExit(1)
    else:
        with console.status("[bold]Cloning repository..."):
            try:
                clone_dir = shallow_clone(parsed.url, ref=parsed.ref)
            except GitError as e:
                console.print(f"[red]Error:[/] {e}")
                raise SystemExit(1)
        source_dir = clone_dir

    try:
        if not source_dir or not source_dir.is_dir():
            console.print(f"[red]Error:[/] Directory not found: {parsed.url}")
            raise SystemExit(1)

        # 3. Discover agent definitions
        name_filter = list(selections) if selections else None
        if parsed.skill_filter and not name_filter:
            name_filter = [parsed.skill_filter]

        discovered = discover_agent_defs(source_dir, names=name_filter)

        if not discovered:
            console.print("[yellow]No agent definitions found in source.[/]")
            raise SystemExit(1)

        # 4. Show discovered and confirm
        console.print(f"\n[bold]Found {len(discovered)} agent definition(s):[/]")
        for ad in discovered:
            console.print(f"  * [cyan]{ad.name}[/] - {ad.description}")

        if not yes and not install_all:
            if not click.confirm("\nInstall these agent definitions?", default=True):
                console.print("[dim]Cancelled.[/]")
                return

        # 5. Resolve coding tools
        if install_all:
            target_agents = list(AGENTS.keys())
        else:
            target_agents = _resolve_agents(coding_agents, yes)

        if not target_agents:
            console.print("[yellow]No coding tools selected.[/]")
            return

        console.print(f"\n[dim]Installing for:[/] {', '.join(target_agents)}")

        # 6. Install each agent definition
        scope = "global" if is_global else "project"
        origin = derive_origin(parsed.type)

        for ad in discovered:
            console.print(f"\n[bold]Installing {ad.name}...[/]")
            results = install_agent_def(ad, target_agents, is_global=is_global, mode=mode)

            for r in results:
                agent = r["agent"]
                status = r["status"]
                if status == "ok":
                    method = r.get("method", "")
                    console.print(f"  [green]OK[/] {agent} ({method}) -> {r['path']}")
                elif status == "error":
                    console.print(f"  [red]FAIL[/] {agent}: {r.get('message', 'unknown error')}")

            # 7. Update registry
            try:
                conn = ensure_registry()
                try:
                    upsert_agent_def(
                        conn, name=ad.name, description=ad.description,
                        origin=origin, source_url=parsed.url,
                        model=ad.model, version=ad.version, category=ad.category,
                        tools=ad.tools, target=ad.target,
                    )
                    mark_agent_installed(conn, ad.name, target_agents, scope)
                finally:
                    conn.close()
            except Exception as exc:
                console.print(f"[dim]Registry warning: {exc}[/]")

        console.print(f"\n[green]Done![/] Agent definitions installed ({scope} scope).")

    finally:
        if clone_dir:
            cleanup_clone(clone_dir)


@agents.command(name="list")
@click.option("-g", "--global", "is_global", is_flag=True, help="List global agent definitions.")
@click.option("-a", "--agent", "coding_agents", multiple=True, help="Filter by coding tool.")
def agents_list(is_global: bool, coding_agents: tuple[str, ...]) -> None:
    """List installed agent definitions."""
    from ai_setup_forge.agent_defs import find_installed_agent_defs

    agent_filter = list(coding_agents) if coding_agents else None
    installed = find_installed_agent_defs(is_global=is_global, agent_names=agent_filter)

    if not installed:
        scope = "global" if is_global else "project"
        console.print(f"[dim]No {scope} agent definitions installed.[/]")
        return

    table = Table(title="Installed Agent Definitions")
    table.add_column("Agent Definition", style="cyan")
    table.add_column("Coding Tools", style="dim")

    for name, tools in sorted(installed.items()):
        table.add_row(name, ", ".join(tools) if tools else "[dim]canonical only[/]")

    console.print(table)


@agents.command(name="remove")
@click.argument("names", nargs=-1)
@click.option("-g", "--global", "is_global", is_flag=True, help="Remove from global scope.")
@click.option("-a", "--agent", "coding_agents", multiple=True, help="Remove from specific coding tools.")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
@click.option("--all", "remove_all", is_flag=True, help="Remove all agent definitions.")
def agents_remove(
    names: tuple[str, ...],
    is_global: bool,
    coding_agents: tuple[str, ...],
    yes: bool,
    remove_all: bool,
) -> None:
    """Remove installed agent definitions."""
    from ai_setup_forge.agent_defs import find_installed_agent_defs, remove_agent_def
    from ai_setup_forge.registry import ensure_registry, mark_agent_uninstalled

    agent_filter = list(coding_agents) if coding_agents else None
    installed = find_installed_agent_defs(is_global=is_global, agent_names=agent_filter)

    if not installed:
        console.print("[dim]No agent definitions found to remove.[/]")
        return

    if remove_all:
        to_remove = list(installed.keys())
    elif names:
        to_remove = [n for n in names if n in installed]
        not_found = [n for n in names if n not in installed]
        if not_found:
            console.print(f"[yellow]Not found:[/] {', '.join(not_found)}")
        if not to_remove:
            console.print("[dim]Nothing to remove.[/]")
            return
    else:
        # Interactive selection
        console.print("[bold]Installed agent definitions:[/]")
        def_names = sorted(installed.keys())
        for i, name in enumerate(def_names, 1):
            tools = installed[name]
            tools_str = f" ({', '.join(tools)})" if tools else ""
            console.print(f"  {i}. [cyan]{name}[/]{tools_str}")

        choices = click.prompt(
            "Select agent definitions to remove (comma-separated numbers or names)",
        )
        to_remove = []
        for part in choices.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(def_names):
                    to_remove.append(def_names[idx])
            elif part in installed:
                to_remove.append(part)

    if not to_remove:
        console.print("[dim]Nothing selected.[/]")
        return

    console.print(f"\n[bold]Will remove:[/] {', '.join(to_remove)}")
    if not yes and not click.confirm("Continue?", default=True):
        console.print("[dim]Cancelled.[/]")
        return

    scope = "global" if is_global else "project"

    for def_name in to_remove:
        results = remove_agent_def(def_name, agent_names=agent_filter, is_global=is_global)
        if results:
            for r in results:
                console.print(f"  [red]FAIL[/] Removed {def_name} from {r['agent']}")
        else:
            console.print(f"  [dim]{def_name}: nothing to remove[/]")

        try:
            conn = ensure_registry()
            try:
                mark_agent_uninstalled(conn, def_name, agent_filter, scope)
            finally:
                conn.close()
        except Exception as exc:
            console.print(f"[dim]Registry warning: {exc}[/]")

    console.print(f"\n[green]Done![/] Removed {len(to_remove)} agent definition(s).")


@agents.command(name="find")
@click.argument("query", required=False)
@click.option("--category", default=None, help="Filter by category.")
@click.option("--tag", default=None, help="Filter by tag.")
@click.option("--installed", "show_installed", is_flag=True, help="Show installed only.")
def agents_find(
    query: str | None,
    category: str | None,
    tag: str | None,
    show_installed: bool,
) -> None:
    """Search agent definitions in the registry."""
    from ai_setup_forge.registry import (
        ensure_registry,
        list_agent_defs,
        search_agent_defs,
    )

    conn = ensure_registry()
    try:
        if query:
            results = search_agent_defs(conn, query)
        else:
            results = list_agent_defs(
                conn,
                category=category,
                tag=tag,
                installed=True if show_installed else None,
            )

        if not results:
            if query:
                console.print(f"[dim]No agent definitions found for \"{query}\".[/]")
            else:
                console.print("[dim]No agent definitions match the filters.[/]")
            return

        title = f"Agent Definitions: \"{query}\"" if query else f"Agent Definitions ({len(results)})"
        table = Table(title=title)
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="dim", max_width=40)
        table.add_column("Category", style="dim")
        table.add_column("Tags", style="dim")
        table.add_column("Origin", style="dim")
        table.add_column("Inst.", justify="center")

        for ad in results:
            desc = ad["description"]
            if len(desc) > 60:
                desc = desc[:60] + "..."
            tags = ", ".join(ad.get("tags", []))
            inst = "[green]Yes[/]" if ad["installed"] else "[dim]No[/]"
            table.add_row(
                ad["name"], desc, ad.get("category") or "-", tags, ad["origin"], inst,
            )

        console.print(table)
    finally:
        conn.close()


@agents.command(name="init")
@click.argument("name", required=False)
def agents_init(name: str | None) -> None:
    """Create a new agent definition from template."""
    from ai_setup_forge.agent_defs import create_agent_template
    from ai_setup_forge.registry import ensure_registry, upsert_agent_def

    result_path = create_agent_template(name=name)

    if result_path is None:
        if name and (Path.cwd() / f"{name}.agent.md").exists():
            console.print(f"[yellow]{name}.agent.md already exists.[/]")
        else:
            console.print("[red]Could not create agent template (template file not found).[/]")
        return

    console.print(f"[green]Created[/] {result_path}")

    # Register in registry as homemade
    agent_name = name or "my-agent"
    try:
        conn = ensure_registry()
        try:
            upsert_agent_def(conn, agent_name, "", "homemade", agent_path=str(result_path))
        finally:
            conn.close()
    except Exception as exc:
        console.print(f"[dim]Registry warning: {exc}[/]")


# =========================================================================
# Registry command group
# =========================================================================

@cli.group()
def registry() -> None:
    """Manage the local skills registry."""


@registry.command(name="init")
@click.option("--force", is_flag=True, help="Drop and recreate from scratch.")
def registry_init(force: bool) -> None:
    """Force (re-)initialize the registry database."""
    from ai_setup_forge.registry import (
        ensure_registry,
        get_registry_db_path,
        init_db,
        sync_bundled_agents,
        sync_bundled_skills,
    )

    db_path = get_registry_db_path()

    if db_path.is_file() and not force:
        console.print(f"[dim]Registry already initialized at {db_path}[/]")
        console.print("[dim]Use --force to recreate.[/]")
        return

    if force:
        conn = init_db(db_path, force=True)
        sr = sync_bundled_skills(conn)
        ar = sync_bundled_agents(conn)
        conn.close()
        console.print(f"[green]Registry recreated.[/] {sr.added} skills, {ar.added} agents synced.")
    else:
        conn = ensure_registry(db_path)
        count = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        agent_count = conn.execute("SELECT COUNT(*) FROM agent_definitions").fetchone()[0]
        conn.close()
        console.print(f"[green]Registry initialized.[/] {count} skills, {agent_count} agents.")


@registry.command(name="sync")
@click.argument("path", default="", required=False)
@click.option("--origin", default=None, help="Override origin for scanned skills.")
@click.option("--validate", "do_validate", is_flag=True, help="Validate each skill.")
def registry_sync(path: str, origin: str | None, do_validate: bool) -> None:
    """Sync a skills directory into the registry."""
    from ai_setup_forge.registry import ensure_registry, sync_bundled_skills, sync_skills_from_dir

    conn = ensure_registry()

    if not path:
        # Re-sync bundled
        result = sync_bundled_skills(conn)
        console.print(f"[green]Synced bundled skills:[/] {result.added} added, {result.updated} updated.")
    else:
        source_dir = Path(path).resolve()
        if not source_dir.is_dir():
            console.print(f"[red]Directory not found:[/] {path}")
            raise SystemExit(1)
        result = sync_skills_from_dir(
            conn, source_dir, origin=origin or "unknown", validate=do_validate,
        )
        console.print(
            f"[green]Synced:[/] {result.added} added, {result.updated} updated."
        )
        if result.errors:
            for err in result.errors:
                console.print(f"  [red]Error:[/] {err}")

    conn.close()


@registry.command(name="list")
@click.option("--category", default=None, help="Filter by category.")
@click.option("--tag", default=None, help="Filter by tag.")
@click.option("--origin", default=None, help="Filter by origin.")
@click.option("--installed", "show_installed", is_flag=True, help="Show installed only.")
@click.option("--not-installed", "show_not_installed", is_flag=True, help="Show not installed only.")
@click.option("--validated", "show_validated", is_flag=True, help="Show validated only.")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def registry_list(
    category: str | None,
    tag: str | None,
    origin: str | None,
    show_installed: bool,
    show_not_installed: bool,
    show_validated: bool,
    fmt: str,
) -> None:
    """List skills in the registry."""
    from ai_setup_forge.registry import ensure_registry, list_skills as reg_list

    conn = ensure_registry()

    installed_filter = None
    if show_installed:
        installed_filter = True
    elif show_not_installed:
        installed_filter = False

    results = reg_list(
        conn,
        category=category,
        tag=tag,
        origin=origin,
        installed=installed_filter,
        validated=True if show_validated else None,
    )

    if fmt == "json":
        console.print(json.dumps([{
            "name": s["name"], "description": s["description"],
            "origin": s["origin"], "installed": bool(s["installed"]),
            "validated": bool(s["validated"]),
            "categories": s.get("categories", []),
            "tags": s.get("tags", []),
        } for s in results], indent=2))
        conn.close()
        return

    if not results:
        console.print("[dim]No skills match the filters.[/]")
        conn.close()
        return

    table = Table(title=f"Registry ({len(results)} skills)")
    table.add_column("Name", style="cyan")
    table.add_column("Categories", style="dim")
    table.add_column("Tags", style="dim")
    table.add_column("Origin", style="dim")
    table.add_column("Inst.", justify="center")
    table.add_column("Valid.", justify="center")

    for s in results:
        cats = ", ".join(s.get("categories", []))
        tags = ", ".join(s.get("tags", []))
        inst = "[green]Yes[/]" if s["installed"] else "[dim]No[/]"
        valid = "[green]Yes[/]" if s["validated"] else "[dim]No[/]"
        table.add_row(s["name"], cats, tags, s["origin"], inst, valid)

    console.print(table)
    conn.close()


@registry.command(name="show")
@click.argument("name")
def registry_show(name: str) -> None:
    """Show detailed info for a skill."""
    from ai_setup_forge.registry import ensure_registry, get_skill

    conn = ensure_registry()
    skill = get_skill(conn, name)

    if not skill:
        console.print(f"[red]Skill not found:[/] {name}")
        conn.close()
        raise SystemExit(1)

    console.print(f"[bold]Name:[/]         {skill['name']}")
    console.print(f"[bold]Description:[/]  {skill['description']}")
    console.print(f"[bold]Categories:[/]   {', '.join(skill.get('categories', [])) or '-'}")
    console.print(f"[bold]Tags:[/]         {', '.join(skill.get('tags', [])) or '-'}")
    console.print(f"[bold]Origin:[/]       {skill['origin']}")
    if skill.get("author"):
        console.print(f"[bold]Author:[/]       {skill['author']}")
    if skill.get("version"):
        console.print(f"[bold]Version:[/]      {skill['version']}")
    if skill.get("license"):
        console.print(f"[bold]License:[/]      {skill['license']}")
    inst = "Yes" if skill["installed"] else "No"
    console.print(f"[bold]Installed:[/]    {inst}")
    if skill.get("agents"):
        agents_str = ", ".join(
            f"{a['agent_name']} ({a['scope']})" for a in skill["agents"]
        )
        console.print(f"  [bold]Agents:[/]     {agents_str}")
    valid = "Yes" if skill["validated"] else "No"
    console.print(f"[bold]Validated:[/]    {valid}")
    if skill.get("skill_path"):
        console.print(f"[bold]Path:[/]         {skill['skill_path']}")
    if skill.get("installed_at"):
        console.print(f"[bold]Installed at:[/] {skill['installed_at']}")
    console.print(f"[bold]Created:[/]      {skill['created_at']}")
    console.print(f"[bold]Updated:[/]      {skill['updated_at']}")
    conn.close()


@registry.command(name="search")
@click.argument("query")
def registry_search(query: str) -> None:
    """Search skills by name, description, tags, or categories."""
    from ai_setup_forge.registry import ensure_registry, search_skills

    conn = ensure_registry()
    results = search_skills(conn, query)

    if not results:
        console.print(f"[dim]No results for \"{query}\".[/]")
        conn.close()
        return

    table = Table(title=f"Search: \"{query}\" ({len(results)} results)")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="dim", max_width=40)
    table.add_column("Origin", style="dim")
    table.add_column("Inst.", justify="center")

    for s in results:
        desc = s["description"][:60] + "..." if len(s["description"]) > 60 else s["description"]
        inst = "[green]Yes[/]" if s["installed"] else "[dim]No[/]"
        table.add_row(s["name"], desc, s["origin"], inst)

    console.print(table)
    conn.close()


@registry.command(name="tag")
@click.argument("skill")
@click.argument("tags", nargs=-1, required=True)
def registry_tag(skill: str, tags: tuple[str, ...]) -> None:
    """Add tags to a skill."""
    from ai_setup_forge.registry import add_tags, ensure_registry

    conn = ensure_registry()
    add_tags(conn, skill, list(tags))
    conn.commit()
    console.print(f"[green]Tagged[/] {skill} with: {', '.join(tags)}")
    conn.close()


@registry.command(name="untag")
@click.argument("skill")
@click.argument("tags", nargs=-1, required=True)
def registry_untag(skill: str, tags: tuple[str, ...]) -> None:
    """Remove tags from a skill."""
    from ai_setup_forge.registry import ensure_registry, remove_tags

    conn = ensure_registry()
    remove_tags(conn, skill, list(tags))
    console.print(f"[green]Untagged[/] {skill}: {', '.join(tags)}")
    conn.close()


@registry.command(name="categorize")
@click.argument("skill")
@click.argument("categories", nargs=-1, required=True)
def registry_categorize(skill: str, categories: tuple[str, ...]) -> None:
    """Assign categories to a skill."""
    from ai_setup_forge.registry import add_categories, ensure_registry

    conn = ensure_registry()
    add_categories(conn, skill, list(categories))
    conn.commit()
    console.print(f"[green]Categorized[/] {skill}: {', '.join(categories)}")
    conn.close()


@registry.command(name="uncategorize")
@click.argument("skill")
@click.argument("categories", nargs=-1, required=True)
def registry_uncategorize(skill: str, categories: tuple[str, ...]) -> None:
    """Remove categories from a skill."""
    from ai_setup_forge.registry import ensure_registry, remove_categories

    conn = ensure_registry()
    remove_categories(conn, skill, list(categories))
    console.print(f"[green]Uncategorized[/] {skill}: {', '.join(categories)}")
    conn.close()


@registry.command(name="set-origin")
@click.argument("skill")
@click.argument("origin")
def registry_set_origin(skill: str, origin: str) -> None:
    """Update the origin of a skill."""
    from ai_setup_forge.registry import ensure_registry, set_origin

    if origin not in VALID_ORIGINS:
        console.print(f"[red]Invalid origin:[/] {origin}")
        console.print(f"[dim]Valid: {', '.join(VALID_ORIGINS)}[/]")
        raise SystemExit(1)

    conn = ensure_registry()
    set_origin(conn, skill, origin)
    console.print(f"[green]Origin set:[/] {skill} -> {origin}")
    conn.close()


@registry.command(name="remove")
@click.argument("skill")
@click.option("--force", is_flag=True, help="No confirmation.")
def registry_remove(skill: str, force: bool) -> None:
    """Remove a skill entry from the registry (does NOT uninstall from disk)."""
    from ai_setup_forge.registry import ensure_registry, remove_skill_entry

    if not force:
        if not click.confirm(f"Remove '{skill}' from registry?", default=False):
            console.print("[dim]Cancelled.[/]")
            return

    conn = ensure_registry()
    removed = remove_skill_entry(conn, skill)
    if removed:
        console.print(f"[green]Removed[/] {skill} from registry.")
    else:
        console.print(f"[yellow]Not found:[/] {skill}")
    conn.close()


@registry.command(name="stats")
def registry_stats() -> None:
    """Show registry statistics."""
    from ai_setup_forge.registry import ensure_registry, get_stats

    conn = ensure_registry()
    stats = get_stats(conn)
    conn.close()

    s = stats["skills"]
    ad = stats["agent_definitions"]

    console.print("[bold]Skills Registry Statistics[/]")
    console.print(f"  Total skills:      {s['total']}")
    console.print(f"  Installed:         {s['installed']}")
    console.print(f"  Not installed:     {s['not_installed']}")
    console.print(f"  Validated:         {s['validated']}")

    if s["by_origin"]:
        console.print("\n  [bold]By origin:[/]")
        for origin, count in sorted(s["by_origin"].items()):
            console.print(f"    {origin}:  {count}")

    if s["by_category"]:
        console.print("\n  [bold]By category:[/]")
        for cat, count in list(s["by_category"].items())[:10]:
            console.print(f"    {cat}:  {count}")

    if s["top_tags"]:
        console.print("\n  [bold]Top tags:[/]")
        for tag, count in list(s["top_tags"].items())[:10]:
            console.print(f"    {tag}:  {count}")

    if ad["total"] > 0:
        console.print(f"\n[bold]Agent Definitions[/]")
        console.print(f"  Total:             {ad['total']}")
        console.print(f"  Installed:         {ad['installed']}")
        console.print(f"  Not installed:     {ad['not_installed']}")
