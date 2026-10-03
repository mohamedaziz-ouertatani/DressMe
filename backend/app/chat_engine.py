"""
The chat assistant's language model. The router only needs:

    engine.reply(system, history, message, tools) -> (answer text, [tool names used])

`tools` is a dict {name: python function}. Gemini reads each function's name,
type hints and docstring, decides when to call it, and our code runs it
(automatic function calling). Tests use a fake engine with the same method.
"""


class ChatUnavailable(Exception):
    """No API key, or the Gemini service failed."""


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
        used = []

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
        try:
            response = client.models.generate_content(
                model=self.settings.gemini_model, contents=contents, config=config)
        except Exception as e:                # network, quota, wrong model name...
            raise ChatUnavailable(f"Gemini error: {e}") from e
        return (response.text or "").strip(), used
