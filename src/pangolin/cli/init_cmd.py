"""Implementation of the `pangolin init` command.

Scaffolds a new pangolin project in the target directory by copying the
bundled project template and creating the runtime data folders declared in
config/data_structure.yaml. The data/ folder is git-ignored by the generated
.gitignore: folders are created on disk but never committed.
"""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

import typer
import yaml

from pangolin.cli._docgen import render_readme

TEMPLATE_PACKAGE = "pangolin._scaffold"
TEMPLATE_DIR_NAME = "project_template"

# Template files stored under a neutral name (dotfiles would be excluded by
# packaging tools / the library repo's own .gitignore) and renamed on copy.
RENAMED_FILES = {
    "template.env": ".env",
    "template.gitignore": ".gitignore",
    "template.dockerignore": ".dockerignore",
    "template.env.docker.example": ".env.docker.example",
}

SKIPPED_DIRS = {"__pycache__", "data"}

# Template folder whose files are copied into the project's data/input/
# so the example pipeline is runnable right after init.
EXAMPLE_INPUT_DIR = "example_input"

# Top-level template entries only copied with --dockerization (checked
# against the on-disk template name, before RENAMED_FILES is applied).
DOCKER_ENTRIES = {"docker", "docker-compose.yml", "Makefile", "make.ps1", "template.dockerignore"}


def _template_root() -> Path:
    return Path(str(resources.files(TEMPLATE_PACKAGE))) / TEMPLATE_DIR_NAME


def _iter_template_files(root: Path, dockerization: bool = False):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIPPED_DIRS for part in rel.parts):
            continue
        if not dockerization and rel.parts[0] in DOCKER_ENTRIES:
            continue
        yield path, rel


def _data_folders_from_structure(structure_path: Path) -> list[str]:
    """Top-level nodes of data_structure.yaml are the runtime data folders."""
    with open(structure_path, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f) or {}
    return [key for key, node in schema.items() if isinstance(node, dict)]


def init(
    path: Path = typer.Argument(
        Path("."),
        help="Target directory for the new project (created if missing).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite files that already exist in the target directory.",
    ),
    dockerization: bool = typer.Option(
        False,
        "--dockerization",
        "-d",
        help="Also scaffold the Docker deployment stack (docker/, docker-compose.yml, Makefile).",
    ),
) -> None:
    """Scaffold a new pangolin project (config, pipelines, custom code, data folders)."""
    target = path.resolve()
    template_root = _template_root()
    if not template_root.is_dir():
        typer.secho(
            f"Template not found at '{template_root}'. Broken installation?",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    target.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    skipped: list[Path] = []
    for src, rel in _iter_template_files(template_root, dockerization=dockerization):
        if rel.parts[0] == EXAMPLE_INPUT_DIR:
            rel = Path("data", "input", *rel.parts[1:])
        else:
            rel = rel.with_name(RENAMED_FILES.get(rel.name, rel.name))
        dest = target / rel
        if dest.exists() and not force:
            skipped.append(rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        copied.append(rel)

    # Runtime data folders: created on disk, ignored by the generated .gitignore.
    data_root = target / "data"
    for folder in _data_folders_from_structure(
        template_root / "config" / "data_structure.yaml"
    ):
        (data_root / folder).mkdir(parents=True, exist_ok=True)

    # User-facing README: mandatory setup steps + a settings reference
    # generated from this project's own data_structure.yaml (see _docgen.py).
    readme_dest = target / "README.md"
    if readme_dest.exists() and not force:
        skipped.append(Path("README.md"))
    else:
        readme_dest.write_text(render_readme(target, dockerization=dockerization), encoding="utf-8")
        copied.append(Path("README.md"))

    for rel in copied:
        typer.secho(f"  created  {rel}", fg=typer.colors.GREEN)
    for rel in skipped:
        typer.secho(f"  skipped  {rel} (already exists)", fg=typer.colors.YELLOW)
    typer.secho(f"  created  data/ runtime folders (git-ignored)", fg=typer.colors.GREEN)

    typer.echo()
    typer.secho(f"Project initialized in {target}", bold=True)
    typer.echo("Next steps:")
    typer.echo("  1. Review and fill .env (BASEPATH, folder names, output format).")
    typer.echo("  2. Describe your project layout in config/data_structure.yaml.")
    typer.echo("  3. Fill the step registries in config/registries/.")
    typer.echo("  4. Add custom processors in custom/processors/ and pipelines in pipelines/.")
    if dockerization:
        typer.echo("  5. Copy docker/.env.docker.example to docker/.env.docker and fill it in.")
        typer.echo("  6. make build && make up   (see docker-compose.yml)")
    else:
        typer.echo(
            "  (Re-run with --dockerization / -d to also scaffold the Docker deployment stack.)"
        )
