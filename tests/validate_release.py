#!/usr/bin/env python3
"""Validate the public release using only the Python standard library."""

from __future__ import annotations

import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "lesson-first-judgment-question-sop"


def require_files() -> None:
    required = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "LICENSE",
        REPO_ROOT / "assets" / "workflow-guizang.png",
        REPO_ROOT / ".gitignore",
        REPO_ROOT / ".gitattributes",
        REPO_ROOT / ".github" / "workflows" / "validate.yml",
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "agents" / "openai.yaml",
        SKILL_ROOT / "scripts" / "audit_terms.py",
        SKILL_ROOT / "references" / "terminology-policy.md",
        SKILL_ROOT / "references" / "quality-gates.md",
        SKILL_ROOT / "references" / "output-schema.md",
        SKILL_ROOT / "references" / "run-artifact-policy.md",
        SKILL_ROOT
        / "references"
        / "lesson-lexicons"
        / "SYNTHETIC-G7-I1.json",
    ]
    missing = [str(path.relative_to(REPO_ROOT)) for path in required if not path.is_file()]
    if missing:
        raise AssertionError(f"Missing required files: {missing}")


def validate_frontmatter() -> None:
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        raise AssertionError("SKILL.md has invalid frontmatter delimiters")

    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise AssertionError(f"Invalid frontmatter line: {line!r}")
        fields[key.strip()] = value.strip()

    if set(fields) != {"name", "description"}:
        raise AssertionError(f"Unexpected frontmatter fields: {sorted(fields)}")

    name = fields["name"]
    description = fields["description"]
    if name != SKILL_ROOT.name:
        raise AssertionError("Skill folder and frontmatter name do not match")
    if not re.fullmatch(r"[a-z0-9-]+", name) or len(name) > 64:
        raise AssertionError("Skill name is not valid hyphen-case")
    if not description or len(description) > 1024 or "<" in description or ">" in description:
        raise AssertionError("Skill description is invalid")


def validate_json() -> None:
    for path in SKILL_ROOT.rglob("*.json"):
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)


def validate_python() -> None:
    source = SKILL_ROOT / "scripts" / "audit_terms.py"
    with tempfile.TemporaryDirectory() as temp_dir:
        target = Path(temp_dir) / "audit_terms.pyc"
        py_compile.compile(str(source), cfile=str(target), doraise=True)


def validate_term_smoke_tests() -> None:
    script = SKILL_ROOT / "scripts" / "audit_terms.py"
    lexicon = (
        SKILL_ROOT
        / "references"
        / "lesson-lexicons"
        / "SYNTHETIC-G7-I1.json"
    )
    common_args = [
        sys.executable,
        str(script),
        "--lexicon",
        str(lexicon),
        "--edition",
        "SYNTHETIC",
        "--lesson-id",
        "SYNTHETIC-G7-I1",
        "--audience",
        "student",
        "--terms",
    ]
    utf8_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    allowed = subprocess.run(
        [*common_args, "整数", "加法", "交换律"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=utf8_env,
        check=False,
    )
    if allowed.returncode != 0:
        raise AssertionError(f"Allowed-term smoke test failed: {allowed.stderr}")
    allowed_report = json.loads(allowed.stdout)
    if allowed_report.get("overall") != "PASS":
        raise AssertionError("Allowed-term smoke test did not return overall PASS")

    blocked = subprocess.run(
        [*common_args, "整数", "分配律"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=utf8_env,
        check=False,
    )
    if blocked.returncode == 0:
        raise AssertionError("Blocked-term smoke test unexpectedly exited successfully")
    blocked_report = json.loads(blocked.stdout)
    if (
        blocked_report.get("overall") != "FAIL"
        or "分配律" not in blocked_report.get("blocked_terms", [])
    ):
        raise AssertionError("Blocked-term smoke test did not block 分配律")


def validate_public_content() -> None:
    forbidden = [
        re.compile(r"[A-Za-z]:\\+"),
        re.compile(r"C:/Users/", re.IGNORECASE),
        re.compile(r"/Users/[^/]+/"),
        re.compile(r"/home/[^/]+/"),
        re.compile(r"博士生szc", re.IGNORECASE),
        re.compile(r"HJ54", re.IGNORECASE),
        re.compile(r"教材印刷页"),
        re.compile(r"PPT第"),
        re.compile(r"作业第"),
        re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
        re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{10,}", re.IGNORECASE),
    ]
    checked_suffixes = {".md", ".json", ".yaml", ".yml", ".py"}
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in checked_suffixes:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern.search(text):
                relative = path.relative_to(REPO_ROOT)
                raise AssertionError(f"Forbidden public content in {relative}: {pattern.pattern}")


def main() -> int:
    checks = [
        require_files,
        validate_frontmatter,
        validate_json,
        validate_python,
        validate_term_smoke_tests,
        validate_public_content,
    ]
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print("PASS: public release validation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
