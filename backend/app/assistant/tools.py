"""
Tools and the registry (step 3c): the only way the assistant touches the user's data.

A Tool is a name, a description the model reads (English, with one example and one "do not use for"), the shape of
its arguments (a pydantic model that forbids extra fields) and a function. The Registry holds the tools, shows the
model their schemas and runs a call safely: whatever goes wrong (unknown tool, bad arguments, an unknown piece
number, a crash) comes back as an error result for the model to read. run() never raises.

Two safety rules live here:
- The user id is NEVER an argument. It comes from the ToolContext, which the route builds from the login.
- A tool argument that names pieces uses their small numbers (refs). The names listed in `piece_args` are
  translated to item ids through the ledger before the function runs; an unknown number is an error.
"""

import time
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .ledger import PieceLedger


@dataclass
class ToolContext:
    user_id: Any                    # the logged-in user's _id (from the login, never from the model)
    db: Any
    ledger: PieceLedger


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable                    # fn(ctx, args) -> dict
    piece_args: tuple = ()          # argument names that hold piece refs (an int, or a list of ints)


@dataclass
class ToolResult:
    ok: bool
    data: dict | None = None
    error_code: str | None = None
    message: str = ""
    ms: int = 0

    def for_model(self):
        """What the model reads: the data, or the error code and message."""
        return self.data if self.ok else {"error": self.error_code, "message": self.message}


def failed(code, message, started):
    return ToolResult(False, error_code=code, message=message, ms=round((time.perf_counter() - started) * 1000))


class Registry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        self._tools[tool.name] = tool

    def names(self):
        return list(self._tools)

    def schemas(self, names):
        """The tools in the format the model servers expect (type "function" + a JSON schema of the arguments)."""
        return [{"type": "function",
                 "function": {"name": t.name, "description": t.description,
                              "parameters": t.args_model.model_json_schema()}}
                for t in (self._tools[n] for n in names)]

    def run(self, call, ctx):
        started = time.perf_counter()
        tool = self._tools.get(call.name)
        if tool is None:
            return failed("unknown_tool", f"There is no tool called {call.name!r}.", started)
        try:
            args = tool.args_model(**call.arguments)
        except (ValidationError, TypeError) as error:
            return failed("invalid_arguments", str(error), started)
        args, unknown = self._translate_refs(tool, args, ctx.ledger)
        if unknown is not None:
            return failed("unknown_piece", f"Piece {unknown} was not shown in this conversation turn.", started)
        try:
            data = tool.fn(ctx, args)
        except Exception as error:                        # a tool must never break the turn
            return failed("tool_failed", f"{type(error).__name__}: {error}", started)
        return ToolResult(True, data=data, ms=round((time.perf_counter() - started) * 1000))

    @staticmethod
    def _translate_refs(tool, args, ledger):
        """Swap each piece ref in the arguments for its item id. Returns (args, the first unknown ref or None)."""
        changes = {}
        for name in tool.piece_args:
            value = getattr(args, name)
            refs = value if isinstance(value, list) else [value]
            ids = [ledger.item_id(r) for r in refs]
            if None in ids:
                return args, refs[ids.index(None)]
            changes[name] = ids if isinstance(value, list) else ids[0]
        # model_copy does not validate: after this the piece fields hold item ids (strings), as documented
        return (args.model_copy(update=changes) if changes else args), None
