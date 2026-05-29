"""Tests for the MOSAICO dispatch router (plan §4.8 test 2 + §5 capture/fallback).

Pins: each path returns a string and NEVER raises; no-files/no-suggestions/empty-ask
-> empty-fallback string; a tool that raises (monkeypatched) -> error-fallback string
with no exception escaping.

asyncio_mode=auto."""
import pytest

import pr_agent.mosaico.dispatch as dispatch
from pr_agent.config_loader import global_settings
from pr_agent.mosaico.dispatch import (_detect_verb, _empty_fallback,
                                       _error_fallback, route_and_run)

PR_URL = "https://github.com/org/repo/pull/123"

SAMPLE_DIFF = """```diff
diff --git a/foo.py b/foo.py
index 1111111..2222222 100644
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,2 @@
-x = 1
+x = 2
 y = 3
```"""

_SENTINEL = object()


@pytest.fixture
def restore_settings():
    """Snapshot/restore the settings keys the router mutates, leaving global_settings
    exactly as found."""
    keys = ["CONFIG.GIT_PROVIDER"]
    before = {k: global_settings.get(k, _SENTINEL) for k in keys}
    mosaico_existed = "MOSAICO" in global_settings
    mosaico_input = global_settings.get("MOSAICO.INPUT", _SENTINEL)
    data_before = global_settings.get("data", _SENTINEL)
    yield
    for k, v in before.items():
        if v is not _SENTINEL:
            global_settings.set(k, v)
    if not mosaico_existed:
        global_settings.unset("MOSAICO")
    elif mosaico_input is _SENTINEL:
        box = global_settings.get("MOSAICO")
        if box is not None and hasattr(box, "pop"):
            box.pop("INPUT", None)
    else:
        global_settings.set("MOSAICO.INPUT", mosaico_input)
    # Dynaconf merges dict assignments; explicitly blank the artifact when it was absent.
    if data_before is _SENTINEL:
        global_settings.data = {"artifact": ""}
    else:
        global_settings.data = data_before


def _set_artifact(value):
    # Mirror how the real tools stash output: attribute assignment replaces cleanly
    # (Dynaconf .set merges dicts, which would not overwrite a prior artifact).
    global_settings.data = {"artifact": value}


def _clear_artifact():
    # Dynaconf merges dict assignments, so an empty {} would not drop a prior 'artifact'.
    # Set the artifact explicitly empty (this is also the legitimate no-output state).
    global_settings.data = {"artifact": ""}


# ---------------------------------------------------------------------------
# Verb detection
# ---------------------------------------------------------------------------
class TestVerbDetection:
    def test_explicit_slash_verbs(self):
        assert _detect_verb("/review please") == "review"
        assert _detect_verb("/improve this") == "improve"
        assert _detect_verb("/describe it") == "describe"
        assert _detect_verb("/ask something") == "ask"

    def test_bare_verb_words(self):
        assert _detect_verb("review this PR") == "review"
        assert _detect_verb("improve the code") == "improve"

    def test_question_defaults_to_ask(self):
        assert _detect_verb("what does this change?") == "ask"
        assert _detect_verb("How is the error handled") == "ask"

    def test_default_is_review(self):
        assert _detect_verb("here is a blob of stuff") == "review"


# ---------------------------------------------------------------------------
# Path (a): host PR URL
# ---------------------------------------------------------------------------
class TestPathPrUrl:
    async def test_pr_url_runs_handle_request_and_returns_artifact(self, monkeypatch, restore_settings):
        captured = {}

        async def fake_handle_request(self, pr_url, request, notify=None):
            captured["pr_url"] = pr_url
            captured["request"] = request
            _set_artifact("REVIEW MARKDOWN")
            return True

        from pr_agent.agent.pr_agent import PRAgent
        monkeypatch.setattr(PRAgent, "handle_request", fake_handle_request)

        out = await route_and_run(f"review {PR_URL}")
        assert out == "REVIEW MARKDOWN"
        assert captured["pr_url"] == PR_URL
        assert captured["request"] == ["/review"]

    async def test_pr_url_leaves_git_provider_default(self, monkeypatch, restore_settings):
        global_settings.set("CONFIG.GIT_PROVIDER", "github")

        async def fake_handle_request(self, pr_url, request, notify=None):
            _set_artifact("OK")
            return True

        from pr_agent.agent.pr_agent import PRAgent
        monkeypatch.setattr(PRAgent, "handle_request", fake_handle_request)

        await route_and_run(f"review {PR_URL}")
        # path (a) must NOT switch the provider to mosaico_diff
        assert global_settings.get("CONFIG.GIT_PROVIDER") == "github"


# ---------------------------------------------------------------------------
# Path (b): supplied diff
# ---------------------------------------------------------------------------
class TestPathSuppliedDiff:
    async def test_diff_sets_provider_and_input(self, monkeypatch, restore_settings):
        captured = {}

        async def fake_handle_request(self, pr_url, request, notify=None):
            # read the context (here: global) settings the router set
            captured["git_provider"] = global_settings.get("CONFIG.GIT_PROVIDER")
            captured["mosaico_input"] = global_settings.get("MOSAICO.INPUT")
            captured["request"] = request
            _set_artifact("DIFF REVIEW")
            return True

        from pr_agent.agent.pr_agent import PRAgent
        monkeypatch.setattr(PRAgent, "handle_request", fake_handle_request)

        out = await route_and_run(f"review the following\n{SAMPLE_DIFF}")
        assert out == "DIFF REVIEW"
        assert captured["git_provider"] == "mosaico_diff"
        assert captured["request"] == ["/review"]
        mi = captured["mosaico_input"]
        assert mi and [f.filename for f in mi["files"]] == ["foo.py"]
        assert mi["title"] == "Supplied diff"

    async def test_unparseable_diff_returns_empty_fallback(self, monkeypatch, restore_settings):
        # looks like a diff (has a fence) but parse yields nothing
        out = await route_and_run("```diff\nnot really a diff\n```")
        assert out == _empty_fallback("review")


# ---------------------------------------------------------------------------
# Path (c): free-text question
# ---------------------------------------------------------------------------
class TestPathFreeText:
    async def test_free_text_uses_prquestions_not_pragent(self, monkeypatch, restore_settings):
        pr_agent_used = {"called": False}

        class FakePRQuestions:
            def __init__(self, pr_url, args=None, ai_handler=None):
                self.prediction = "ANSWER TEXT"

            async def run(self):
                return ""

        async def fail_handle_request(self, *a, **k):
            pr_agent_used["called"] = True
            return True

        monkeypatch.setattr("pr_agent.tools.pr_questions.PRQuestions", FakePRQuestions)
        from pr_agent.agent.pr_agent import PRAgent
        monkeypatch.setattr(PRAgent, "handle_request", fail_handle_request)

        out = await route_and_run("what does this codebase do?")
        assert out == "ANSWER TEXT"
        assert pr_agent_used["called"] is False

    async def test_empty_ask_returns_empty_fallback(self, monkeypatch, restore_settings):
        class FakePRQuestions:
            def __init__(self, pr_url, args=None, ai_handler=None):
                self.prediction = ""  # empty-diff ask path

            async def run(self):
                return ""

        monkeypatch.setattr("pr_agent.tools.pr_questions.PRQuestions", FakePRQuestions)
        out = await route_and_run("what is up?")
        assert out == _empty_fallback("ask")


# ---------------------------------------------------------------------------
# §5 defensive capture / fallbacks
# ---------------------------------------------------------------------------
class TestDefensiveCapture:
    async def test_handle_request_false_returns_error_fallback(self, monkeypatch, restore_settings):
        async def fake_handle_request(self, pr_url, request, notify=None):
            return False  # swallowed internal failure

        from pr_agent.agent.pr_agent import PRAgent
        monkeypatch.setattr(PRAgent, "handle_request", fake_handle_request)

        out = await route_and_run(f"review {PR_URL}")
        assert out == _error_fallback("review")

    async def test_ok_but_no_artifact_returns_empty_fallback(self, monkeypatch, restore_settings):
        async def fake_handle_request(self, pr_url, request, notify=None):
            # ok=True but never sets data["artifact"] (early-return paths in §5)
            return True

        from pr_agent.agent.pr_agent import PRAgent
        monkeypatch.setattr(PRAgent, "handle_request", fake_handle_request)
        # ensure no stale artifact from a prior test
        _clear_artifact()

        out = await route_and_run(f"review {PR_URL}")
        assert out == _empty_fallback("review")

    async def test_ask_that_raises_returns_error_fallback(self, monkeypatch, restore_settings):
        class RaisingPRQuestions:
            def __init__(self, pr_url, args=None, ai_handler=None):
                self.prediction = None

            async def run(self):
                raise RuntimeError("boom")

        monkeypatch.setattr("pr_agent.tools.pr_questions.PRQuestions", RaisingPRQuestions)
        out = await route_and_run("what is the meaning of this?")
        assert out == _error_fallback("ask")

    async def test_route_and_run_never_raises_on_garbage(self, restore_settings):
        # No monkeypatching: a host-less PR-agent run / ask should still return a string.
        for text in ("", None, "   ", "random text with no url and no diff"):
            out = await route_and_run(text)
            assert isinstance(out, str)
