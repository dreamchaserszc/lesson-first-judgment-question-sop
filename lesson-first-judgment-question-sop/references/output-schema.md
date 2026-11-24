# 输出契约与状态判定

## 一、题包状态（供教师及下游学习单组装判断）

- `READY`：课时材料明确或范围无实质争议，全部保留题已通过数学真值、术语准入、独立「口语脱敏重写关」与组内去重，可直接进入学习单或课堂投影。
- `PENDING_JUDGMENT`：已完整生成高质量题包，但因仅输入课题标题等原因含有 AI 推定的授课深度边界，待教师结合本班进度勾选。
- `INSUFFICIENT_INPUT`：输入信息不足以确定可靠的核心数学命题，不伪造题包。

## 二、默认教师可见输出（Markdown / 聊天）

按以下顺序清晰呈现，学生题目一律不使用表格承载：

### 1. 课时理解卡
- **课题**：
- **主要内容**：
- **包含范围**：
- **不包含范围**：
- **依据与待核对项**：
- **状态**：`READY` | `PENDING_JUDGMENT` | `INSUFFICIENT_INPUT`

### 2. 学生版
- 简短作答导语（需要时附一句 15 字以内的组首课堂约定，如 `（题中字母均取使原式有意义的值）` 或 `（题中的角均指同一平面内小于 180° 的角）`）
- **第一类：知识辨析型**（题号 ＋ 短句陈述 ＋ `（　　）`）
- **第二类：想法辨析型**（题号 ＋ 自然推理或情境想法 ＋ `（　　）`，严禁句尾追加 `他的想法正确。` 等复读挂件）

### 3. 教师版答案与简析
按两类分别给出题号、答案（`√` / `×`）及简明课内证明或具体反例。

### 4. 选用提示（按需简短给出）
标注跨组“可二选一”的题目对，以及针对当堂例题深浅的选做建议。

---

## 三、文件型运行的轻量结构化题包（`判断题包.json`）

当项目或学习单工作流要求落盘保存 JSON 时，使用轻量、诚实的 `schema_version = "2.1"` 结构（不再使用繁琐的 SHA-256 指纹自证，把算力用于真实语言打磨）：

```json
{
  "schema_version": "2.1",
  "output_mode": "DUAL_BRANCH",
  "status": "READY",
  "lesson_profile": {
    "lesson_id": "SYNTHETIC-G7-SYM-1",
    "lesson_title": "中心对称",
    "main_content": ["..."],
    "included_scope": ["..."],
    "excluded_scope": ["..."],
    "evidence_basis": ["..."]
  },
  "group_assumption": "可选的组首课堂约定，无则为空字符串",
  "branches": [
    {
      "branch_id": "KNOWLEDGE",
      "items": [
        {
          "item_id": "K1",
          "knowledge_point_id": "collinear",
          "statement": "成中心对称的两个图形，对应线段互相平行且相等。",
          "answer": false,
          "proof_or_counterexample": "对应线段平行或在同一直线上且相等；当对称中心在线段上时，两线段共线。"
        }
      ]
    },
    {
      "branch_id": "STUDENT_THINKING",
      "items": [
        {
          "item_id": "T1",
          "knowledge_point_id": "rotation_angle",
          "statement": "等边三角形绕某一点旋转 120° 后能与原来的图形重合，所以它是中心对称图形。",
          "answer": false,
          "proof_or_counterexample": "中心对称图形要求绕某点旋转 180° 后重合；等边三角形旋转 180° 后不能与原图重合。"
        }
      ]
    }
  ],
  "cross_branch_pairs": [
    {
      "item_ids": ["K2", "T3"],
      "note": "同考对称点连线中点性质，可二选一"
    }
  ],
  "spoken_rewrite_log": [
    {
      "before": "初稿中拗口、带法条补丁或剧透旁白的原句",
      "action": "REWRITE | DROP",
      "after": "口语脱敏重写后的定稿句（DROP 时为空）",
      "reason": "简明修改或淘汰原因"
    }
  ]
}
```

文件型完整输出可运行 `python scripts/validate_dual_output.py <判断题包.json>` 检查真实语言红线（如句尾复读尾巴、免责括号补丁、人物点名过载、超长拗口句及空转日志）。
