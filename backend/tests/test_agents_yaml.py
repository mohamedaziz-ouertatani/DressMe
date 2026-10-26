"""agents.yaml (step 3c): the real file loads, and a bad file stops the start-up with a message that says where."""

import pytest
import yaml

from app.assistant import default_registry
from app.assistant.agents import AgentsConfigError, load_agents
from app.config import ROOT

REAL_FILE = ROOT / "mappings" / "agents.yaml"
TOOLS = default_registry().names()


def broken(tmp_path, change):
    """The real file with one change applied to the loaded data, written to a temporary file."""
    data = yaml.safe_load(REAL_FILE.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_the_real_file_loads():
    config = load_agents(REAL_FILE, TOOLS)
    stylist = config.agents["stylist"]
    assert stylist.tools == ["list_wardrobe", "search_wardrobe", "get_weather", "suggest_outfits", "build_outfit",
                            "score_outfit"] and set(stylist.keywords) == {"en", "fr", "ar"}
    assert (config.limits.max_tools, config.limits.max_rounds, config.limits.max_tokens) == (9, 6, 600)
    assert "{n}" in config.shared_rules


def test_an_unknown_tool_is_refused_with_the_agent_and_the_field(tmp_path):
    path = broken(tmp_path, lambda d: d["agents"]["stylist"]["tools"].append("teleport"))
    with pytest.raises(AgentsConfigError, match=r"agent 'stylist', field 'tools': tool 'teleport' is not registered"):
        load_agents(path, TOOLS)


def test_ten_tools_are_refused(tmp_path):
    path = broken(tmp_path, lambda d: d["agents"]["stylist"].update(tools=["list_wardrobe"] * 10))
    with pytest.raises(AgentsConfigError, match=r"agent 'stylist', field 'tools': 10 tools, but limits.max_tools is 9"):
        load_agents(path, TOOLS)


def test_a_missing_field_is_refused_with_the_agent_and_the_field(tmp_path):
    path = broken(tmp_path, lambda d: d["agents"]["stylist"].pop("instructions"))
    with pytest.raises(AgentsConfigError, match=r"agent 'stylist', field 'instructions': Field required"):
        load_agents(path, TOOLS)


def test_an_agent_above_the_global_limit_is_refused(tmp_path):
    path = broken(tmp_path, lambda d: d["agents"]["stylist"].update(max_rounds=7))
    with pytest.raises(AgentsConfigError, match=r"agent 'stylist', field 'max_rounds': 7 is above limits.max_rounds"):
        load_agents(path, TOOLS)


def test_the_model_settings_load():
    model = load_agents(REAL_FILE, TOOLS).model
    assert (model.temperature, model.top_p, model.top_k, model.presence_penalty) == (0.7, 0.8, 20, 1.5)
    assert (model.num_ctx, model.keep_alive, model.timeout_s, model.think) == (8192, "10m", 90, False)


def test_a_model_setting_out_of_range_is_refused(tmp_path):
    path = broken(tmp_path, lambda d: d["model"].update(top_p=1.5))
    with pytest.raises(AgentsConfigError, match=r"field 'model.top_p': Input should be less than or equal to 1"):
        load_agents(path, TOOLS)
