#!/usr/bin/env python3
"""Audit explicitly identified math terms against one lesson-standard lexicon."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


STUDENT_ALLOWED = {"SOURCE_EXPLICIT", "VERIFIED_PRIOR", "TEACHER_APPROVED"}
TEACHER_ALLOWED = STUDENT_ALLOWED | {"TEACHER_ONLY"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check known terms found in a text file and/or candidate terms explicitly "
            "listed by the caller against one CURRENT_VERIFIED lesson lexicon. "
            "Unknown professional terms remain blocked."
        )
    )
    parser.add_argument("--lexicon", required=True, type=Path)
    parser.add_argument("--edition", required=True)
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--audience", choices=("student", "teacher"), required=True)
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--terms", nargs="*", default=[])
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def unique_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def pick_record(
    term: str,
    entries: list[dict[str, Any]],
    lesson_id: str,
) -> dict[str, Any] | None:
    matches = [
        entry
        for entry in entries
        if entry.get("term") == term
        and (
            not entry.get("lesson_ids")
            or lesson_id in entry.get("lesson_ids", [])
        )
    ]
    return matches[0] if matches else None


def validate_lexicon_scope(
    lexicon: dict[str, Any],
    edition: str,
    lesson_id: str,
) -> None:
    if lexicon.get("lexicon_type") != "LESSON_STANDARD":
        raise SystemExit("Lexicon is not a LESSON_STANDARD file.")
    if lexicon.get("lexicon_status") != "CURRENT_VERIFIED":
        raise SystemExit("Lexicon is not CURRENT_VERIFIED.")
    if lexicon.get("edition") != edition:
        raise SystemExit(
            f"Edition mismatch: lexicon={lexicon.get('edition')!r}, requested={edition!r}."
        )
    if lexicon.get("lesson_id") != lesson_id:
        raise SystemExit(
            "Lesson mismatch: "
            f"lexicon={lexicon.get('lesson_id')!r}, requested={lesson_id!r}."
        )


def audit_term(
    term: str,
    entries: list[dict[str, Any]],
    lesson_id: str,
    audience: str,
) -> dict[str, Any]:
    record = pick_record(term, entries, lesson_id)
    if record is None:
        return {
            "term": term,
            "verdict": "BLOCK",
            "reason": "UNKNOWN_PROFESSIONAL_TERM",
            "status": "UNKNOWN",
            "replacement": None,
            "evidence": [],
        }

    status = record.get("status", "UNKNOWN")
    audiences = set(record.get("audiences", []))
    allowed_statuses = STUDENT_ALLOWED if audience == "student" else TEACHER_ALLOWED
    allowed = status in allowed_statuses and audience in audiences

    if allowed and status == "TEACHER_ONLY":
        verdict = "ALLOW_WITH_EXPLANATION"
        reason = "TEACHER_ONLY_REQUIRES_IMMEDIATE_EXPLANATION"
    elif allowed:
        verdict = "ALLOW"
        reason = "EVIDENCE_BACKED_FOR_SCOPE"
    else:
        verdict = "BLOCK"
        reason = f"{status}_NOT_ALLOWED_FOR_{audience.upper()}"

    return {
        "term": term,
        "verdict": verdict,
        "reason": reason,
        "status": status,
        "preferred_expression": record.get("preferred_expression"),
        "replacement": record.get("plain_replacement"),
        "evidence": record.get("source_evidence", []),
    }


def main() -> int:
    args = parse_args()
    lexicon = read_json(args.lexicon)
    validate_lexicon_scope(lexicon, args.edition, args.lesson_id)
    entries = lexicon.get("entries", [])

    candidates = list(args.terms)
    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8")
        candidates.extend(
            entry["term"]
            for entry in entries
            if entry.get("term") and entry["term"] in text
        )

    candidates = unique_in_order(candidates)
    if not candidates:
        raise SystemExit("No terms found. Pass --terms and/or --text-file.")

    results = [
        audit_term(
            term=term,
            entries=entries,
            lesson_id=args.lesson_id,
            audience=args.audience,
        )
        for term in candidates
    ]
    blocked = [result for result in results if result["verdict"] == "BLOCK"]
    report = {
        "lexicon_ref": {
            "lexicon_id": lexicon.get("lexicon_id"),
            "version": lexicon.get("version"),
            "status": lexicon.get("lexicon_status"),
            "path": str(args.lexicon),
        },
        "lexicon_id": lexicon.get("lexicon_id"),
        "lexicon_schema_version": lexicon.get("schema_version"),
        "lexicon_version": lexicon.get("version"),
        "lexicon_status": lexicon.get("lexicon_status"),
        "edition": args.edition,
        "lesson_id": args.lesson_id,
        "audience": args.audience,
        "overall": "FAIL" if blocked else "PASS",
        "terms_used": candidates,
        "blocked_terms": [result["term"] for result in blocked],
        "replacements": [
            {
                "term": result["term"],
                "replacement": result.get("replacement"),
            }
            for result in blocked
            if result.get("replacement")
        ],
        "candidate_term_count": len(candidates),
        "blocked_term_count": len(blocked),
        "results": results,
        "limitation": (
            "This script checks lesson-lexicon matches and caller-supplied candidates. "
            "The caller must still extract every professional term and run the classroom-fluency gate."
        ),
    }
    payload = json.dumps(
        report,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
    ) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
