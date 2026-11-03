"""
The agents, read from mappings/agents.yaml and checked at start-up (step 3c).

An agent is a job, its instructions, the tools it may use, keywords that will route a message to it (step 3e) and
its own limits. The team edits the file; this module refuses to start the API with a clear message when something
is wrong, so a typo is found at start-up and not in the middle of a user's chat:

    - a field is missing or has the wrong type (the message names the agent and the field)
    - an agent lists a tool that is not registered
    - an agent has more tools than limits.max_tools (small models choose badly among many tools)
    - an agent's max_rounds or max_tokens is above the global limit
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class AgentsConfigError(Exception):
    """agents.yaml cannot be used. The text says where."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")      # an unknown field is a typo: refuse it


class Limits(Strict):
    max_tools: int = Field(gt=0)
    max_rounds: int = Field(gt=0)
    max_tokens: int = Field(gt=0)


class ModelSettings(Strict):
    """How the model is asked (step 3d): the sampling knobs, the context window, how long it stays loaded."""
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    top_k: int = Field(ge=1)
    presence_penalty: float = Field(ge=-2, le=2)
    num_ctx: int = Field(ge=512, le=262144)           # the context window, in tokens (more = more GPU memory)
    keep_alive: str = Field(pattern=r"^(-1|0|\d+[smh])$")   # e.g. "10m"; -1 = keep it loaded, 0 = unload at once
    timeout_s: float = Field(gt=0, le=600)
    think: bool


class RouterSettings(Strict):
    """The routing call (step 3e): one word back, so a few tokens, and no randomness."""
    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(gt=0, le=50)


class Agent(Strict):
    job: str
    description: str                               # one line the router reads to choose (what it handles / not)
    examples: list[str] = []                       # messages this agent should get: shown to the router after the description
    instructions: str
    tools: list[str]                             # may be empty: an agent that only talks (general)
    keywords: dict[str, list[str]] = {}            # language -> words (en / fr / ar): the router's fallback
    max_rounds: int = Field(gt=0)
    max_tokens: int = Field(gt=0)


class AgentsFile(Strict):
    limits: Limits
    model: ModelSettings
    router: RouterSettings
    shared_rules: str
    agents: dict[str, Agent]


def where(loc):
    """('agents', 'stylist', 'job') -> "agent 'stylist', field 'job'"."""
    if len(loc) >= 3 and loc[0] == "agents":
        return f"agent '{loc[1]}', field '{'.'.join(map(str, loc[2:]))}'"
    return "field '" + ".".join(map(str, loc)) + "'"


def load_agents(path, tool_names):
    """The validated agents file. `tool_names` = the names in the tool registry."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        config = AgentsFile.model_validate(raw)
    except OSError as error:
        raise AgentsConfigError(f"{path.name}: cannot be read ({error})") from error
    except yaml.YAMLError as error:
        raise AgentsConfigError(f"{path.name}: is not valid YAML ({error})") from error
    except ValidationError as error:
        lines = [f"{where(e['loc'])}: {e['msg']}" for e in error.errors()]
        raise AgentsConfigError(f"{path.name}: " + "; ".join(lines)) from error

    problems = []
    for name, agent in config.agents.items():
        for tool in agent.tools:
            if tool not in tool_names:
                problems.append(f"agent '{name}', field 'tools': tool '{tool}' is not registered "
                                f"(known tools: {', '.join(sorted(tool_names))})")
        if len(agent.tools) > config.limits.max_tools:
            problems.append(f"agent '{name}', field 'tools': {len(agent.tools)} tools, "
                            f"but limits.max_tools is {config.limits.max_tools}")
        for field in ("max_rounds", "max_tokens"):
            if getattr(agent, field) > getattr(config.limits, field):
                problems.append(f"agent '{name}', field '{field}': {getattr(agent, field)} is above "
                                f"limits.{field} ({getattr(config.limits, field)})")
    if not config.agents:
        problems.append("field 'agents': there is no agent")
    if problems:
        raise AgentsConfigError(f"{path.name}: " + "; ".join(problems))
    return config
