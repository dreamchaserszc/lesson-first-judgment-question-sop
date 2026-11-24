#!/usr/bin/env python3
"""Validate dual-branch judgment packages (v2.1 natural-Chinese checks + v2.0 compatibility)."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
from validate_count_formation import validate_package, nonempty_string

BRANCHES = {"KNOWLEDGE", "STUDENT_THINKING"}
FORBIDDEN_TAILS = (
    "他的想法正确",
    "她的想法正确",
    "他的判断正确",
    "她的判断正确",
    "他的方法正确",
    "她的方法正确",
    "他的作法正确",
    "她的作法正确",
    "他的说法正确",
    "她的说法正确",
)
FORBIDDEN_PATCHES = (
    "边界忽略不计",
    "对于任意给定的",
    "对于任意给出的",
)
PERSON_MARKERS = ("小明", "小华", "小丽", "小芳", "小强", "小林", "小敏", "小海", "小安", "小杰", "小红")


def visible_chinese_len(text: str) -> int:
    """Count readable length after collapsing inline LaTeX math expressions to a short token."""
    cleaned = re.sub(r"\$[^$]+\$|\\\([^)]+\\\)", "式", text)
    cleaned = re.sub(r"[（(]\s*[）)]\s*$", "", cleaned)
    return len(cleaned.strip())


def check_natural_language(bid: str, iid: str, stmt: str, failures: list[str], warnings: list[str]) -> bool:
    for tail in FORBIDDEN_TAILS:
        if tail in stmt:
            failures.append(f"{iid}: 含禁用句尾复读挂件『{tail}』")
    for patch in FORBIDDEN_PATCHES:
        if patch in stmt:
            failures.append(f"{iid}: 含法条腔/免责补丁『{patch}』")
    vlen = visible_chinese_len(stmt)
    limit = 42 if bid == "KNOWLEDGE" else 62
    if vlen > limit:
        warnings.append(f"{iid}: 题干偏长（折算约 {vlen} 字 > {limit} 字），请复核是否可拆短或脱敏")
    return any(p in stmt for p in PERSON_MARKERS)


def validate_v21(path: Path, package: dict, *, allow_non_ready: bool = False) -> dict:
    failures, warnings, branch_summaries = [], [], []
    if package.get("output_mode") != "DUAL_BRANCH":
        failures.append("output_mode 必须为 DUAL_BRANCH")
    status = package.get("status")
    if status != "READY":
        (warnings if allow_non_ready else failures).append(f"题包状态为 {status!r}（非 READY）")
    if not isinstance(package.get("lesson_profile"), dict):
        failures.append("缺少 lesson_profile 对象")

    branches = package.get("branches")
    if not isinstance(branches, list) or len(branches) != 2:
        failures.append("branches 必须包含 KNOWLEDGE 与 STUDENT_THINKING 两组")
        branches = []
    elif {str(b.get("branch_id")) for b in branches if isinstance(b, dict)} != BRANCHES:
        failures.append("branches 必须各有一组 KNOWLEDGE 和 STUDENT_THINKING")

    all_ids: set[str] = set()
    total = 0
    thinking_total = 0
    thinking_person_count = 0

    for branch in branches:
        if not isinstance(branch, dict):
            continue
        bid = str(branch.get("branch_id"))
        items = branch.get("items")
        if not isinstance(items, list):
            failures.append(f"{bid}: items 必须是列表")
            continue
        branch_summaries.append({"branch_id": bid, "final_item_count": len(items)})
        total += len(items)
        for item in items:
            if not isinstance(item, dict):
                failures.append(f"{bid}: 题目条目必须是对象")
                continue
            iid = str(item.get("item_id", "")).strip()
            if not iid:
                failures.append(f"{bid}: 存在缺少 item_id 的题目")
                continue
            if iid in all_ids:
                failures.append(f"item_id 重复: {iid}")
            all_ids.add(iid)
            stmt = item.get("statement")
            if not nonempty_string(stmt):
                failures.append(f"{iid}: 缺少 statement")
                stmt = ""
            if type(item.get("answer")) is not bool:
                failures.append(f"{iid}: answer 必须为布尔值")
            if not nonempty_string(item.get("proof_or_counterexample")):
                failures.append(f"{iid}: 缺少 proof_or_counterexample")
            has_person = check_natural_language(bid, iid, str(stmt), failures, warnings)
            if bid == "STUDENT_THINKING":
                thinking_total += 1
                if has_person:
                    thinking_person_count += 1

    if total == 0:
        failures.append("题包没有任何保留题")
    if thinking_total >= 3 and thinking_person_count == thinking_total:
        warnings.append("STUDENT_THINKING 全部题目均套用人物名字，建议将直观算式/图形题改为客观推理句")

    rewrite_log = package.get("spoken_rewrite_log")
    if not isinstance(rewrite_log, list) or not rewrite_log:
        warnings.append("缺少非空 spoken_rewrite_log（请如实记录口语脱敏重写或淘汰的初稿句，勿空转跳过）")

    overall = "FAIL" if failures else "WARN" if warnings else "PASS"
    return {
        "file": str(path),
        "schema_version": "2.1",
        "status": overall,
        "final_item_count": total,
        "branches": branch_summaries,
        "failures": failures,
        "warnings": warnings,
    }


def validate_v20_legacy(path: Path, package: dict, *, allow_non_ready: bool = False) -> dict:
    failures, warnings, results = [], [], []
    if package.get("output_mode") != "DUAL_BRANCH":
        failures.append("完整输出必须声明 output_mode=DUAL_BRANCH")
    if package.get("status") != "READY":
        (warnings if allow_non_ready else failures).append("完整包未达到 READY")
    if not isinstance(package.get("lesson_profile"), dict):
        failures.append("缺少共享 lesson_profile")
    branches = package.get("branches") if isinstance(package.get("branches"), list) else []
    ids = [b.get("branch_id") for b in branches if isinstance(b, dict)]
    if len(branches) != 2 or set(str(x) for x in ids) != BRANCHES:
        failures.append("必须各有一组 KNOWLEDGE 和 STUDENT_THINKING")
    total = 0
    with tempfile.TemporaryDirectory(prefix="judgment-dual-check-") as directory:
        for index, branch in enumerate(branches):
            if not isinstance(branch, dict):
                continue
            bid = str(branch.get("branch_id"))
            single_path = Path(directory) / f"branch-{index}.json"
            single_path.write_text(json.dumps(branch, ensure_ascii=False), encoding="utf-8")
            result = validate_package(single_path, allow_non_ready=allow_non_ready)
            failures.extend(f"{bid}: {x}" for x in result["failures"])
            warnings.extend(f"{bid}: {x}" for x in result["warnings"])
            results.append({"branch_id": bid, "status": result["status"], "final_item_count": result["final_item_count"]})
            total += result["final_item_count"]
    return {
        "file": str(path),
        "schema_version": "2.0",
        "status": "FAIL" if failures else "WARN" if warnings else "PASS",
        "final_item_count": total,
        "branches": results,
        "failures": failures,
        "warnings": warnings,
    }


def validate_dual(path: Path, *, allow_non_ready: bool = False) -> dict:
    try:
        package = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return {"file": str(path), "status": "FAIL", "failures": [str(exc)], "warnings": []}
    if not isinstance(package, dict):
        return {"file": str(path), "status": "FAIL", "failures": ["顶层必须是对象"], "warnings": []}
    ver = str(package.get("schema_version", ""))
    if ver == "2.1":
        return validate_v21(path, package, allow_non_ready=allow_non_ready)
    if ver == "2.0":
        return validate_v20_legacy(path, package, allow_non_ready=allow_non_ready)
    return {"file": str(path), "status": "FAIL", "failures": [f"不支持的 schema_version: {ver!r}（请使用 2.1）"], "warnings": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packages", nargs="+", type=Path)
    parser.add_argument("--allow-non-ready", action="store_true")
    args = parser.parse_args()
    results = [validate_dual(p, allow_non_ready=args.allow_non_ready) for p in args.packages]
    status = "FAIL" if any(r["status"] == "FAIL" for r in results) else "WARN" if any(r["status"] == "WARN" for r in results) else "PASS"
    print(json.dumps({"status": status, "packages": results}, ensure_ascii=False, indent=2))
    return int(status == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
