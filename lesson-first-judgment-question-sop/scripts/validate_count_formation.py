#!/usr/bin/env python3
"""Validate count-formation evidence for formal judgment-question packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


READY = "READY"
COUNT_SOURCE = "DERIVED_FROM_DIAGNOSTIC_UNITS"
FORBIDDEN_COUNT_KEYS = {
    "target_item_count",
    "default_item_count",
    "required_item_count",
    "fixed_item_count",
    "item_quota",
    "target_count",
    "default_count",
}
UNIT_FIELDS = (
    "unit_id",
    "source_proposition",
    "changed_boundary",
    "cognitive_action",
    "necessity_reason",
)


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def canonical_fingerprint(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def find_forbidden_keys(value: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_COUNT_KEYS:
                hits.append(path)
            hits.extend(find_forbidden_keys(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{prefix}[{index}]"))
    return hits


def normalized_action_signature(units: list[dict[str, Any]]) -> tuple[str, ...]:
    actions: list[str] = []
    for unit in units:
        raw = str(unit.get("cognitive_action", "")).strip().lower()
        actions.append(re.sub(r"\s+", "", raw))
    return tuple(actions)


def validate_package(path: Path, *, allow_non_ready: bool) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    try:
        package = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "file": str(path),
            "status": "FAIL",
            "failures": [f"无法读取JSON：{exc}"],
            "warnings": [],
        }

    if not isinstance(package, dict):
        return {
            "file": str(path),
            "status": "FAIL",
            "failures": ["题包顶层必须是JSON对象"],
            "warnings": [],
        }

    package_status = package.get("status")
    if package_status != READY:
        message = f"正式校验只接受 READY 题包，实际为 {package_status!r}"
        if allow_non_ready:
            warnings.append(message)
        else:
            failures.append(message)

    receipt = package.get("count_formation_receipt")
    if not isinstance(receipt, dict):
        failures.append("缺少 count_formation_receipt 对象")
        receipt = {}

    forbidden_paths = find_forbidden_keys(receipt)
    if forbidden_paths:
        failures.append("题数形成凭证含预设题数字段：" + "、".join(forbidden_paths))

    if receipt.get("count_source") != COUNT_SOURCE:
        failures.append(f"count_source 必须为 {COUNT_SOURCE}")
    if receipt.get("overall") != "PASS":
        failures.append("count_formation_receipt.overall 必须为 PASS")

    contract = receipt.get("diagnostic_contract")
    if not isinstance(contract, dict):
        failures.append("缺少 diagnostic_contract 对象")
        contract = {}
    if not nonempty_string(contract.get("contract_id")):
        failures.append("diagnostic_contract.contract_id 不能为空")
    if not nonempty_string(contract.get("lesson_profile_fingerprint")):
        failures.append("diagnostic_contract.lesson_profile_fingerprint 不能为空")
    if contract.get("created_before_candidates") is not True:
        failures.append("diagnostic_contract 必须声明 created_before_candidates=true")

    lesson_profile = package.get("lesson_profile")
    if not isinstance(lesson_profile, dict):
        failures.append("lesson_profile 必须是对象")
        lesson_profile = {}
    expected_profile_fingerprint = canonical_fingerprint(lesson_profile)
    if contract.get("lesson_profile_fingerprint") != expected_profile_fingerprint:
        failures.append("lesson_profile_fingerprint 与当前 lesson_profile 的 SHA-256 不一致")
    expected_contract_fingerprint = canonical_fingerprint(contract)
    if receipt.get("diagnostic_contract_fingerprint") != expected_contract_fingerprint:
        failures.append("diagnostic_contract_fingerprint 与冻结诊断契约的 SHA-256 不一致")
    if receipt.get("candidate_generation_input_fingerprint") != expected_contract_fingerprint:
        failures.append("candidate_generation_input_fingerprint 与冻结诊断契约指纹不一致")

    raw_units = contract.get("diagnostic_units")
    if not isinstance(raw_units, list) or not raw_units:
        failures.append("diagnostic_units 必须是非空列表")
        raw_units = []
    units: list[dict[str, Any]] = []
    unit_ids: list[str] = []
    for index, unit in enumerate(raw_units):
        if not isinstance(unit, dict):
            failures.append(f"diagnostic_units[{index}] 必须是对象")
            continue
        units.append(unit)
        for field in UNIT_FIELDS:
            if not nonempty_string(unit.get(field)):
                failures.append(f"diagnostic_units[{index}].{field} 不能为空")
        if nonempty_string(unit.get("unit_id")):
            unit_ids.append(unit["unit_id"].strip())
    duplicated_units = duplicate_values(unit_ids)
    if duplicated_units:
        failures.append("诊断点ID重复：" + "、".join(duplicated_units))

    candidate_ids = receipt.get("candidate_item_ids")
    if not isinstance(candidate_ids, list) or not all(nonempty_string(x) for x in candidate_ids):
        failures.append("candidate_item_ids 必须是非空字符串列表")
        candidate_ids = []
    else:
        candidate_ids = [x.strip() for x in candidate_ids]
    duplicated_candidates = duplicate_values(candidate_ids)
    if duplicated_candidates:
        failures.append("候选题ID重复：" + "、".join(duplicated_candidates))
    candidate_count = receipt.get("candidate_item_count")
    if candidate_count != len(candidate_ids):
        failures.append(
            f"candidate_item_count 与候选ID数量不一致：{candidate_count!r} != {len(candidate_ids)}"
        )

    retained_ids = receipt.get("retained_item_ids")
    if not isinstance(retained_ids, list) or not all(nonempty_string(x) for x in retained_ids):
        failures.append("retained_item_ids 必须是非空字符串列表")
        retained_ids = []
    else:
        retained_ids = [x.strip() for x in retained_ids]
    duplicated_retained = duplicate_values(retained_ids)
    if duplicated_retained:
        failures.append("保留题ID重复：" + "、".join(duplicated_retained))

    dropped_items = receipt.get("dropped_items")
    if not isinstance(dropped_items, list):
        failures.append("dropped_items 必须是列表")
        dropped_items = []
    dropped_ids: list[str] = []
    for index, dropped in enumerate(dropped_items):
        if not isinstance(dropped, dict):
            failures.append(f"dropped_items[{index}] 必须是对象")
            continue
        item_id = dropped.get("item_id")
        reason = dropped.get("reason")
        if not nonempty_string(item_id):
            failures.append(f"dropped_items[{index}].item_id 不能为空")
        else:
            dropped_ids.append(item_id.strip())
        if not nonempty_string(reason):
            failures.append(f"dropped_items[{index}].reason 不能为空")
    duplicated_dropped = duplicate_values(dropped_ids)
    if duplicated_dropped:
        failures.append("淘汰题ID重复：" + "、".join(duplicated_dropped))
    overlap = sorted(set(retained_ids) & set(dropped_ids))
    if overlap:
        failures.append("题目不能同时保留和淘汰：" + "、".join(overlap))
    if set(candidate_ids) != set(retained_ids) | set(dropped_ids):
        failures.append("候选题集合必须恰好等于保留题与淘汰题的并集")

    items = package.get("items")
    if not isinstance(items, list):
        failures.append("items 必须是列表")
        items = []
    kept_items: list[dict[str, Any]] = []
    all_item_ids: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            failures.append(f"items[{index}] 必须是对象")
            continue
        item_id = item.get("item_id")
        if not nonempty_string(item_id):
            failures.append(f"items[{index}].item_id 不能为空")
            continue
        item_id = item_id.strip()
        all_item_ids.append(item_id)
        if item.get("audit_status") == "KEEP":
            kept_items.append(item)
    duplicated_items = duplicate_values(all_item_ids)
    if duplicated_items:
        failures.append("items 中 item_id 重复：" + "、".join(duplicated_items))

    kept_ids = [str(item.get("item_id", "")).strip() for item in kept_items]
    if set(kept_ids) != set(retained_ids):
        failures.append("items 中 KEEP 题目与 retained_item_ids 不一致")

    primary_units: list[str] = []
    primary_by_item: dict[str, str] = {}
    for item in kept_items:
        item_id = str(item.get("item_id", "")).strip()
        primary = item.get("primary_diagnostic_unit_id")
        if not nonempty_string(primary):
            failures.append(f"保留题 {item_id} 缺少 primary_diagnostic_unit_id")
            continue
        primary = primary.strip()
        primary_units.append(primary)
        primary_by_item[item_id] = primary
        if primary not in set(unit_ids):
            failures.append(f"保留题 {item_id} 引用了不存在的诊断点 {primary}")
    duplicated_primary = duplicate_values(primary_units)
    if duplicated_primary:
        failures.append("多个保留题共享同一主要诊断点：" + "、".join(duplicated_primary))
    if set(primary_units) != set(unit_ids):
        failures.append("正式题的主要诊断点必须与诊断契约中的诊断点一一对应")

    package_final_count = package.get("final_item_count")
    receipt_final_count = receipt.get("final_item_count")
    expected_final_count = len(kept_items)
    counts = {
        "package.final_item_count": package_final_count,
        "receipt.final_item_count": receipt_final_count,
        "retained_item_ids": len(retained_ids),
        "KEEP items": expected_final_count,
        "diagnostic_units": len(unit_ids),
    }
    if any(value != expected_final_count for value in counts.values()):
        failures.append("最终题数不一致：" + json.dumps(counts, ensure_ascii=False))

    deletion_tests = receipt.get("deletion_tests")
    if not isinstance(deletion_tests, list):
        failures.append("deletion_tests 必须是列表")
        deletion_tests = []
    deletion_by_item: dict[str, dict[str, Any]] = {}
    for index, test in enumerate(deletion_tests):
        if not isinstance(test, dict):
            failures.append(f"deletion_tests[{index}] 必须是对象")
            continue
        item_id = test.get("item_id")
        if not nonempty_string(item_id):
            failures.append(f"deletion_tests[{index}].item_id 不能为空")
            continue
        item_id = item_id.strip()
        if item_id in deletion_by_item:
            failures.append(f"删除测试重复：{item_id}")
        deletion_by_item[item_id] = test
    if set(deletion_by_item) != set(retained_ids):
        failures.append("每道保留题必须且只能有一条删除测试")
    for item_id in retained_ids:
        test = deletion_by_item.get(item_id, {})
        lost_units = test.get("would_lose_unit_ids")
        if not isinstance(lost_units, list) or not all(nonempty_string(x) for x in lost_units):
            failures.append(f"删除测试 {item_id} 缺少 would_lose_unit_ids")
            continue
        lost_units = [x.strip() for x in lost_units]
        primary = primary_by_item.get(item_id)
        if primary and primary not in lost_units:
            failures.append(f"删除测试 {item_id} 未声明会失去其主要诊断点 {primary}")
        if test.get("conclusion") != "KEEP":
            failures.append(f"保留题 {item_id} 的删除测试结论必须为 KEEP")

    template_audit = receipt.get("template_contamination_audit")
    if not isinstance(template_audit, dict):
        failures.append("缺少 template_contamination_audit")
        template_audit = {}
    for field in (
        "count_was_precommitted",
        "numbered_slot_template_used",
        "prior_lesson_count_used",
        "quota_or_truth_pattern_used",
    ):
        if template_audit.get(field) is not False:
            failures.append(f"template_contamination_audit.{field} 必须为 false")
    if template_audit.get("overall") != "PASS":
        failures.append("template_contamination_audit.overall 必须为 PASS")

    batch_audit = receipt.get("batch_independence_audit")
    if not isinstance(batch_audit, dict):
        failures.append("缺少 batch_independence_audit")
        batch_audit = {}
    if batch_audit.get("lesson_contract_frozen_independently") is not True:
        failures.append("batch_independence_audit.lesson_contract_frozen_independently 必须为 true")
    for field in ("other_lesson_counts_visible_before_freeze", "shared_numbered_scaffold_used"):
        if batch_audit.get(field) is not False:
            failures.append(f"batch_independence_audit.{field} 必须为 false")
    if batch_audit.get("overall") != "PASS":
        failures.append("batch_independence_audit.overall 必须为 PASS")

    status = "FAIL" if failures else ("WARN" if warnings else "PASS")
    return {
        "file": str(path),
        "lesson_title": package.get("lesson_profile", {}).get("lesson_title")
        if isinstance(package.get("lesson_profile"), dict)
        else None,
        "status": status,
        "final_item_count": expected_final_count,
        "action_signature": normalized_action_signature(units),
        "failures": failures,
        "warnings": warnings,
    }


def batch_warnings(results: list[dict[str, Any]]) -> list[str]:
    groups: dict[tuple[int, tuple[str, ...]], list[str]] = defaultdict(list)
    for result in results:
        if result.get("status") == "FAIL":
            continue
        count = result.get("final_item_count")
        signature = result.get("action_signature")
        if isinstance(count, int) and isinstance(signature, tuple):
            groups[(count, signature)].append(result.get("lesson_title") or result["file"])
    warnings: list[str] = []
    for (count, signature), lessons in groups.items():
        if len(lessons) >= 3:
            warnings.append(
                "三个及以上题包具有相同题数和认知动作顺序，需人工复核是否复制模板："
                f"题数={count}，认知动作={list(signature)}，课时={lessons}"
            )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="校验判断题题数形成凭证，并对多题包执行模板相似预警。"
    )
    parser.add_argument("packages", nargs="+", type=Path, help="判断题包 JSON 文件")
    parser.add_argument(
        "--allow-non-ready",
        action="store_true",
        help="允许非 READY 题包进入结构检查，但仍给出警告。",
    )
    args = parser.parse_args()

    results = [
        validate_package(path, allow_non_ready=args.allow_non_ready) for path in args.packages
    ]
    warnings = batch_warnings(results)
    overall = "FAIL" if any(result["status"] == "FAIL" for result in results) else (
        "WARN" if warnings or any(result["status"] == "WARN" for result in results) else "PASS"
    )
    output = {
        "status": overall,
        "packages": [
            {key: value for key, value in result.items() if key != "action_signature"}
            for result in results
        ],
        "batch_warnings": warnings,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if overall == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
