"""spin-software-ci: flag common GitHub Actions failure causes by rules."""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

INTRO = (
    "spin-software-ci by Joshua Almeida.\n"
    "Rules and code, no API, offline. Sponsor: https://github.com/sponsors/fitzyracing1"
)

UNPINNED_REFS = frozenset({"main", "master", "head", "dev", "develop", "latest"})
SHA_REF_RE = re.compile(r"^[0-9a-f]{7,40}$", re.I)
MOVING_TAG_RE = re.compile(r"^v?\d+(\.\d+)*$", re.I)
USES_RE = re.compile(r"^(\s*)(?:-\s*)?uses:\s*(\S+)\s*(#.*)?$")
SECRET_ECHO_RE = re.compile(
    r"(?i)(?:^|[\s;])(?:echo|printf|print|write-output|write-host)\b[^\n]*\$\{\{\s*secrets\."
)
PIPE_SHELL_RE = re.compile(
    r"(?i)\b(?:curl|wget|fetch)\b[^\n]*\|\s*(?:sudo\s+)?(?:bash|sh|zsh|ksh)\b"
)
SETOUTPUT_RE = re.compile(r"::set-output\s+|::save-state\s+")
PRT_RE = re.compile(r"(?im)\bpull_request_target\b")
PR_REF_RE = re.compile(
    r"(?i)ref:\s*\$\{\{\s*github\.(?:event\.pull_request|head_ref|event\.number)"
)


@dataclass(frozen=True)
class Finding:
    severity: str  # "error" or "warning"
    rule: str
    location: str
    message: str

    def line(self) -> str:
        return f"  [{self.severity}] {self.rule}  {self.location}: {self.message}"


LOG_RULES = (
    (
        "out-of-memory",
        re.compile(r"\bKilled\b|out of memory|MemoryError|OSError: \[Errno 12\]", re.I),
        "The job looks like it ran out of memory.",
    ),
    (
        "timeout",
        re.compile(
            r"The action has timed out|exited because of timeout|Error: The operation was canceled|"
            r"cancellationToken.*timeout|##\[error\].*timed out",
            re.I,
        ),
        "The job or a step looks like it timed out.",
    ),
    (
        "module-not-found",
        re.compile(r"ModuleNotFoundError|ImportError: No module named", re.I),
        "Python could not import a module. Check dependencies and the working directory.",
    ),
    (
        "permission-denied",
        re.compile(r"Permission denied|EACCES|Error: Permission", re.I),
        "A step hit a permission error. Check checkout credentials, permissions:, and file modes.",
    ),
    (
        "token-permissions",
        re.compile(r"Resource not accessible by integration", re.I),
        "GITHUB_TOKEN lacked a permission this step needed. Tighten or grant permissions: on the job.",
    ),
    (
        "rate-limit",
        re.compile(r"API rate limit|HTTP 429|toomanyrequests|pull rate limit exceeded", re.I),
        "A registry or API rate limit was hit.",
    ),
    (
        "disk-full",
        re.compile(r"No space left on device|ENOSPC", re.I),
        "The runner ran out of disk space.",
    ),
    (
        "checkout-failed",
        re.compile(r"fatal: repository|Checkout failed|Error: Invalid ref|fatal: couldn't find remote ref", re.I),
        "git checkout failed. Check the ref, submodules, and token permissions.",
    ),
    (
        "npm-error",
        re.compile(r"npm ERR!|error Command failed", re.I),
        "npm or yarn reported a command failure.",
    ),
    (
        "pytest-failed",
        re.compile(r"={3,} .*(failed|error)", re.I),
        "pytest reported failed or errored tests.",
    ),
    (
        "actions-error",
        re.compile(r"##\[error\]"),
        "GitHub Actions logged an error annotation.",
    ),
    (
        "nonzero-exit",
        re.compile(r"Process completed with exit code ([1-9]\d*)"),
        "A step exited with a non-zero status.",
    ),
)


def _strip_comment(line: str) -> str:
    in_single = in_double = False
    out = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
        elif ch == "#" and not in_single and not in_double:
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _mapping_key(line: str):
    body = _strip_comment(line).lstrip()
    if not body or body.startswith("-"):
        return None
    if ":" not in body:
        return None
    key, _, rest = body.partition(":")
    key = key.strip().strip("\"'")
    if not key or any(ch.isspace() for ch in key):
        return None
    return key, rest.strip()


def _iter_jobs(text: str):
    lines = text.splitlines()
    jobs_index = None
    jobs_indent = None
    for i, raw in enumerate(lines):
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        key = _mapping_key(raw)
        if key and key[0] == "jobs" and jobs_index is None:
            jobs_index = i
            jobs_indent = _line_indent(raw)
            if key[1] != "":
                return []  # flow-style jobs; not parsed into job names
            break
    if jobs_index is None:
        return None

    job_indent = None
    jobs = []
    i = jobs_index + 1
    while i < len(lines):
        raw = lines[i]
        stripped = _strip_comment(raw)
        if not stripped.strip():
            i += 1
            continue
        indent = _line_indent(raw)
        if indent <= jobs_indent:
            break
        key = _mapping_key(raw)
        if job_indent is None and key:
            job_indent = indent
        if key and indent == job_indent:
            name = key[0]
            start = i
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not _strip_comment(nxt).strip():
                    i += 1
                    continue
                nindent = _line_indent(nxt)
                if nindent <= job_indent:
                    break
                i += 1
            body = "\n".join(lines[start + 1 : i])
            jobs.append((name, start + 1, body))
            continue
        i += 1
    return jobs


def _job_has_top_level_key(body: str, want: str) -> bool:
    if not body:
        return False
    # Top-level job keys are the least-indented mapping keys in the job body.
    min_indent = None
    for raw in body.splitlines():
        if not _strip_comment(raw).strip():
            continue
        indent = _line_indent(raw)
        key = _mapping_key(raw)
        if key is None:
            continue
        if min_indent is None:
            min_indent = indent
        if indent == min_indent and key[0] == want:
            return True
    return False


def check_workflow(text: str, source: str = "workflow.yml") -> list[Finding]:
    findings: list[Finding] = []
    if not text.strip():
        return [
            Finding("error", "empty-file", source, "The workflow file is empty.")
        ]

    jobs = _iter_jobs(text)
    if jobs is None:
        findings.append(
            Finding("error", "missing-jobs", source, "No top-level jobs: key was found.")
        )
    elif jobs == []:
        findings.append(
            Finding(
                "warning",
                "jobs-unparsed",
                source,
                "The jobs: block could not be split into named jobs (flow style or unusual indent).",
            )
        )
    else:
        for name, _lineno, body in jobs:
            loc = f"jobs.{name}"
            reusable = _job_has_top_level_key(body, "uses")
            if not reusable and not _job_has_top_level_key(body, "runs-on"):
                findings.append(
                    Finding(
                        "error",
                        "missing-runs-on",
                        loc,
                        "Job has no runs-on: and is not a reusable workflow.",
                    )
                )
            if not reusable and not _job_has_top_level_key(body, "timeout-minutes"):
                findings.append(
                    Finding(
                        "warning",
                        "missing-timeout",
                        loc,
                        "Job has no timeout-minutes:; a hung step can burn the whole run.",
                    )
                )

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = _strip_comment(raw)
        match = USES_RE.match(stripped)
        if match:
            action = match.group(2).strip().strip("\"'")
            loc = f"{source}:{lineno}"
            findings.extend(_check_uses(action, loc))

    if SECRET_ECHO_RE.search(text):
        findings.append(
            Finding(
                "error",
                "secret-echo",
                source,
                "A run step echoes or prints ${{ secrets.* }}; that can leak a secret in the log.",
            )
        )
    if PIPE_SHELL_RE.search(text):
        findings.append(
            Finding(
                "error",
                "pipe-to-shell",
                source,
                "A step pipes curl/wget into a shell. Pin and review the script, or vendor it.",
            )
        )
    if SETOUTPUT_RE.search(text):
        findings.append(
            Finding(
                "warning",
                "deprecated-set-output",
                source,
                "The workflow uses ::set-output or ::save-state, which GitHub deprecated.",
            )
        )
    if PRT_RE.search(text) and PR_REF_RE.search(text):
        findings.append(
            Finding(
                "error",
                "pull-request-target-checkout",
                source,
                "pull_request_target checks out PR code, which can run untrusted code with repo secrets.",
            )
        )
    if re.search(r"(?m)^\s*permissions:\s*write-all\s*$", text):
        findings.append(
            Finding(
                "warning",
                "write-all-permissions",
                source,
                "permissions: write-all grants a broad token to the job.",
            )
        )
    return findings


def _check_uses(action: str, loc: str) -> list[Finding]:
    if action.startswith("./"):
        return []
    if action.startswith("docker://"):
        if action.rstrip(":").endswith("docker://") or action.endswith(":"):
            return [
                Finding("warning", "docker-unpinned", loc, f"Docker image {action} has no tag.")
            ]
        if action.endswith(":latest"):
            return [
                Finding("error", "action-unpinned", loc, f"{action} uses the floating tag latest.")
            ]
        return []
    if "@" not in action:
        return [
            Finding(
                "error",
                "action-unpinned",
                loc,
                f"{action} has no version or SHA. Pin it with @<sha> or a version tag.",
            )
        ]
    name, ref = action.rsplit("@", 1)
    if ref.lower() in UNPINNED_REFS:
        return [
            Finding(
                "error",
                "action-unpinned",
                loc,
                f"{action} tracks a moving branch or latest. Pin a commit SHA.",
            )
        ]
    if SHA_REF_RE.match(ref):
        return []
    if MOVING_TAG_RE.match(ref):
        return [
            Finding(
                "warning",
                "action-moving-tag",
                loc,
                f"{action} is pinned to a tag, which can move. A commit SHA is more stable.",
            )
        ]
    return []


def check_log(text: str, source: str = "log") -> list[Finding]:
    findings: list[Finding] = []
    seen = set()
    for rule, pattern, message in LOG_RULES:
        match = pattern.search(text)
        if not match or rule in seen:
            continue
        seen.add(rule)
        extra = ""
        if rule == "nonzero-exit":
            extra = f" Exit code {match.group(1)}."
        findings.append(Finding("error", rule, source, message + extra))
    return findings


def verdict(findings: list[Finding]) -> str:
    return "DARK" if any(f.severity == "error" for f in findings) else "LIT"


def render(source: str, findings: list[Finding]) -> str:
    status = verdict(findings)
    lines = [INTRO, "", f"{status}  {source}"]
    if not findings:
        lines.append("  No common failure signatures fired.")
    else:
        lines.extend(f.line() for f in findings)
    return "\n".join(lines)


def _read_input(path: str) -> tuple[str, str]:
    if path == "-":
        return "stdin", sys.stdin.read()
    p = Path(path)
    return str(p), p.read_text(encoding="utf-8", errors="replace")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="software_ci.py",
        description="Flag common GitHub Actions failure causes in a workflow or a job log.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Workflow YAML path, or a log path when --log is set. Use - for stdin.",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Treat the path as a job log instead of a workflow YAML file.",
    )
    try:
        args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    except SystemExit as exc:
        code = exc.code
        return 0 if code in (0, None) else int(code)
    if args.path is None:
        print(INTRO)
        print()
        print("Usage: python software_ci.py WORKFLOW.yml")
        print("       python software_ci.py --log JOB.log")
        print("       python software_ci.py --log -  < JOB.log")
        return 0
    try:
        source, text = _read_input(args.path)
    except OSError as exc:
        print(f"Could not read {args.path}: {exc}", file=sys.stderr)
        return 2
    findings = check_log(text, source) if args.log else check_workflow(text, source)
    print(render(source, findings))
    return 1 if verdict(findings) == "DARK" else 0


if __name__ == "__main__":
    raise SystemExit(main())
