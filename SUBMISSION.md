# Mindseam Cognition Suite — Awesome Skills Submission

## Ready-to-paste entry for yzfly/awesome-skills-zh

```markdown
- [Mindseam Cognition Suite](https://github.com/yzfly/Mindseam-Cognition-Suite-V3.6)
  — A model-agnostic inference-time control system for deep reasoning, long-horizon work,
  verification, and recovery. Packaged as a cross-platform Skill (SKILL.md + selective modules).
  Runs with Python standard library only; no network, no external dependencies.
  Category: `reasoning-control`, `state-management`, `skill-framework`
```

## Category keywords (pick one primary + optional secondary)

| Keyword | Rationale |
|---|---|
| `reasoning-control` | Mindseam's core thesis: managed workspace for inference-time reasoning |
| `state-management` | Optional ledger/skillbook/ship controller for multi-turn task state |
| `skill-framework` | Delivered as an installable Skill with SKILL.md routing |
| `agent-architecture` | Inner/ledger/outer register model, metacognition detectors |
| `verification` | Completion gates, risk assessment, claim coverage auditing |

## One-line pitch (140 chars)

```
Model-agnostic workspace controller for deep reasoning. Skill package, stdlib only, zero deps.
```

## Key differentiators for listing

1. **Inference-time only** — weights and training unchanged; works with any model
2. **Standard library only** — `python -m pytest` runs 1034 tests, no pip install needed
3. **Skill-native** — SKILL.md first-class entry; 11 modules + 3 references loaded selectively
4. **Skillbook pattern** — auto-extracts recurring failure patterns from history to `.mindseam/skillbook.md`
5. **Ship gate** — `mindseam.py ship OUTPUT_FILE` checks outgoing text for inner-register leakage
6. **Bilingual** — full README in English and Chinese (README.zh-CN.md)
7. **Apache 2.0** — permissive license; CONTRIBUTING.md establishes contribution norms

## Repository health snapshot

| Metric | Value |
|---|---|
| Python stdlib tests | 1034 passed, 0 failed |
| Integrity verifier | 9/9 PASS |
| README coverage | EN + ZH |
| License | Apache 2.0 |
| DOI | https://zenodo.org/badge/latestdoi/1308234922 |

## Submitter notes

- Maintainer: yzfly
- Repository: https://github.com/yzfly/Mindseam-Cognition-Suite-V3.6
- Primary audience: AI engineers, Skill authors, reasoning layer researchers
- Not a "wrapper around a model API"; it is a model-side operating design packaged as a Skill
