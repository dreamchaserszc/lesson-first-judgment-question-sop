# 输出契约

## 一、题包状态

- `READY`：所有正式题通过质量门，可以直接使用。
- `PENDING_JUDGMENT`：已完整生成题包，但课时理解卡中仍有会影响实际课堂对齐的 AI 推定范围或关键问题，需教师核对。
- `INSUFFICIENT_INPUT`：无法从输入形成可靠的核心正确命题，不生成正式题包。

不设默认题数或目标题数。最终题数等于通过逐题质量门、认知动作去重和删除测试后保留的不可替代题目数；当继续生成只能造成重复、越界、降质或凑数时自动停止。

## 二、默认教师可见输出

按以下顺序输出：

### 1. 课时理解卡

```text
课时：
本次主要内容：
命题边界（包含）：
命题边界（不包含）：
本次依据：
AI 推定内容：
待教师修正或确认：
状态：
```

课时理解卡必须位于判断题之前。只有课时标题时也要直接生成这张卡，明确展示 AI 猜到的课程内容和边界；有教师说明或课堂材料时，区分材料明示内容与 AI 补全内容。

### 2. 学生版

只显示题号、题干和作答位置，不显示答案、分类、设计理由或审核信息。

### 3. 教师版

| 题号 | 答案 | 简要证明或有效反例 |
|---:|---|---|

### 4. 必要的补充说明

只在必要时列出：自动停止出题的原因、无法在课时理解卡中简洁表达的关键风险。不要重复卡片中已经列出的边界。

## 三、标准结构化题包

项目或完整审核模式应保留以下包级字段：

```text
lesson_profile
lesson_lexicon_ref
status
input_summary
assumptions
excluded_or_uncertain_scope
final_item_count
terminology_audit
fluency_audit
artifact_manifest
items
```

`lesson_profile` 至少保留：

```text
lesson_title
main_content
included_scope
excluded_scope
evidence_basis
ai_inferred_items
uncertain_items
```

内部 `lesson_lexicon_ref` 只引用本课唯一现行标准词表，不复制整份词表：

```text
lesson_id
lexicon_id
lexicon_version
lexicon_status
lexicon_path
source_basis
```

同一课时重复运行时，`lesson_lexicon_ref` 必须指向同一现行词表；不得在题包中沉淀另一份运行词库。`terminology_audit` 是每次运行的新产物，至少记录：

```text
lexicon_ref
audience
terms_used
blocked_terms
replacements
overall
```

`SOURCE_EXPLICIT`、`VERIFIED_PRIOR` 和 `TEACHER_APPROVED` 可以进入学生版；`TEACHER_ONLY` 不得进入学生题干；`UNVERIFIED`、`AI_COINED` 和未知专业词必须从正式学生版和教师简析中移除。

`fluency_audit` 至少记录每题的顺读状态和必要改写：

```text
item_id
status = PASS | REVISE | DROP
issue_types
before
after
reason
```

`artifact_manifest` 仅用于文件型运行，按 `run-artifact-policy.md` 记录每道关键质量门的输入、输出与 `PASS_NO_CHANGE` 状态；纯聊天输出可以省略文件路径，但不得省略题目稳定编号和审核状态。

每道题保留：

```text
item_id
display_order
statement
answer
evidence_type
proof_or_counterexample
source_proposition
changed_boundary
cognitive_action
possible_confusion
scope_status
terms_used
term_audit_status
fluency_audit_status
disambiguation_audit_status
revision_trace
audit_status
```

`possible_confusion` 只能写成待追问验证的候选理解偏差，不能写成已经诊断的学生错因。

`source_proposition` 必须能够追溯到 `lesson_profile.main_content` 中的一个内容；无法对应的题目不得进入正式题包。

教师修改课时理解卡后，以修改后的 `lesson_profile` 为最高优先级输入，只重新生成或最小修改受影响的题目，并再次执行全部质量门。

任何正式题的 `term_audit_status` 不是 `PASS` 时，必须修改或淘汰；不得仅把题包降为 `PENDING_JUDGMENT` 后继续向学生展示未核验术语。确需教师确认某词是否已教时，先用普通语言完成学生版，再把该词列入待确认项。

任何正式题的 `fluency_audit_status` 或 `disambiguation_audit_status` 不是 `PASS` 时，也必须修改或淘汰。`item_id` 在原始稿、各质量门阶段稿和最终稿中保持不变；最终展示顺序由 `display_order` 决定，不能因删除题目而改写其内部身份。

## 四、项目适配边界

项目可在合格题包之后增加：

- 对应作业题；
- PPT 支撑缺口；
- 建议插入位置；
- 建议追问；
- 项目表格编号与文件路径。

项目不得修改：

- `statement` 的数学含义；
- `answer`；
- `proof_or_counterexample`；
- `source_proposition`；
- `audit_status`。

## 五、默认不展示

不要默认输出：

- 大段内部推理或生成流水账；
- 被淘汰的候选题；
- 母题、错因树和旧表6编号；
- 强制难度分类或真假配额；
- 没有证据支持的学生错因结论。
- 课时标准词表全文和逐词内部审计流水。

用户要求完整审核时，可以展示简洁的来源命题、改变边界、认知动作和审核结论，但仍不需要输出内部自言自语。
