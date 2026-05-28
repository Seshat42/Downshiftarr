#!/usr/bin/env python3
"""Convert Bandit JSON output into the SARIF subset accepted by code scanning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def sarif_level(severity: str) -> str:
    normalized = severity.upper()
    if normalized == "HIGH":
        return "error"
    if normalized == "MEDIUM":
        return "warning"
    return "note"


def clean_uri(filename: str) -> str:
    return filename.removeprefix("./").replace("\\", "/")


def bandit_to_sarif(bandit: dict[str, Any]) -> dict[str, Any]:
    results = bandit.get("results", [])
    rules: dict[str, dict[str, Any]] = {}
    sarif_results: list[dict[str, Any]] = []

    for item in results:
        rule_id = item.get("test_id") or "bandit"
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "name": item.get("test_name") or rule_id,
                "shortDescription": {"text": item.get("issue_text") or rule_id},
                "helpUri": item.get("more_info") or "https://bandit.readthedocs.io/",
                "properties": {
                    "tags": ["security", "bandit"],
                    "precision": "medium",
                    "security-severity": "5.0",
                },
            },
        )
        sarif_results.append(
            {
                "ruleId": rule_id,
                "level": sarif_level(item.get("issue_severity", "LOW")),
                "message": {"text": item.get("issue_text") or rule_id},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": clean_uri(item.get("filename", ""))},
                            "region": {"startLine": int(item.get("line_number") or 1)},
                        }
                    }
                ],
                "properties": {
                    "confidence": item.get("issue_confidence"),
                    "severity": item.get("issue_severity"),
                    "test_name": item.get("test_name"),
                },
            }
        )

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Bandit",
                        "informationUri": "https://bandit.readthedocs.io/",
                        "rules": list(rules.values()),
                    }
                },
                "results": sarif_results,
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bandit_json")
    parser.add_argument("sarif_output")
    args = parser.parse_args(argv)

    bandit = json.loads(Path(args.bandit_json).read_text(encoding="utf-8"))
    sarif = bandit_to_sarif(bandit)
    Path(args.sarif_output).write_text(json.dumps(sarif, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote SARIF: {args.sarif_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
