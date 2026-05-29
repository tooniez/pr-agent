"""Tests for the MOSAICO agent card (plan §4.8 test 1)."""
from pr_agent.mosaico.card import (OBSERVABILITY_EXTENSION_URI,
                                   build_agent_card)


class TestAgentCard:
    def test_protocol_version_0_3_0(self):
        card = build_agent_card()
        assert card.protocol_version == "0.3.0"

    def test_streaming_false(self):
        card = build_agent_card()
        assert card.capabilities.streaming is False

    def test_observability_extension_required(self):
        card = build_agent_card()
        exts = card.capabilities.extensions
        assert exts, "no extensions advertised"
        obs = [e for e in exts if e.uri == OBSERVABILITY_EXTENSION_URI]
        assert len(obs) == 1, "observability extension not found exactly once"
        assert obs[0].required is True

    def test_observability_extension_uri_value(self):
        assert OBSERVABILITY_EXTENSION_URI == \
            "https://mosaico-project.eu/extensions/mosaico-observability"

    def test_four_skills(self):
        card = build_agent_card()
        skill_ids = {s.id for s in card.skills}
        assert skill_ids == {"review", "improve", "describe", "ask"}

    def test_url_ends_with_slash(self):
        card = build_agent_card()
        assert card.url.endswith("/")

    def test_input_output_modes(self):
        card = build_agent_card()
        assert card.default_input_modes == ["text", "text/plain"]
        assert "text/markdown" in card.default_output_modes

    def test_version_is_nonempty(self):
        card = build_agent_card()
        assert isinstance(card.version, str) and card.version
