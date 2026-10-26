"""
The language model, seen from the assistant (step 3c).

The loop only knows this small interface, so the model behind it can change: a scripted FakeModel in the tests
(this step), a real model served by Ollama (step 3d), our own fine-tune (step 3h).

    chat(messages, tools, max_tokens) -> ModelReply
        messages   the conversation so far, as a list of {"role": ..., "content": ...} dicts
        tools      the tools the model may ask for (the registry's schemas); [] = it must just answer
        ModelReply either some text (the answer) or tool calls (the model asks us to run tools)
"""

import copy
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class ModelReply:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class ModelUnavailable(Exception):
    """The model cannot be reached or is not set up. The route answers 503 assistant_unavailable."""


class ModelClient(Protocol):
    name: str          # saved with every chat turn, so we know which model said what

    def chat(self, messages: list[dict], tools: list[dict], max_tokens: int) -> ModelReply: ...


class FakeModel:
    """Returns the scripted replies in order and remembers everything it was asked (`received`)."""
    name = "fake"

    def __init__(self, script):
        self.script = list(script)
        self.received = []         # one {"messages", "tools", "max_tokens"} per call

    def chat(self, messages, tools, max_tokens):
        self.received.append({"messages": copy.deepcopy(messages), "tools": tools, "max_tokens": max_tokens})
        if not self.script:
            raise AssertionError("FakeModel: the script has no reply left for this call")
        return self.script.pop(0)


class NoModel:
    """The default until a real model is plugged in (step 3d): every call says it is unavailable."""
    name = "none"

    def chat(self, messages, tools, max_tokens):
        raise ModelUnavailable("no language model is set up")
