# 🐶 BugHound

BugHound is a small, agent-style debugging tool. It analyzes a Python code snippet, proposes a fix, and runs basic reliability checks before deciding whether the fix is safe to apply automatically.

---

## What BugHound Does

Given a short Python snippet, BugHound:

1. **Analyzes** the code for potential issues  
   - Uses heuristics in offline mode  
   - Uses Gemini when API access is enabled  

2. **Proposes a fix**  
   - Either heuristic-based or LLM-generated  
   - Attempts minimal, behavior-preserving changes  

3. **Assesses risk**  
   - Scores the fix  
   - Flags high-risk changes  
   - Decides whether the fix should be auto-applied or reviewed by a human  

4. **Shows its work**  
   - Displays detected issues  
   - Shows a diff between original and fixed code  
   - Logs each agent step

---

## Setup

### 1. Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# or
.venv\Scripts\activate      # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running in Offline (Heuristic) Mode

No API key required.

```bash
streamlit run bughound_app.py
```

In the sidebar, select:

* **Model mode:** Heuristic only (no API)

This mode uses simple pattern-based rules and is useful for testing the workflow without network access.

---

## Running with Gemini

### 1. Set up your API key

Copy the example file:

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```text
GEMINI_API_KEY=your_real_key_here
```

### 2. Run the app

```bash
streamlit run bughound_app.py
```

In the sidebar, select:

* **Model mode:** Gemini (requires API key)
* Choose a Gemini model and temperature

BugHound will now use Gemini for analysis and fix generation, while still applying local reliability checks.

---

## Known Issues / Fixes

* **Fixed:** `GeminiClient.complete()` previously sent the system prompt as a `{"role": "system", ...}` message. The `google-generativeai` SDK only accepts `USER`/`MODEL` roles, so every real Gemini call failed with `400 Role 'system' is not supported`, was silently swallowed by the `except Exception` guard, and always fell back to heuristics — even with a valid API key. The system prompt is now passed via `GenerativeModel(..., system_instruction=system_prompt)` instead.
* **Fixed:** `GeminiClient.complete()` also used to catch *every* exception internally and return `""`, so a genuine API failure (bad key, rate limit, invalid model name, network error) looked identical to a normal empty/unparseable model response. `BugHoundAgent` already has its own try/except around `client.complete()` that logs a distinct `"API Error: ..."` trace entry and drives the app's "API Request Failed" warning banner — but it never fired, because the error never reached it. `GeminiClient.complete()` now lets exceptions propagate so real failures are reported with their actual error message instead of a generic empty-output note.
* `google-generativeai` is end-of-life upstream (Google recommends migrating to `google-genai`). Not yet migrated here; a `FutureWarning` on import is expected.

---

## Running Tests

Tests focus on **reliability logic** and **agent behavior**, not the UI.

```bash
pytest
```

You should see tests covering:

* Risk scoring and guardrails
* Heuristic fallbacks when LLM output is invalid
* End-to-end agent workflow shape
