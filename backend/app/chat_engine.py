"""
The chat assistant's language model. Two engines, chosen by CHAT_ENGINE in backend/.env:

    gemini  Google Gemini (default; needs GEMINI_API_KEY, free key = 20 requests a day)
    ollama  a model running on our own machine with Ollama (no key, no quota), e.g.
            qwen3:4b-instruct or our fine-tuned dressme-chat (see LLM.md)

The router only needs:

    engine.reply(system, history, message, tools) -> (answer text, [tool names used])

`tools` is a dict {name: python function}. Gemini reads each function's name,
type hints and docstring, decides when to call it, and our code runs it
(automatic function calling). Tests use a fake engine with the same method.

Gemini sometimes answers "high demand, try later" (503) for a few seconds; those
calls are retried a few times before giving up. A 429 means the key's quota is
used up (the free tier allows only ~20 requests a day per model, and one answer
that uses tools costs several), so it is never retried: that would only waste more.
"""
import inspect
import json
import re
import time
import typing

RETRY_CODES = {500, 503}           # temporary errors worth trying again
RETRY_WAITS = [1, 3]               # seconds to wait before the 2nd and 3rd try


class ChatUnavailable(Exception):
    """No API key: the assistant is switched off (HTTP 503)."""


class ChatBusy(Exception):
    """Gemini failed or is overloaded, even after the retries (HTTP 502)."""


class ChatQuota(ChatBusy):
    """The Gemini key has used up its quota (HTTP 429)."""


def make_engine(settings):
    """The engine named by CHAT_ENGINE (gemini or ollama)."""
    if settings.chat_engine == "ollama":
        return OllamaEngine(settings)
    return GeminiEngine(settings)


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


# ------------------------------------------------------------------ local model (Ollama)
JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def _json_type(hint):
    """A Python type hint (str, int, list[str]...) as a JSON schema."""
    if typing.get_origin(hint) is list:
        (inner,) = typing.get_args(hint) or (str,)
        return {"type": "array", "items": _json_type(inner)}
    return {"type": JSON_TYPES.get(hint, "string")}


def tool_schema(fn):
    """The function's name, docstring and type hints as an OpenAI-style tool, the
    format Ollama (and the fine-tuning data, src/phase4/build_chat_dataset.py) use.
    Gemini reads the same three things from the function itself."""
    params, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        params[name] = _json_type(p.annotation)
        if p.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "function", "function": {
        "name": fn.__name__,
        "description": " ".join((fn.__doc__ or "").split()),
        "parameters": {"type": "object", "properties": params, "required": required}}}


def run_tool(tools, name, arguments):
    """Run one tool call and return its answer as JSON text (errors included,
    so the model can read them and recover instead of crashing the chat)."""
    if name not in tools:
        return json.dumps({"error": f"unknown tool {name}"})
    if isinstance(arguments, str):          # some models send the arguments as JSON text
        try:
            arguments = json.loads(arguments or "{}")
        except ValueError:
            arguments = {}
    try:
        result = tools[name](**(arguments or {}))
    except Exception as e:                  # wrong argument names or values
        result = {"error": f"{type(e).__name__}: {e}"}
    return json.dumps(result, ensure_ascii=False)


_TOOL_BLOCK = re.compile(r"<tool_call\b[^>]*>.*?</tool_call\s*>", re.IGNORECASE | re.DOTALL)
_TOOL_TAG = re.compile(r"</?tool_call\b[^>]*>", re.IGNORECASE)


def clean_model_text(text):
    """Remove tool protocol artifacts that some local models echo to users."""
    text = _TOOL_BLOCK.sub("", text or "")
    text = _TOOL_TAG.sub("", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                value = json.loads(stripped)
            except ValueError:
                value = None
            if isinstance(value, dict) and (
                "tool_calls" in value or {"name", "arguments"} <= set(value)
            ):
                continue
        lines.append(line)
    return "\n".join(lines).strip()


class OllamaEngine:
    """A local model served by Ollama (http://localhost:11434). Ollama does not run
    the tools itself: it answers with `tool_calls`, we run them, send the results
    back as "tool" messages and ask again, at most MAX_ROUNDS times."""

    MAX_ROUNDS = 6                  # like Gemini's maximum_remote_calls

    def __init__(self, settings):
        self.settings = settings

    def _post(self, payload):
        import httpx
        try:
            r = httpx.post(self.settings.ollama_url.rstrip("/") + "/api/chat", json=payload,
                           timeout=self.settings.ollama_timeout)
        except httpx.ConnectError as e:
            raise ChatUnavailable(f"Ollama is not running at {self.settings.ollama_url} "
                                  "(start it, or set CHAT_ENGINE=gemini)") from e
        except httpx.HTTPError as e:        # timeout...
            raise ChatBusy(f"Ollama error: {e}") from e
        if r.status_code == 404:
            raise ChatUnavailable(f"Ollama has no model {self.settings.ollama_model!r}: "
                                  f"run `ollama pull {self.settings.ollama_model}`")
        if r.status_code != 200:
            raise ChatBusy(f"Ollama error {r.status_code}: {r.text[:200]}")
        try:
            body = r.json()
            message = body["message"]
        except (ValueError, KeyError, TypeError) as e:
            raise ChatBusy(f"Ollama returned an invalid response: {e}") from e
        if not isinstance(message, dict):
            raise ChatBusy("Ollama returned an invalid message")
        return message

    def reply(self, system, history, message, tools):
        messages = [{"role": "system", "content": system}]
        messages += [{"role": "assistant" if h["role"] == "model" else "user", "content": h["text"]}
                     for h in history]
        messages.append({"role": "user", "content": message})
        schemas = [tool_schema(f) for f in tools.values()]
        used = []
        last_content = ""
        for _ in range(self.MAX_ROUNDS + 1):
            answer = self._post({"model": self.settings.ollama_model, "messages": messages,
                                 "tools": schemas, "stream": False,
                                 "options": {"temperature": self.settings.ollama_temperature,
                                             # Ollama's default window is too short for
                                             # 20 messages of history + tool answers
                                             "num_ctx": self.settings.ollama_num_ctx,
                                             # a small model sometimes repeats itself until
                                             # the timeout: cut the answer instead
                                             "num_predict": self.settings.ollama_max_tokens}})
            calls = answer.get("tool_calls") or []
            if not isinstance(calls, list):
                raise ChatBusy("Ollama returned invalid tool calls")
            last_content = clean_model_text(answer.get("content"))
            if not calls or len(used) >= self.MAX_ROUNDS:
                return last_content or "I couldn't finish that answer. Please try again.", used
            messages.append({"role": "assistant", "content": answer.get("content", ""),
                             "tool_calls": calls})
            for call in calls:
                try:
                    function = call["function"]
                    name = function["name"]
                except (KeyError, TypeError) as e:
                    raise ChatBusy(f"Ollama returned an invalid tool call: {e}") from e
                if not isinstance(name, str) or not name:
                    raise ChatBusy("Ollama returned a tool call without a name")
                used.append(name)
                messages.append({"role": "tool", "tool_name": name,
                                 "content": run_tool(tools, name, function.get("arguments"))})
                if name in used[:-1]:
                    messages.append({
                        "role": "user",
                        "content": "Use the tool result above and answer the original user directly. "
                                   "Do not call any more tools.",
                    })
                    final = self._post({"model": self.settings.ollama_model, "messages": messages,
                                        "tools": [], "stream": False,
                                        "options": {"temperature": self.settings.ollama_temperature,
                                                    "num_ctx": self.settings.ollama_num_ctx,
                                                    "num_predict": self.settings.ollama_max_tokens}})
                    content = clean_model_text(final.get("content"))
                    return content or "I found outfit ideas from your wardrobe. See the pieces below.", used
        return last_content or "I couldn't finish that answer. Please try again.", used
