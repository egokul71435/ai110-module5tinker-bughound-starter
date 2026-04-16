from reliability.risk_assessor import assess_risk


def test_no_fix_is_high_risk():
    risk = assess_risk(
        original_code="print('hi')\n",
        fixed_code="",
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "print"}],
    )
    assert risk["level"] == "high"
    assert risk["should_autofix"] is False
    assert risk["score"] == 0


def test_low_risk_when_minimal_change_and_low_severity():
    original = "import logging\n\ndef add(a, b):\n    return a + b\n"
    fixed = "import logging\n\ndef add(a, b):\n    return a + b\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "minor"}],
    )
    assert risk["level"] in ("low", "medium")  # depends on scoring rules
    assert 0 <= risk["score"] <= 100


def test_high_severity_issue_drives_score_down():
    original = "def f():\n    try:\n        return 1\n    except:\n        return 0\n"
    fixed = "def f():\n    try:\n        return 1\n    except Exception as e:\n        return 0\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Reliability", "severity": "High", "msg": "bare except"}],
    )
    assert risk["score"] <= 60
    assert risk["level"] in ("medium", "high")


def test_identical_fix_does_not_autofix():
    """
    When the heuristic fixer has no handler for an issue type (e.g. Maintainability/TODO),
    it returns the original code unchanged. The risk assessor must not recommend
    auto-applying a fix that is byte-for-byte identical to the original — that would
    be unsafe confidence (the system acts certain while changing nothing).

    This test would FAIL before the guardrail (score=80, level=low → should_autofix=True)
    and PASS after it (identical-fix check overrides should_autofix to False).
    """
    code = "# TODO: validate inputs before calling API\n# TODO: add error handling\n"
    risk = assess_risk(
        original_code=code,
        fixed_code=code,  # heuristic fixer produced no change — identical to original
        issues=[{"type": "Maintainability", "severity": "Medium", "msg": "TODO comment"}],
    )
    assert risk["should_autofix"] is False
    assert any("identical" in r.lower() for r in risk["reasons"])


def test_missing_return_is_penalized():
    original = "def f(x):\n    return x + 1\n"
    fixed = "def f(x):\n    x + 1\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[],
    )
    assert risk["score"] < 100
    assert any("Return" in r or "return" in r for r in risk["reasons"])
