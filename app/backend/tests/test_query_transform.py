from app.services.query_transform import (
    build_rewrite_prompt,
    expand_query,
    is_ambiguous,
    needs_history_rewrite,
)


def test_is_ambiguous_flags_single_word_question():
    assert is_ambiguous("how?") is True
    assert is_ambiguous("why") is True


def test_is_ambiguous_flags_pronoun_reference():
    assert is_ambiguous("it is broken") is True
    assert is_ambiguous("that doesn't work") is True


def test_is_ambiguous_false_for_clear_query():
    assert is_ambiguous("How do I restart a pod in OpenShift?") is False


def test_needs_history_rewrite_requires_history_and_pronoun():
    history = [{"role": "user", "content": "How do I restart a pod?"}]
    assert needs_history_rewrite("what about that one", history) is True
    assert needs_history_rewrite("what about that one", []) is False
    assert needs_history_rewrite("how do I list pods", history) is False


def test_expand_query_adds_synonyms():
    expansions = expand_query("pod error", limit=3)
    assert expansions[0] == "pod error"
    assert len(expansions) <= 3
    assert len(expansions) > 1


def test_expand_query_no_match_returns_original_only():
    expansions = expand_query("completely unrelated topic")
    assert expansions == ["completely unrelated topic"]


def test_build_rewrite_prompt_includes_query_and_history():
    history = [{"role": "user", "content": "How do I restart a pod?"}]
    prompt = build_rewrite_prompt("what about that", history)
    assert "what about that" in prompt
    assert "How do I restart a pod?" in prompt
