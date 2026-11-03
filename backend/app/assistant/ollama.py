"""
The real model, served by Ollama on the PC (step 3d). A TRANSLATOR between our messages and Ollama's /api/chat.

    our side (loop.py)                     Ollama's side
    chat(messages, tools, max_tokens)  ->  POST /api/chat {model, messages, tools, stream: false, think: false,
                                                           options: {temperature, top_p, top_k, presence_penalty,
                                                                     num_ctx, num_predict}, keep_alive}
    ModelReply(text, tool_calls)       <-  {"message": {"content": ..., "tool_calls": [{"function": {...}}]}}

The model's name is a setting (CHAT_MODEL); the knobs are the team's, in mappings/agents.yaml (`model:`).
Anything that goes wrong (Ollama off, too slow, model not pulled, a broken answer) is ModelUnavailable, which the
route turns into 503 assistant_unavailable. A connection error or an HTTP 5xx is tried again twice first (after 1 s,
then 2 s, step 4); a timeout is NOT (the model is just slow, another try would only double the wait), and neither is
a 4xx (model not pulled) or a broken answer. TODO(step 3e): a second provider when Ollama is down.
"""

import json
import re
import time

import httpx

from .model import ModelReply, ModelUnavailable, ToolCall

THINK = re.compile(r"<think>.*?</think>", re.DOTALL)      # hidden reasoning some models still write out
STATUS_TIMEOUT_S = 3                                      # /api/show must answer fast, or the model counts as off
STATUS_CACHE_S = 60
RETRY_DELAYS_S = (1, 2)                                   # waits before the 2nd and the 3rd try of /api/chat


class OllamaClient:
    def __init__(self, url, model, settings, transport=None, retry_delays=RETRY_DELAYS_S, sleep=time.sleep):
        """url: where Ollama answers; model: e.g. "qwen3.5:4b"; settings: agents.ModelSettings.
        transport: a fake HTTP layer in the tests (None = the real network); retry_delays / sleep: the waits
        between tries, and how to wait (the tests do not really wait)."""
        self.url, self.name, self.settings = url.rstrip("/"), model, settings
        self.transport = transport
        self.retry_delays, self.sleep = retry_delays, sleep
        self._status = None                               # (time, answer) of the last /api/show

    def _post(self, path, body, timeout):
        with httpx.Client(base_url=self.url, timeout=timeout, transport=self.transport) as http:
            response = http.post(path, json=body)
            response.raise_for_status()
            return response.json()

    def chat(self, messages, tools, max_tokens, temperature=None):
        s = self.settings
        body = {"model": self.name, "messages": [to_ollama(m) for m in messages], "stream": False, "think": s.think,
                "options": {"temperature": s.temperature if temperature is None else temperature, "top_p": s.top_p, "top_k": s.top_k,
                            "presence_penalty": s.presence_penalty, "num_ctx": s.num_ctx, "num_predict": max_tokens},
                "keep_alive": s.keep_alive}
        if tools:                                         # no tools = the model must answer in words
            body["tools"] = tools
        for delay in (*self.retry_delays, None):          # None = the last try: no more waiting
            try:
                return from_ollama(self._post("/api/chat", body, s.timeout_s)["message"])
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:     # ValueError: broken JSON
                if delay is not None and worth_retrying(error):
                    self.sleep(delay)
                    continue
                raise ModelUnavailable(f"Ollama ({self.name}): {type(error).__name__}: {error}") from error

    def available(self):
        """True when Ollama answers and has the model (asked at most once a minute, 3 s at most)."""
        if self._status and time.time() - self._status[0] < STATUS_CACHE_S:
            return self._status[1]
        try:
            self._post("/api/show", {"model": self.name}, STATUS_TIMEOUT_S)
            ok = True
        except (httpx.HTTPError, ValueError):
            ok = False
        self._status = (time.time(), ok)
        return ok


def worth_retrying(error):
    """A dropped or refused connection, or an HTTP 5xx: Ollama may be restarting. Not a timeout (httpx's timeouts are
    not NetworkErrors), not a 4xx, not a broken answer."""
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code >= 500
    return isinstance(error, httpx.NetworkError)


def make_ollama(settings, model_settings):
    """The app's model client, from CHAT_MODEL / OLLAMA_URL and agents.yaml. Says once at start-up whether Ollama
    has the model; a missing model never stops the app (the assistant then answers 503 until it is there)."""
    client = OllamaClient(settings.ollama_url, settings.chat_model, model_settings)
    found = "yes" if client.available() else "NO (the assistant answers 503 until Ollama has it)"
    print(f"assistant: model {client.name} at {client.url}; Ollama answered /api/show: {found}", flush=True)
    return client


def to_ollama(message):
    """Our messages are already in Ollama's shape, except a tool result: Ollama names its tool `tool_name`."""
    if message.get("role") == "tool":
        return {"role": "tool", "tool_name": message["name"], "content": message["content"]}
    return message


def from_ollama(message):
    """Ollama's message -> ModelReply. A <think> block in the text is removed (and flagged for the trace)."""
    calls = []
    for call in message.get("tool_calls") or []:
        function = call["function"]
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):                    # some templates send the arguments as JSON text
            arguments = json.loads(arguments or "{}")
        calls.append(ToolCall(name=function["name"], arguments=arguments))
    text = message.get("content") or ""
    stripped = THINK.sub("", text)
    return ModelReply(text=stripped.strip() or None, tool_calls=calls, thinking_stripped=stripped != text)
