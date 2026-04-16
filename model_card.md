# BugHound Mini Model Card (Reflection)

---

## 1) What is this system?

**Name:** BugHound
**Purpose:** Analyze a Python snippet for common bugs, propose a minimal fix, assess the risk of that fix, and decide whether to auto-apply it or defer to a human reviewer.

**Intended users:** Students learning agentic AI workflows and AI reliability concepts — specifically, how to build systems that fail gracefully, guard against bad model output, and know when to stop and ask for help.

---

## 2) How does it work?

BugHound runs a five-step agentic loop each time it receives a code snippet:

1. **PLAN** — logs intent and sets up the workflow. No real decision-making here; it always proceeds to analyze.
2. **ANALYZE** — scans the code for issues. If a live LLM client is available, it sends the snippet to Gemini with a strict prompt asking for a JSON array of issues. If the model's response is empty, unparseable, or an empty array, the agent falls back to heuristic rules (checking for `print(`, bare `except:`, and `TODO` comments). If no client is configured at all, heuristics run directly.
3. **ACT** — proposes a fix. With an LLM, it asks Gemini to return the full rewritten code. With heuristics, it applies targeted regex substitutions: replacing bare `except:` with `except Exception as e:` and swapping `print(` calls for `logging.info(`. If there are no issues, the original code is returned unchanged.
4. **TEST** — calls `assess_risk()` to score the proposed fix on a 0–100 scale and classify it as low, medium, or high risk.
5. **REFLECT** — reads the risk report's `should_autofix` flag and logs either "safe to auto-apply" or "human review recommended."

**Heuristics vs. Gemini:**
Heuristics are deterministic, fast, and always available. They catch a narrow, predefined set of patterns reliably. Gemini can reason about logic, naming, edge cases, and security issues that no regex will catch — but its output must be strictly validated because it can hallucinate, return wrong structure, or add unrequested changes.

---

## 3) Inputs and outputs

**Inputs tested:**

| Label | Description |
|---|---|
| `cleanish.py` | Two-function module using `logging` correctly; no obvious issues |
| `mixed_issues.py` | Short function with a bare `except:`, a `print(`, and a `TODO` comment — all three heuristic triggers active |
| TODO-only comments | Two lines of Python comments starting with `# TODO:` and nothing else — no executable code |

**Observed outputs:**

- `cleanish.py`: zero issues detected, fix = original code unchanged, risk score = 100, `should_autofix = True` (no-op auto-apply, harmless).
- `mixed_issues.py`: three issues (High/Reliability, Medium/Maintainability, Low/Code Quality), fix added `import logging`, replaced `print(` with `logging.info(`, rewrote `except:` → `except Exception as e:`. Risk score = 15, level = high, `should_autofix = False`.
- TODO-only: one issue (Medium/Maintainability), heuristic fixer returned **the original code unchanged** (no handler for `Maintainability` type). Risk score = 80, level = low — would have said `should_autofix = True` without the identical-fix guardrail added during this session.

---

## 4) Reliability and safety rules

**Rule 1 — Return statement removal penalty (`−30 points`)**

Checks whether `return` appears in the original but is absent from the fixed code. A fix that drops return statements almost certainly breaks the function's contract with its callers, producing silent `None` returns where a value was expected. This is a high-consequence, easy-to-miss change.

- *Why it matters:* An LLM rewriting code can accidentally omit returns when restructuring a function body. The heuristic fixer could also silently swallow a return if a regex substitution is too aggressive.
- *False positive:* A function that genuinely should not return a value (e.g., a setter or side-effect function) might be incorrectly penalized if the original happened to include a `return None` explicitly and the fix removes it cleanly.
- *False negative:* The check is a simple `in` string search, so it only catches total removal. A fix that changes `return result` to `return None` or `return []` would score as safe even though it silently changes behavior.

**Rule 2 — New import signal (`−15 points`)**

Checks whether the fixed code introduces any `import` or `from ... import` statements that were not present in the original. New imports mean the fix is pulling in dependencies the original code did not have.

- *Why it matters:* The heuristic fixer always adds `import logging` when replacing print statements. While that specific change is benign, the principle generalizes: an LLM could add `import subprocess`, `import os`, or a third-party library, subtly expanding the code's attack surface or breaking environments where that library is not installed.
- *False positive:* The rule fires even for genuinely safe additions like `import logging` or `import typing`. A low-risk fix that only adds a standard-library import still gets penalized, which might unfairly push it from "low" to "medium" risk.
- *False negative:* The rule only inspects top-level `import` lines. An LLM could add `__import__('os')` inline or use `importlib`, both of which this regex would miss entirely.

---

## 5) Observed failure modes

**Failure 1 — Unsafe confidence on a no-op fix (TODO-only input)**

Input: two lines of `# TODO:` comments, no executable code.
What happened: the heuristic analyzer correctly detected a `Maintainability` issue. The heuristic fixer ran but has no handler for `Maintainability` — it only handles `Reliability` and `Code Quality`. It returned the original code unchanged. The risk assessor scored this as 80/low and set `should_autofix = True`.

The system was about to "auto-apply" a fix that would change zero bytes of the file, while confidently telling the user it was safe. This is unsafe confidence: the risk number reflects the issues found, not whether the fix actually addresses them. A human reading `should_autofix: True` would reasonably assume the agent had done something meaningful.

**Guardrail added:** `risk_assessor.py` now checks `fixed_code.strip() == original_code.strip()` and overrides `should_autofix = False` with a reason string reading "Fix is identical to original code; nothing would be changed by auto-applying."

**Failure 2 — LLM silently returns an empty issues list**

Input: any clean code sent to the LLM (tested via MockClient).
What happened (before the session's `analyze` fix): if Gemini returned `[]` — a valid JSON array but with no items — the agent accepted it as "no issues found" and never ran heuristics. A bare `except:` block in the snippet would have been silently ignored.

The original guard only caught `None` (unparseable JSON). An empty list parses fine and was treated as a clean bill of health, regardless of whether the LLM actually analyzed the code or simply produced a minimal valid response.

**Guardrail added:** `analyze()` now uses `if not issues:` instead of `if issues is None:`, so both a parse failure and an empty-list response trigger the heuristic fallback.

---

## 6) Heuristic vs. Gemini comparison

All runs in this session used offline/heuristic mode, either directly (`client=None`) or via `MockClient`, which intentionally returns non-JSON for analyzer prompts to force fallback. The following comparison is therefore based on observed heuristic behavior plus the behavior Gemini mode is designed to produce based on the prompts and parsing code.

| Dimension | Heuristic mode | Gemini mode |
|---|---|---|
| Issue detection | Catches exactly three patterns: `print(`, bare `except:`, `TODO` — nothing else | Can reason about logic errors, off-by-one bugs, type mismatches, security issues, missing validation |
| Fix quality | Deterministic regex substitutions — always the same output for the same input | Free-form rewrite, potentially more accurate but also capable of introducing unrequested changes |
| Output reliability | 100% structurally valid — always returns a Python string | Requires strict parsing: JSON arrays can be wrapped in markdown fences, prefaced with explanation, or returned as empty lists |
| False negatives | High — misses anything outside the three patterns | Low on known patterns, but unpredictable on novel code |
| Consistency | Identical output every run | Varies across runs even with temperature=0.2 |

The most notable discrepancy: heuristics gave `mixed_issues.py` a fix score of 15 (high risk, no autofix) while a Gemini-produced fix addressing the same three issues — but without adding new imports or altering structure — could score 55–75 (medium or low risk). Gemini potentially produces a more surgical fix that the risk assessor rewards more. However, Gemini is also the path where output format failures and over-editing are possible, so the scoring tradeoff is intentional.

---

## 7) Human-in-the-loop decision

**Scenario:** A file contains a `try/except` block that catches a specific exception — not a bare `except:` — but the LLM decides to restructure the entire error handling path, removing the specific exception type, adding a new `logging` import, and splitting the function. The risk assessor scores this as medium (score ≈ 55): no return statements removed, no dramatic length change. The system does not auto-fix, but the reasons listed don't communicate *why* the restructure is risky.

**What should happen instead:** When the number of changed lines exceeds a threshold (e.g., more than 40% of the original file), the agent should decline to auto-fix and surface a specific message explaining the scope of the change.

**Where to implement it:** `risk_assessor.py`. The line-count ratio check already exists (`len(fixed_lines) < len(original_lines) * 0.5` deducts 20 points), but it only fires when code shrinks dramatically. Adding a symmetric check for large additions — or a raw diff-line count — would catch over-editing in either direction without needing to parse the semantics of the change.

**Message to show the user:**
> "The proposed fix modifies more than 40% of the original code. BugHound cannot verify that behavior is preserved at this scale. Human review required before applying."

---

## 8) Improvement idea

**Guardrail: count changed lines and penalize large-scope fixes**

Currently the risk assessor only checks if the fixed code is *shorter* than the original (< 50% of original line count). It does not penalize fixes that are dramatically *longer* or that touch most of the original lines.

A simple improvement: compute the number of lines that differ between original and fixed using a line-set diff (or even just `len(set(fixed_lines) - set(original_lines))`), and deduct points proportionally if more than 30–40% of lines are new.

```python
changed_lines = len(set(fixed_lines) - set(original_lines))
if len(original_lines) > 0 and changed_lines / len(original_lines) > 0.4:
    score -= 20
    reasons.append(
        f"Fix rewrites ~{int(changed_lines/len(original_lines)*100)}% of original lines; scope may exceed the reported issues."
    )
```

This is low-complexity (pure Python, no new dependencies), testable with a single unit test, and directly addresses the most dangerous failure mode in LLM-assisted auto-editing: a model that "fixes" one issue by rewriting everything around it.
