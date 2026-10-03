"""
The chat assistant's language model. The router only needs:

    engine.reply(system, history, message, tools) -> (answer text, [tool names used])

`tools` is a dict {name: python function}. Gemini reads each function's name,
type hints and docstring, decides when to call it, and our code runs it
(automatic function calling). Tests use a fake engine with the same method.

Gemini sometimes answers "high demand, try later" (503) for a few seconds; those
calls are retried a few times before giving up. A 429 means the key's quota is
used up (the free tier allows only ~20 requests a day per model, and one answer
that uses tools costs several), so it is never retried: that would only waste more.
"""
import time

RETRY_CODES = {500, 503}           # temporary errors worth trying again
RETRY_WAITS = [1, 3]               # seconds to wait before the 2nd and 3rd try


class ChatUnavailable(Exception):
    """No API key: the assistant is switched off (HTTP 503)."""


class ChatBusy(Exception):
    """Gemini failed or is overloaded, even after the retries (HTTP 502)."""


class ChatQuota(ChatBusy):
    """The Gemini key has used up its quota (HTTP 429)."""


class GeminiEngine:
    def __init__(self, settings):
        self.settings = settings
        self._client = None

    def _get_client(self):
        if not self.settings.gemini_api_key:
            raise ChatUnavailable("The chat assistant needs GEMINI_API_KEY in backend/.env")
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    def reply(self, system, history, message, tools):
        from google.genai import types

        client = self._get_client()
        used = []                      # tool names, for the "used: wardrobe" line

        def recorded(name, fn):
            def wrapper(*args, **kwargs):
                used.append(name)
                return fn(*args, **kwargs)
            wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
            wrapper.__annotations__ = fn.__annotations__
            wrapper.__wrapped__ = fn           # keeps the signature visible to Gemini
            return wrapper

        contents = [types.Content(role=h["role"], parts=[types.Part(text=h["text"])])
                    for h in history]
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[recorded(n, f) for n, f in tools.items()],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=6),
        )
        for attempt in range(len(RETRY_WAITS) + 1):
            used.clear()                       # a retry runs the tools again
            try:
                response = client.models.generate_content(
                    model=self.settings.gemini_model, contents=contents, config=config)
                return (response.text or "").strip(), used
            except Exception as e:             # network, overload, quota, wrong model name...
                code = getattr(e, "code", None)
                if code == 429:
                    raise ChatQuota(f"Gemini quota used up: {e}") from e
                if code not in RETRY_CODES or attempt == len(RETRY_WAITS):
                    raise ChatBusy(f"Gemini error: {e}") from e
                time.sleep(RETRY_WAITS[attempt])
