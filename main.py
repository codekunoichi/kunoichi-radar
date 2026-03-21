import csv
import json
import logging
import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from src.database import get_engine, get_session, get_repos, get_categories
from src.scheduler import run_fetch

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = typer.Typer(help="Kunoichi Radar — trending AI repos by industry vertical")
console = Console()

DB_PATH = os.getenv("DB_PATH", "data/radar.db")
CONFIG_PATH = "config/categories.yaml"


def _get_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        console.print("[bold red]Error:[/] GITHUB_TOKEN not set. Add it to your .env file.")
        raise typer.Exit(1)
    return token


@app.command()
def fetch():
    """Refresh all categories from the GitHub API."""
    token = _get_token()
    console.print("[bold cyan]Kunoichi Radar[/] — fetching repositories...\n")

    summary = run_fetch(token=token, db_path=DB_PATH, config_path=CONFIG_PATH)

    table = Table(title="Fetch Summary", show_header=True)
    table.add_column("Category", style="cyan")
    table.add_column("Repos Upserted", justify="right", style="green")

    for category, count in summary.items():
        table.add_row(category, str(count))

    console.print(table)


@app.command(name="list")
def list_repos(
    category: str = typer.Option(None, "--category", "-c", help="Filter by category name"),
    min_stars: int = typer.Option(0, "--min-stars", "-s", help="Minimum star count"),
):
    """Display ranked repositories in a rich terminal table."""
    engine = get_engine(DB_PATH)

    with get_session(engine) as session:
        repos = get_repos(session, category=category, min_stars=min_stars)
        available_categories = get_categories(session)

    if not repos:
        console.print("[yellow]No repos found.[/] Run [bold]python main.py fetch[/] first.")
        return

    title = f"Kunoichi Radar — {category or 'All Categories'}"
    if min_stars:
        title += f" (min ★ {min_stars})"

    table = Table(title=title, show_header=True, show_lines=False)
    table.add_column("Rank", justify="right", style="dim", width=5)
    table.add_column("Repository", style="bold cyan", min_width=30)
    table.add_column("★ Stars", justify="right", style="yellow", width=8)
    table.add_column("Category", style="magenta", width=18)
    table.add_column("Topics", style="green", max_width=30)
    table.add_column("Last Pushed", width=12)

    for rank, repo in enumerate(repos, 1):
        topics_str = ", ".join(repo["topics"][:3]) if repo["topics"] else "—"
        pushed = (repo["pushed_at"] or "")[:10] if repo["pushed_at"] else "—"
        table.add_row(
            str(rank),
            repo["name"],
            f"{repo['stars']:,}",
            repo["category"],
            topics_str,
            pushed,
        )

    console.print(table)
    console.print(f"\n[dim]{len(repos)} repos shown[/]")


@app.command()
def export(
    format: str = typer.Option("csv", "--format", "-f", help="Export format: csv or json"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    min_stars: int = typer.Option(0, "--min-stars", "-s", help="Minimum star count"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export results to CSV or JSON."""
    engine = get_engine(DB_PATH)

    with get_session(engine) as session:
        repos = get_repos(session, category=category, min_stars=min_stars)

    if not repos:
        console.print("[yellow]No repos to export.[/]")
        return

    if format == "csv":
        out_path = output or "export.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=repos[0].keys())
            writer.writeheader()
            for repo in repos:
                row = {**repo, "topics": ",".join(repo["topics"])}
                writer.writerow(row)
        console.print(f"[green]Exported {len(repos)} repos to[/] {out_path}")

    elif format == "json":
        out_path = output or "export.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(repos, f, indent=2)
        console.print(f"[green]Exported {len(repos)} repos to[/] {out_path}")

    else:
        console.print(f"[red]Unknown format:[/] {format}. Use 'csv' or 'json'.")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
