#!/usr/bin/env python3
"""List the manual hardening runs prepared for Downshiftarr."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.testing.hardening_catalog import all_runs, redact_secrets, validate_catalog


def render_text(category: str | None = None) -> str:
    selected = [run for run in all_runs() if category is None or run.category == category]
    lines = [
        "# Downshiftarr Hardening Initial Run List",
        "",
        "These commands are prepared for manual execution after setup verification. They are intentionally not part of the default local gate.",
        "",
    ]
    for run in selected:
        lines.extend(
            [
                f"## {run.category}: {run.name}",
                run.description,
                "",
                "List/setup command:",
                f"  {run.list_command}",
                "",
                "Bounded first pass:",
                f"  {run.first_pass_command}",
                "",
                f"Enhance after first run: {run.enhancement_note}",
                "",
            ]
        )
    return redact_secrets("\n".join(lines))


def render_json(category: str | None = None) -> str:
    selected = [run for run in all_runs() if category is None or run.category == category]
    payload = [
        {
            "category": run.category,
            "name": run.name,
            "description": run.description,
            "list_command": run.list_command,
            "first_pass_command": run.first_pass_command,
            "enhancement_note": run.enhancement_note,
        }
        for run in selected
    ]
    return redact_secrets(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", help="Limit output to one hardening category.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--check", action="store_true", help="Validate the catalog before printing.")
    args = parser.parse_args(argv)

    issues = validate_catalog() if args.check else []
    if issues:
        print("Hardening run catalog is invalid:", file=sys.stderr)
        print("\n".join(issues), file=sys.stderr)
        return 1

    if args.category and args.category not in {run.category for run in all_runs()}:
        print(f"Unknown hardening category: {args.category}", file=sys.stderr)
        return 2

    print(render_json(args.category) if args.json else render_text(args.category))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
