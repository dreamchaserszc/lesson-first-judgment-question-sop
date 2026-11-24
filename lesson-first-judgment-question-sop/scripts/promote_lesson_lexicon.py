#!/usr/bin/env python3
"""Validate and atomically promote a new lesson lexicon into the Skill.

The promoter only installs a missing lesson lexicon or reuses an existing
byte-identical lexicon. It never overwrites a different existing file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROMOTER_VERSION = "1.0"
ALLOWED_STATUSES = {
    "SOURCE_EXPLICIT",
    "VERIFIED_PRIOR",
    "TEACHER_APPROVED",
    "TEACHER_ONLY",
    "UNVERIFIED",
    "AI_COINED",
}
STUDENT_STATUSES = {"SOURCE_EXPLICIT", "VERIFIED_PRIOR", "TEACHER_APPROVED"}


class PromotionError(Exception):
    """A safe, user-reviewable promotion failure."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromotionError(f"JSON无法读取：{path}；{exc}") from exc
    if not isinstance(value, dict):
        raise PromotionError(f"JSON顶层必须为对象：{path}")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PromotionError(f"缺少有效字段：{label}")
    return value.strip()


def validate_candidate(data: dict[str, Any], expected_lesson_id: str) -> None:
    if str(data.get("schema_version")) != "0.2":
        raise PromotionError("候选词表schema_version必须为0.2")
    lesson_id = require_text(data.get("lesson_id"), "lesson_id")
    if lesson_id != expected_lesson_id:
        raise PromotionError(f"课时ID不一致：期望{expected_lesson_id}，实际{lesson_id}")
    if require_text(data.get("lexicon_id"), "lexicon_id") != lesson_id:
        raise PromotionError("lexicon_id必须与lesson_id相同")
    if data.get("lexicon_type") != "LESSON_STANDARD":
        raise PromotionError("lexicon_type必须为LESSON_STANDARD")
    if data.get("lexicon_status") != "CURRENT_VERIFIED":
        raise PromotionError("lexicon_status必须为CURRENT_VERIFIED")
    for field in ("version", "edition", "lesson_title", "source_policy", "reuse_policy", "reviewed_on"):
        require_text(data.get(field), field)

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise PromotionError("entries必须为非空数组")
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise PromotionError(f"第{index}个词条不是对象")
        term = require_text(entry.get("term"), f"entries[{index}].term")
        if term in seen:
            raise PromotionError(f"词条重复：{term}")
        seen.add(term)
        status = require_text(entry.get("status"), f"{term}.status")
        if status not in ALLOWED_STATUSES:
            raise PromotionError(f"词条状态不受支持：{term}={status}")
        evidence = entry.get("source_evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            raise PromotionError(f"词条缺少来源证据：{term}")
        audiences = entry.get("audiences")
        if not isinstance(audiences, list):
            raise PromotionError(f"词条audiences必须为数组：{term}")
        audience_set = {str(item) for item in audiences}
        preferred = entry.get("preferred_expression")
        if status in STUDENT_STATUSES:
            if not ({"student", "teacher"} & audience_set):
                raise PromotionError(f"准入词条缺少师生使用对象：{term}")
            require_text(preferred, f"{term}.preferred_expression")
        elif status == "TEACHER_ONLY":
            if audience_set != {"teacher"}:
                raise PromotionError(f"TEACHER_ONLY只能面向teacher：{term}")
            require_text(preferred, f"{term}.preferred_expression")
        elif status == "UNVERIFIED":
            if audience_set:
                raise PromotionError(f"UNVERIFIED不得面向师生：{term}")
            if preferred not in (None, ""):
                raise PromotionError(f"UNVERIFIED不得设置preferred_expression：{term}")
        elif status == "AI_COINED":
            if audience_set not in (set(), {"internal"}):
                raise PromotionError(f"AI_COINED只能面向internal：{term}")
            if preferred not in (None, ""):
                raise PromotionError(f"AI_COINED不得设置preferred_expression：{term}")


def find_current_matches(lexicon_dir: Path, lesson_id: str) -> list[Path]:
    matches: list[Path] = []
    for path in sorted(lexicon_dir.glob("*.json")):
        try:
            data = read_json(path)
        except PromotionError:
            continue
        if data.get("lesson_id") == lesson_id and data.get("lexicon_status") == "CURRENT_VERIFIED":
            matches.append(path.resolve())
    return matches


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def write_receipt(
    receipt_path: Path,
    *,
    status: str,
    action: str,
    lesson_id: str,
    candidate_path: Path,
    candidate_hash: str,
    target_path: Path,
    target_hash: str | None,
    message: str,
    unique_current_count: int,
) -> None:
    receipt = {
        "schemaVersion": "1.0",
        "promoterVersion": PROMOTER_VERSION,
        "status": status,
        "action": action,
        "lessonId": lesson_id,
        "candidatePath": candidate_path.as_posix(),
        "candidateSha256": candidate_hash,
        "formalLexiconPath": target_path.as_posix(),
        "formalLexiconSha256": target_hash or "NOT_APPLICABLE",
        "lexiconStatus": "CURRENT_VERIFIED" if status == "PASS" else "NOT_APPLICABLE",
        "uniqueCurrentCount": unique_current_count,
        "message": message,
        "createdAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    write_json_atomic(receipt_path, receipt)


def promote(args: argparse.Namespace) -> int:
    candidate = args.candidate.resolve()
    skill_root = Path(__file__).resolve().parent.parent
    shared_lexicons = skill_root.parent / "_shared" / "lesson-first-math" / "references" / "lesson-lexicons"
    lexicon_dir = shared_lexicons.resolve() if shared_lexicons.parent.exists() else (skill_root / "references" / "lesson-lexicons").resolve()
    receipt = args.receipt.resolve()
    lesson_id = args.lesson_id.strip()
    if (
        not lesson_id
        or lesson_id in {".", ".."}
        or Path(lesson_id).name != lesson_id
        or any(character in lesson_id for character in '<>:"/\\|?*')
        or any(ord(character) < 32 for character in lesson_id)
    ):
        raise PromotionError("lesson_id不能包含路径分隔符、Windows保留字符或控制字符")
    target = (lexicon_dir / f"{lesson_id}.json").resolve()
    if not candidate.is_file():
        raise PromotionError(f"候选词表不存在：{candidate}")
    if candidate.parent == lexicon_dir:
        raise PromotionError("候选词表不得直接放在正式词表目录中")
    lexicon_dir.mkdir(parents=True, exist_ok=True)
    candidate_hash = sha256(candidate)
    installed_new = False

    try:
        data = read_json(candidate)
        validate_candidate(data, lesson_id)
        matches = find_current_matches(lexicon_dir, lesson_id)
        if len(matches) > 1:
            raise PromotionError(f"发现{len(matches)}份CURRENT_VERIFIED同课词表，禁止自动处理")

        if target.exists():
            target_hash = sha256(target)
            if target_hash != candidate_hash:
                raise PromotionError("正式目录已有不同内容的同课词表，必须进入人工维护与版本升级流程")
            action = "REUSED"
        else:
            if matches:
                raise PromotionError(f"同课现行词表文件名不符合唯一目标：{matches[0]}")
            descriptor, temporary_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=lexicon_dir)
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                temporary.write_bytes(candidate.read_bytes())
                if sha256(temporary) != candidate_hash:
                    raise PromotionError("候选复制到临时文件后哈希不一致")
                os.replace(temporary, target)
                installed_new = True
            finally:
                if temporary.exists():
                    temporary.unlink()
            action = "INSTALLED"

        matches_after = find_current_matches(lexicon_dir, lesson_id)
        target_hash = sha256(target)
        if matches_after != [target] or target_hash != candidate_hash:
            raise PromotionError("自动沉淀后的唯一性或SHA256复核失败")
        write_receipt(
            receipt,
            status="PASS",
            action=action,
            lesson_id=lesson_id,
            candidate_path=candidate,
            candidate_hash=candidate_hash,
            target_path=target,
            target_hash=target_hash,
            message="首次新建已自动沉淀" if action == "INSTALLED" else "现行词表完全相同，已自动复用",
            unique_current_count=1,
        )
        if args.cleanup_candidate:
            candidate.unlink()
        print("PASS")
        print(f"action={action} lessonId={lesson_id} sha256={target_hash}")
        return 0
    except (PromotionError, OSError) as exc:
        if installed_new and target.is_file() and sha256(target) == candidate_hash:
            target.unlink()
        matches = find_current_matches(lexicon_dir, lesson_id)
        target_hash = sha256(target) if target.is_file() else None
        try:
            write_receipt(
                receipt,
                status="BLOCKED",
                action="BLOCKED_CONFLICT",
                lesson_id=lesson_id,
                candidate_path=candidate,
                candidate_hash=candidate_hash,
                target_path=target,
                target_hash=target_hash,
                message=str(exc),
                unique_current_count=len(matches),
            )
        except OSError as receipt_exc:
            print(f"ERROR: 回执写入失败：{receipt_exc}", file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="自动沉淀单课时标准词表；绝不覆盖不同内容的现行词表。")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--cleanup-candidate", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        raise SystemExit(promote(parse_args()))
    except PromotionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(3)
