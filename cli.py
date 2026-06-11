from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from pipeline import Pipeline
from src.data_layer.file_importer import FileImporter
from src.data_layer.data_store import DataStore
from src.execution.troubleshooter import Troubleshooter

app = typer.Typer(help="AMZ竞品运营自动化框架 CLI")
console = Console()
_pipeline = Pipeline()


@app.command()
def import_data(
    path: str = typer.Argument(help="数据文件或目录路径"),
):
    console.print(f"[bold blue]Importing data from:[/bold blue] {path}")
    try:
        results = _pipeline.import_data(path)
        if not results:
            console.print("[yellow]No files imported.[/yellow]")
            raise typer.Exit(1)

        table = Table(title="Import Summary")
        table.add_column("File", style="cyan")
        table.add_column("Format", style="green")
        table.add_column("Status", style="magenta")

        for r in results:
            fmt = r.get("format", "unknown")
            filename = r.get("filename", r.get("path", ""))
            has_data = r.get("data") is not None
            status = "[green]OK[/green]" if has_data else "[red]EMPTY[/red]"
            if fmt == "error":
                status = f"[red]ERROR: {r.get('error', '')}[/red]"
            elif fmt == "unsupported":
                status = "[yellow]UNSUPPORTED[/yellow]"
            table.add_row(filename, fmt, status)

        console.print(table)
        console.print(f"\n[bold green]Total files processed: {len(results)}[/bold green]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Import failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def keyword_build(
    own_asin: str = typer.Argument(help="自身产品ASIN"),
    data_dir: str = typer.Option("data/raw", help="数据目录"),
    category_cvr: float = typer.Option(None, help="类目CVR（不填则自动从数据估算）"),
):
    console.print(f"[bold blue]Building keyword library for ASIN:[/bold blue] {own_asin}")
    try:
        imported_data = _pipeline.import_data(data_dir)
        if not imported_data:
            console.print("[yellow]No data found. Import files first.[/yellow]")
            raise typer.Exit(1)

        if category_cvr is None:
            from src.analysis.keyword_builder import KeywordBuilder
            category_cvr = KeywordBuilder.estimate_cvr(imported_data)
            console.print(f"[dim]Auto-estimated category CVR: {category_cvr:.4f} ({category_cvr:.2%})[/dim]")

        library = _pipeline.build_keyword_library(own_asin, category_cvr, imported_data)

        console.print(f"\n[bold green]Keyword Library Built[/bold green]")
        console.print(f"  Total Keywords: {library.total_keywords}")
        console.print(f"  Traffic Structure: {library.traffic_structure}")
        console.print(f"  Competitor ASINs: {', '.join(library.competitor_asins)}")
        console.print(f"  Negation List: {len(library.negation_list)} keywords")

        table = Table(title="Priority Distribution")
        table.add_column("Priority", style="cyan")
        table.add_column("Count", style="green")
        table.add_column("Keywords", style="white")
        priority_counts: dict[str, list[str]] = {}
        for kw in library.classified_keywords:
            priority_counts.setdefault(kw.priority, []).append(kw.keyword_text)
        for priority, kws in sorted(priority_counts.items()):
            sample = ", ".join(kws[:5])
            if len(kws) > 5:
                sample += f" ... (+{len(kws) - 5})"
            table.add_row(priority, str(len(kws)), sample)
        console.print(table)

        store = DataStore()
        store.save_json(library.model_dump(), "keyword_library.json")
        console.print(f"\n[dim]Saved to data/processed/keyword_library.json[/dim]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Keyword build failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def market_rhythm(
    data_dir: str = typer.Option("data/raw", help="数据目录"),
):
    console.print("[bold blue]Analyzing market rhythm...[/bold blue]")
    try:
        imported_data = _pipeline.import_data(data_dir)
        if not imported_data:
            console.print("[yellow]No data found. Import files first.[/yellow]")
            raise typer.Exit(1)

        phase = _pipeline.analyze_market(imported_data)

        phase_label = {"up": "上升期", "down": "下行期", "stable": "稳定期", "unknown": "未知"}.get(
            phase.phase, phase.phase
        )
        phase_color = {"up": "green", "down": "red", "stable": "yellow", "unknown": "white"}.get(
            phase.phase, "white"
        )

        console.print(f"\n[bold]Market Phase:[/bold] [{phase_color}]{phase_label}[/{phase_color}]")
        console.print(f"  Confidence: {phase.confidence:.0%}")
        console.print(f"  Consecutive Weeks: {phase.consecutive_weeks}")
        console.print(f"  Change: {phase.change_pct:+.1f}%")
        console.print(f"  Recommended Action: {phase.recommended_action}")

        store = DataStore()
        store.save_json(phase.model_dump(), "market_phase.json")
        console.print(f"\n[dim]Saved to data/processed/market_phase.json[/dim]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Market analysis failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def competitor_teardown(
    asin: str = typer.Argument(help="竞品ASIN"),
    data_dir: str = typer.Option("data/raw", help="数据目录"),
):
    console.print(f"[bold blue]Competitor teardown for ASIN:[/bold blue] {asin}")
    try:
        imported_data = _pipeline.import_data(data_dir)
        if not imported_data:
            console.print("[yellow]No data found. Import files first.[/yellow]")
            raise typer.Exit(1)

        timeline = _pipeline.teardown_competitor(asin, imported_data)

        console.print(f"\n[bold green]Competitor Timeline[/bold green]")
        console.print(f"  ASIN: {timeline.asin}")
        console.print(f"  Total Weeks: {timeline.total_weeks}")
        console.print(f"  Phase Summary: {timeline.phase_summary}")

        if timeline.weekly_events:
            table = Table(title="Weekly Events (Last 10)")
            table.add_column("Week", style="cyan", max_width=25)
            table.add_column("KWs", style="green", justify="right")
            table.add_column("Price", style="yellow", justify="right")
            table.add_column("BSR", style="white", justify="right")
            table.add_column("Reviews", style="white", justify="right")
            table.add_column("Decision", style="magenta", max_width=40)
            for ev in timeline.weekly_events[-10:]:
                table.add_row(
                    ev.week_label,
                    str(ev.ad_keyword_count),
                    f"${ev.price:.2f}" if ev.price else "-",
                    str(ev.bsr_category) if ev.bsr_category else "-",
                    f"{ev.reviews} ({ev.review_change})" if ev.reviews else "-",
                    ev.key_decision,
                )
            console.print(table)

        store = DataStore()
        store.save_json(timeline.model_dump(), f"competitor_timeline_{asin}.json")
        console.print(f"\n[dim]Saved to data/processed/competitor_timeline_{asin}.json[/dim]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Competitor teardown failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def attack_plan(
    own_asin: str = typer.Argument(help="自身ASIN"),
    competitor_asins: str = typer.Argument(help="竞品ASIN，逗号分隔"),
    data_dir: str = typer.Option("data/raw", help="数据目录"),
):
    console.print("[bold blue]Generating attack plans...[/bold blue]")
    try:
        comp_asins = [a.strip() for a in competitor_asins.split(",") if a.strip()]
        imported_data = _pipeline.import_data(data_dir)

        keyword_library = _pipeline.build_keyword_library(own_asin, 0.05, imported_data)
        classified = keyword_library.classified_keywords if keyword_library else []

        store = DataStore()
        for comp_asin in comp_asins:
            plan = _pipeline.attack_planner.generate_plan(
                own_asin=own_asin,
                competitor_asin=comp_asin,
                classified_keywords=classified,
            )

            console.print(f"\n[bold green]Attack Plan vs {comp_asin}[/bold green]")

            if plan.weaknesses:
                console.print("  [bold]Weaknesses:[/bold]")
                for w in plan.weaknesses:
                    console.print(f"    - {w.get('type', '')}: {w.get('detail', '')}")

            if plan.copy_actions:
                console.print("  [bold]Copy Actions:[/bold]")
                for a in plan.copy_actions[:5]:
                    console.print(f"    - {a}")

            if plan.differentiate_actions:
                console.print("  [bold]Differentiate Actions:[/bold]")
                for a in plan.differentiate_actions[:5]:
                    console.print(f"    - {a}")

            if plan.phased_plan:
                console.print("  [bold]Phased Plan:[/bold]")
                for phase in plan.phased_plan:
                    console.print(f"    - {phase.get('phase', '')}: {phase.get('goal', '')}")

            store.save_json(plan.model_dump(), f"attack_plan_{comp_asin}.json")

        console.print(f"\n[dim]Plans saved to data/processed/[/dim]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Attack plan generation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def daily_sop(
    sp_report: str = typer.Argument(help="SP搜索词报告路径"),
    category_cvr: float = typer.Option(0.05, help="类目CVR"),
):
    console.print("[bold blue]Generating daily optimization SOP...[/bold blue]")
    try:
        imported_data = _pipeline.import_data(sp_report)
        actions = _pipeline.daily_optimization(imported_data, category_cvr)

        if not actions:
            console.print("[yellow]No optimization actions generated.[/yellow]")
            return

        table = Table(title=f"Daily SOP ({len(actions)} actions)")
        table.add_column("#", style="dim", justify="right")
        table.add_column("Priority", style="bold")
        table.add_column("Method", style="cyan")
        table.add_column("Campaign", style="green", max_width=25)
        table.add_column("Keyword", style="white", max_width=20)
        table.add_column("Current", style="red")
        table.add_column("Suggested", style="green")
        table.add_column("Reason", style="yellow", max_width=40)

        for i, act in enumerate(actions, 1):
            priority_color = {"高": "red", "中": "yellow", "低": "dim"}.get(act.priority, "white")
            table.add_row(
                str(i),
                f"[{priority_color}]{act.priority}[/{priority_color}]",
                act.method,
                act.campaign[:25],
                act.keyword[:20],
                act.current_value,
                act.suggested_value,
                act.reason[:40],
            )
        console.print(table)

        console.print(f"\n[bold]Summary:[/bold]")
        high = sum(1 for a in actions if a.priority == "高")
        mid = sum(1 for a in actions if a.priority == "中")
        low = sum(1 for a in actions if a.priority == "低")
        console.print(f"  High: {high} | Medium: {mid} | Low: {low}")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Daily SOP generation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def diagnose(
    symptoms: list[str] = typer.Argument(help="症状描述"),
):
    console.print("[bold blue]Running diagnosis...[/bold blue]")
    try:
        troubleshooter = Troubleshooter()
        results = troubleshooter.diagnose(symptoms)

        if not results:
            console.print("[yellow]No matching scenarios found.[/yellow]")
            return

        for i, r in enumerate(results, 1):
            confidence_bar = "█" * int(r["confidence"] * 10)
            console.print(f"\n[bold]{i}. {r['problem']}[/bold]")
            console.print(f"   Scenario: {r['scenario']}")
            console.print(f"   Confidence: [{confidence_bar}] {r['confidence']:.0%}")
            console.print(f"   Matched: {', '.join(r['matched_symptoms'])}")
            console.print(f"   [green]Solution: {r['solution']}[/green]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Diagnosis failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def full_pipeline(
    data_dir: str = typer.Argument(help="数据目录"),
    own_asin: str = typer.Option(..., help="自身ASIN"),
    category_cvr: float = typer.Option(None, help="类目CVR（不填则自动估算）"),
    product_stage: str = typer.Option("新品期", help="产品阶段"),
    revenue: float = typer.Option(0, help="月营收"),
):
    console.print("[bold blue]Running full pipeline...[/bold blue]\n")
    try:
        with console.status("[bold green]Processing..."):
            result = _pipeline.full_pipeline(
                data_dir=data_dir,
                own_asin=own_asin,
                category_cvr=category_cvr,
                product_stage=product_stage,
                revenue=revenue,
            )

        console.print("[bold green]Pipeline Complete[/bold green]\n")

        if result.keyword_library:
            kl = result.keyword_library
            console.print(f"[bold]Keywords:[/bold] {kl.total_keywords} total, structure={kl.traffic_structure}")

        if result.market_phase:
            mp = result.market_phase
            phase_label = {"up": "上升", "down": "下行", "stable": "稳定"}.get(mp.phase, mp.phase)
            console.print(f"[bold]Market:[/bold] {phase_label} (confidence {mp.confidence:.0%})")

        if result.competitor_timelines:
            console.print(f"[bold]Competitors:[/bold] {len(result.competitor_timelines)} timelines")

        if result.budget_plan:
            bp = result.budget_plan
            console.print(f"[bold]Budget:[/bold] ${bp.ad_spend_amount:,.2f} ({bp.ad_spend_ratio:.1%} of revenue)")

        if result.ad_architecture:
            arch = result.ad_architecture
            console.print(f"[bold]Ad Architecture:[/bold] {arch.push_strategy}, {len(arch.campaigns)} campaigns")

        if result.risk_alerts:
            console.print(f"[bold red]Risks:[/bold red] {len(result.risk_alerts)} alerts")

        if result.optimization_actions:
            console.print(f"[bold]Optimizations:[/bold] {len(result.optimization_actions)} actions")

        if result.attack_plans:
            console.print(f"[bold]Attack Plans:[/bold] {len(result.attack_plans)} plans")

        store = DataStore()
        console.print(f"\n[dim]Results saved to data/processed/ and data/reports/[/dim]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Pipeline failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def dashboard():
    console.print("[bold blue]Starting Streamlit dashboard...[/bold blue]")
    import subprocess
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "dashboard/app.py"],
            check=True,
        )
    except FileNotFoundError:
        console.print("[red]Streamlit not found. Install with: pip install streamlit[/red]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")


if __name__ == "__main__":
    app()
