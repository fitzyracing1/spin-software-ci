from pathlib import Path

from software_ci import (
    INTRO,
    check_log,
    check_workflow,
    main,
    verdict,
)

DATA = Path(__file__).resolve().parent / "testdata"


def _rules(findings):
    return {f.rule for f in findings}


def test_intro_names_the_project_and_sponsor():
    assert "spin-software-ci" in INTRO
    assert "Joshua Almeida" in INTRO
    assert "https://github.com/sponsors/fitzyracing1" in INTRO


def test_help_is_zero():
    assert main([]) == 0
    assert main(["--help"]) == 0


def test_lit_workflow_is_lit():
    findings = check_workflow((DATA / "lit.yml").read_text(), "lit.yml")
    assert verdict(findings) == "LIT"
    assert _rules(findings) == set()


def test_dark_workflow_flags_common_causes():
    findings = check_workflow((DATA / "dark.yml").read_text(), "dark.yml")
    assert verdict(findings) == "DARK"
    rules = _rules(findings)
    assert "missing-runs-on" in rules
    assert "action-unpinned" in rules
    assert "secret-echo" in rules
    assert "pipe-to-shell" in rules
    assert "pull-request-target-checkout" in rules


def test_warn_workflow_stays_lit_with_warnings():
    findings = check_workflow((DATA / "warn.yml").read_text(), "warn.yml")
    assert verdict(findings) == "LIT"
    rules = _rules(findings)
    assert "missing-timeout" in rules
    assert "action-moving-tag" in rules
    assert "deprecated-set-output" in rules
    assert "write-all-permissions" in rules


def test_reusable_workflow_does_not_need_runs_on():
    findings = check_workflow((DATA / "reusable.yml").read_text(), "reusable.yml")
    assert "missing-runs-on" not in _rules(findings)
    assert verdict(findings) == "LIT"


def test_cli_lit_workflow_exits_zero():
    assert main([str(DATA / "lit.yml")]) == 0


def test_cli_dark_workflow_exits_one():
    assert main([str(DATA / "dark.yml")]) == 1


def test_log_lit_is_lit():
    findings = check_log((DATA / "lit.log").read_text(), "lit.log")
    assert findings == []
    assert verdict(findings) == "LIT"
    assert main(["--log", str(DATA / "lit.log")]) == 0


def test_log_dark_flags_module_and_exit():
    findings = check_log((DATA / "dark.log").read_text(), "dark.log")
    assert verdict(findings) == "DARK"
    rules = _rules(findings)
    assert "module-not-found" in rules
    assert "nonzero-exit" in rules
    assert "actions-error" in rules
    assert main(["--log", str(DATA / "dark.log")]) == 1


def test_log_oom_and_timeout():
    findings = check_log((DATA / "oom.log").read_text(), "oom.log")
    rules = _rules(findings)
    assert "out-of-memory" in rules
    assert "timeout" in rules
    assert "nonzero-exit" in rules


def test_empty_workflow_is_dark():
    findings = check_workflow("   \n", "empty.yml")
    assert verdict(findings) == "DARK"
    assert "empty-file" in _rules(findings)


def test_missing_jobs_is_dark():
    findings = check_workflow("name: nojobs\non: push\n", "nojobs.yml")
    assert "missing-jobs" in _rules(findings)
    assert verdict(findings) == "DARK"


def test_local_action_is_not_unpinned():
    text = """
name: local
on: push
jobs:
  t:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: ./tools/my-action
"""
    assert verdict(check_workflow(text, "local.yml")) == "LIT"


def test_missing_file_is_usage_error(tmp_path):
    assert main([str(tmp_path / "nope.yml")]) == 2
