import json

from scripts.testing import bandit_json_to_sarif


def test_bandit_json_to_sarif_converts_findings():
    bandit = {
        "results": [
            {
                "test_id": "B110",
                "test_name": "try_except_pass",
                "issue_text": "Try, Except, Pass detected.",
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "filename": "./Downshiftarr.py",
                "line_number": 139,
                "more_info": "https://bandit.readthedocs.io/",
            }
        ]
    }

    sarif = bandit_json_to_sarif.bandit_to_sarif(bandit)

    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["tool"]["driver"]["rules"][0]["id"] == "B110"
    result = sarif["runs"][0]["results"][0]
    assert result["ruleId"] == "B110"
    assert result["level"] == "note"
    assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "Downshiftarr.py"
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 139


def test_bandit_json_to_sarif_writes_file(tmp_path):
    source = tmp_path / "bandit.json"
    output = tmp_path / "bandit.sarif"
    source.write_text(json.dumps({"results": []}), encoding="utf-8")

    assert bandit_json_to_sarif.main([str(source), str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["runs"][0]["results"] == []
