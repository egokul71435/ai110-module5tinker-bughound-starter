import os
from typing import Optional


class MockClient:
    """
    Offline stand-in for an LLM client.
    This lets the app run without an API key.
    """

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        # Very small, predictable behavior for demos.
        if "Return ONLY valid JSON" in system_prompt:
            # Purposely not JSON to force fallback unless students change behavior.
            return "I found some issues, but I'm not returning JSON right now."
        return "# MockClient: no rewrite available in offline mode.\n"


class GeminiClient:
    """
    Minimal Gemini API wrapper with added error resilience.

    Requirements:
    - google-generativeai installed
    - GEMINI_API_KEY set in environment (or loaded via python-dotenv)
    """

    def __init__(self, model_name: str = "gemini-2.5-flash", temperature: float = 0.2):
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY. Create a .env file and set GEMINI_API_KEY=..."
            )

        # Import here so heuristic mode doesn't require the dependency at import time.
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._genai = genai
        self.model_name = model_name
        self.temperature = float(temperature)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Sends a single request to Gemini.

        The `google-generativeai` SDK only accepts USER/MODEL roles in the
        content list, so the system prompt must be passed via the model's
        `system_instruction` param rather than as a "system" role message.

        API errors (rate limits, invalid model name, network failures) are
        allowed to propagate to the caller. BugHoundAgent already wraps calls
        to `complete()` in its own try/except and logs a distinct "API Error"
        trace entry before falling back to heuristics, so swallowing errors
        here would just hide the real cause behind a generic empty response.
        """
        model = self._genai.GenerativeModel(
            self.model_name, system_instruction=system_prompt
        )
        response = model.generate_content(
            user_prompt,
            generation_config={"temperature": self.temperature},
        )

        # Defensive: response.text is None (rather than raising) when the
        # model returns no candidates, e.g. an empty-but-valid response.
        return response.text or ""
