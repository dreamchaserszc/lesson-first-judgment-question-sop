[中文](README.md) | **English**

# Lesson-first Judgment Question SOP

![Lesson-first workflow from lesson understanding to quality review](assets/workflow-guizang.png)

> Understand the lesson first. Then generate judgment questions that can be proved, refuted, and traced back to what was actually taught.

`lesson-first-judgment-question-sop` is an open-source Codex Skill for generating, auditing, and minimally revising true/false judgment questions for Chinese junior-middle-school mathematics.

It accepts a lesson title, teacher notes, slides, textbook pages, lesson plans, or other classroom materials. Before writing questions, it produces a visible lesson profile that states what the lesson covers, what it excludes, which claims are evidence-backed, and which parts were inferred by AI.

**Language scope:** the student-facing output is designed for Chinese mathematics classrooms. This English README explains the method to the international open-source community; it does not turn the Skill into an English-language item generator.

**Release status:** public release candidate. This repository contains the original workflow, general-purpose validation code, and fully synthetic examples. It does not include copyrighted textbook pages, internal school materials, student data, or private lesson lexicons derived from those sources.

## The problem it solves

| Common approach | This Skill |
| --- | --- |
| Start from a quota such as “two basic items and two misconception items” | Start from the lesson content and its teaching boundary |
| Return questions and answer keys only | Require a general justification for true items and a valid counterexample for false items |
| Fill a fixed number of questions | Keep only items that pass every gate and add unique information |
| Treat mathematically valid wording as sufficient | Also check textbook terminology, classroom fluency, and natural disambiguation |
| Review each item in isolation | Run cognitive-overlap and deletion tests on the full set |
| Present a plausible student difficulty as a diagnosed misconception | Keep unverified hypotheses separate from evidence-backed findings |

## What it returns

The default teacher-visible output has four parts:

1. **Lesson profile** — main content, included scope, excluded scope, evidence basis, AI-inferred items, and unresolved items;
2. **Student version** — only questions with one defensible truth value and a distinct diagnostic purpose;
3. **Teacher version** — answers with a short proof, calculation, or valid counterexample;
4. **Structured record** — stable item IDs, terminology status, quality-gate results, and revision history for project integration or file-based runs.

## How it works

```text
Lesson title / teacher notes / slides / textbook pages / lesson plan
                              ↓
                        Lesson profile
                              ↓
              Core propositions and lesson boundary
                              ↓
                    Candidate judgment items
                              ↓
        Terminology → fluency → natural disambiguation
                              ↓
        Proof or counterexample → deduplication → deletion test
                              ↓
             Student version + teacher version + structured package
```

A package can be marked `READY` only when every hard gate passes and the run references the single current verified lexicon for that exact lesson. With only a title and no matching verified lexicon, the Skill still generates a complete candidate package, but the status must remain `PENDING_JUDGMENT`.

## Quick start

### 1. Install

Download or clone this repository. Copy the inner `lesson-first-judgment-question-sop` folder into your Codex skills directory:

```text
Windows: %USERPROFILE%\.codex\skills\lesson-first-judgment-question-sop
macOS/Linux: ~/.codex/skills/lesson-first-judgment-question-sop
```

Refresh or restart Codex so it can discover the Skill.

### 2. Ask for a lesson-aligned question set

The minimum input is a lesson title:

```text
Use $lesson-first-judgment-question-sop for the lesson “Commutative and associative laws of integer addition.”
Show the lesson profile first, then produce the Chinese student and teacher versions.
Do not fill a fixed item quota.
```

For stronger alignment, also provide what was actually taught, what was explicitly excluded, or the relevant classroom materials.

### 3. Check the status before use

- `READY` — every hard gate passed; the package can move to final teacher or curriculum review;
- `PENDING_JUDGMENT` — the full candidate package exists, but an inferred boundary, evidence source, or classroom judgment still needs confirmation;
- `INSUFFICIENT_INPUT` — the available evidence cannot support a reliable core proposition or a unique truth value.

## Representative knowledge-point examples

The Chinese wording is intentionally preserved because terminology and classroom fluency are part of what the Skill evaluates.

| Knowledge point | Chinese judgment item | Answer | Evidence |
| --- | --- | :---: | --- |
| Conditions for comparing two angles | 比较两个均小于180°的角时，只让两个角的顶点重合，就能判断它们的大小。 | × | Matching the vertices is not enough; one side must also coincide, with the other two sides placed on the same side of the shared ray. |
| Two kinds of certain events | 确定事件都是确定会发生的事件。 | × | A certain event may be guaranteed to occur or guaranteed not to occur. |
| Range of an obtuse angle | 大于90°的角都是钝角。 | × | A straight angle is 180°, which is greater than 90° but is not obtuse. |

The [Chinese README](README.md#案例示范知识点对应判断题) lists 27 lesson-tested mappings in the form `knowledge point → judgment item → answer → proof or counterexample`.

## Three working modes

- **Generate** — create and audit a new set from the current lesson content;
- **Audit** — classify each existing item as keep, minimally revise, or drop;
- **Minimal revision** — preserve the original intent while fixing scope, ambiguity, multiple targets, or invalid evidence.

## Repository layout

```text
.
├─ lesson-first-judgment-question-sop/   # Installable Skill
│  ├─ SKILL.md                            # Core workflow
│  ├─ agents/openai.yaml                  # Codex interface metadata
│  ├─ scripts/audit_terms.py              # Terminology audit script
│  └─ references/                         # Quality gates, output contracts, synthetic lexicon
├─ assets/workflow-guizang.png            # Workflow illustration
├─ examples/                              # Synthetic input and output
├─ tests/validate_release.py              # Public-release validation
├─ .github/workflows/validate.yml         # GitHub Actions
├─ README.md                              # Chinese product page
├─ README_EN.md                           # English product page
└─ LICENSE
```

The root-level READMEs, `examples/`, and `tests/` support public documentation and release validation. They are not required runtime context for the installed Skill.

## Synthetic example and real lesson lexicons

- [Synthetic input](examples/sample-input.md)
- [Synthetic output](examples/sample-output.md)

`SYNTHETIC-G7-I1.json` demonstrates the lexicon schema and tests the audit script. It is not a lexicon for any real textbook, school, or lesson, and it must not be used as terminology evidence for a real classroom run.

Real lesson lexicons are edition- and lesson-specific. Do not reuse one across textbooks, editions, or lessons without source verification.

## Local validation

Run the complete public-release check from the repository root:

```bash
python tests/validate_release.py
```

The check covers required files, Skill frontmatter, JSON parsing, Python compilation, UTF-8, public-content scanning, README language links, and allow/block smoke tests for terminology auditing. The included GitHub Actions workflow runs the same validation on pushes and pull requests.

## Capability boundaries

- The terminology script audits caller-supplied candidate terms; it cannot discover every professional term in arbitrary prose.
- Mathematical truth values, proofs, and counterexamples still require item-level review.
- A lesson scope inferred from a title is not evidence of what a particular class actually learned.
- The Skill does not present plausible student difficulties as diagnosed misconceptions.
- Final classroom use remains a teacher or curriculum-review decision.

## Data and copyright boundary

Use real classroom materials only when you have the right to do so. Store only the terminology, status, and source location needed for the task. Do not publish copyrighted textbook pages or passages, internal school materials, student information, or private lexicons directly derived from those materials.

## License

Original content in this repository is released under the [MIT License](LICENSE). Third-party materials are outside the scope of this license.
