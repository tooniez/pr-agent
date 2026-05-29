"""Observability metadata + langfuse_span no-op-safety tests (plan §4.8 #6).

parse_observability_metadata: all-3 -> all 3; missing-one -> PARTIAL dict (not {});
non-string value -> key omitted; non-Mapping -> {}; never raises.
langfuse_span: no-op-safe when langfuse unavailable AND when meta is partial/empty."""
import pytest

from pr_agent.mosaico.observability import (langfuse_span,
                                            mosaico_log_context,
                                            parse_observability_metadata)


class TestParseObservabilityMetadata:
    def test_all_three(self):
        raw = {
            "mosaico-root-task-id": "r",
            "mosaico-super-task-id": "s",
            "mosaico-root-task-name": "n",
        }
        assert parse_observability_metadata(raw) == raw

    def test_missing_one_is_partial(self):
        raw = {"mosaico-root-task-id": "r", "mosaico-root-task-name": "n"}
        out = parse_observability_metadata(raw)
        assert out == {"mosaico-root-task-id": "r", "mosaico-root-task-name": "n"}
        assert out != {}

    def test_non_string_value_omitted(self):
        raw = {"mosaico-root-task-id": "r", "mosaico-super-task-id": 5}
        assert parse_observability_metadata(raw) == {"mosaico-root-task-id": "r"}

    def test_non_mapping_returns_empty(self):
        for bad in (None, [], "x", 7, ("a",)):
            assert parse_observability_metadata(bad) == {}

    def test_never_raises(self):
        # Exhaustive no-raise check across odd inputs.
        for bad in (None, {}, {"x": "y"}, [1, 2], "str", 0, object()):
            parse_observability_metadata(bad)


class TestLangfuseSpanNoOpSafety:
    def test_empty_meta_is_noop(self):
        ran = {"v": False}
        with langfuse_span({}, "ctx"):
            ran["v"] = True
        assert ran["v"] is True

    def test_none_meta_is_noop(self):
        with langfuse_span(None, "ctx"):
            pass  # must not raise

    def test_partial_meta_does_not_raise_when_langfuse_unavailable(self, monkeypatch):
        # Simulate langfuse import failure inside the CM; it must degrade to untraced.
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langfuse":
                raise ImportError("langfuse not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        ran = {"v": False}
        with langfuse_span({"mosaico-root-task-id": "r"}, "ctx"):
            ran["v"] = True
        assert ran["v"] is True  # body still executed despite langfuse failure

    def test_log_context_partial_and_empty(self):
        with mosaico_log_context({"mosaico-root-task-id": "r"}, "ctx"):
            pass
        with mosaico_log_context({}, None):
            pass
