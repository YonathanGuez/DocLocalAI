from datetime import datetime, timezone

import pytest

from app.config import settings
from app.services.chat_service import ChatService
from app.repositories import MessageRepository, PromptRepository, RunbookRepository
from app.models import PromptTemplate


@pytest.fixture
def chat_service():
    return ChatService()


def test_retrieve_context_routes_list_sources_query(chat_service, mocker):
    mocker.patch.object(
        RunbookRepository, "get_distinct_sources",
        return_value=[("pods.md", 3), ("network.md", 2)],
    )
    search_spy = mocker.patch.object(RunbookRepository, "search_similar_chunks")

    context, sources, score, chunk_map = chat_service.retrieve_context(None, "What runbooks do you have?")

    assert "pods.md" in context
    assert sources == ["pods.md", "network.md"]
    assert score == 1.0
    assert chunk_map == {}
    search_spy.assert_not_called()


def test_retrieve_context_vector_search_merges_expansions(chat_service, mocker, monkeypatch):
    # Isolate the merge logic from hybrid search / reranking (tested separately)
    monkeypatch.setattr(settings, "enable_hybrid_search", False)
    monkeypatch.setattr(settings, "enable_reranker", False)
    mocker.patch.object(chat_service.embedding_service, "get_embedding", return_value=[0.1, 0.2])
    mocker.patch.object(
        RunbookRepository, "search_similar_chunks",
        return_value=[("pods.md", "Restart a pod with kubectl delete pod.", 0.9)],
    )

    context, sources, score, chunk_map = chat_service.retrieve_context(None, "pod error")

    assert sources == ["pods.md"]
    assert score == 0.9
    assert "[1] [Source: pods.md]" in context
    assert chunk_map["[1]"][0] == "pods.md"


def test_retrieve_context_below_threshold_returns_no_sources(chat_service, mocker, monkeypatch):
    monkeypatch.setattr(settings, "enable_hybrid_search", False)
    monkeypatch.setattr(settings, "enable_reranker", False)
    mocker.patch.object(chat_service.embedding_service, "get_embedding", return_value=[0.1])
    mocker.patch.object(
        RunbookRepository, "search_similar_chunks",
        return_value=[("pods.md", "unrelated content", 0.1)],
    )
    monkeypatch.setattr(settings, "similarity_threshold", 0.4)

    context, sources, score, chunk_map = chat_service.retrieve_context(None, "pod error")

    assert sources == []
    assert score == 0.1
    assert chunk_map == {}


def test_retrieve_context_reranks_broad_recall_set_by_default(chat_service, mocker):
    # Default settings: hybrid search + reranker both enabled
    mocker.patch.object(chat_service.embedding_service, "get_embedding", return_value=[0.1, 0.2])
    mocker.patch.object(
        RunbookRepository, "hybrid_search",
        return_value=[
            ("pods.md", "Restart a pod with kubectl delete pod.", 0.9),
            ("network.md", "Check routes with oc get routes.", 0.5),
        ],
    )

    context, sources, score, chunk_map = chat_service.retrieve_context(None, "pod error")

    # "pods.md" has lexical overlap with "pod error"; "network.md" has none,
    # so the reranked ordering should put pods.md first with a blended score.
    assert sources == ["pods.md"]
    assert score == pytest.approx(0.85 * 0.5 + 0.15 * 0.9)


def test_retrieve_context_hybrid_search_failure_falls_back_to_vector_search(chat_service, mocker, monkeypatch):
    monkeypatch.setattr(settings, "enable_reranker", False)
    mocker.patch.object(chat_service.embedding_service, "get_embedding", return_value=[0.1])
    mocker.patch.object(RunbookRepository, "hybrid_search", side_effect=RuntimeError("no content_tsv column"))
    mocker.patch.object(
        RunbookRepository, "search_similar_chunks",
        return_value=[("pods.md", "Restart a pod with kubectl delete pod.", 0.9)],
    )

    context, sources, score, chunk_map = chat_service.retrieve_context(None, "pod error")

    assert sources == ["pods.md"]
    assert score == 0.9


def test_generate_response_list_sources_bypasses_llm(chat_service, mocker):
    mocker.patch.object(MessageRepository, "get_conversation_history", return_value=[])
    mocker.patch.object(
        RunbookRepository, "get_distinct_sources",
        return_value=[("pods.md", 3), ("network.md", 2)],
    )
    llm_spy = mocker.patch.object(chat_service.llm_client.chat.completions, "create")

    reply = chat_service.generate_response(None, "11111111-1111-1111-1111-111111111111", "What runbooks do you have?")

    assert "pods.md" in reply
    assert "network.md" in reply
    llm_spy.assert_not_called()


def test_generate_response_asks_for_clarification_on_ambiguous_query(chat_service, mocker):
    mocker.patch.object(MessageRepository, "get_conversation_history", return_value=[])
    search_spy = mocker.patch.object(RunbookRepository, "search_similar_chunks")

    reply = chat_service.generate_response(None, "11111111-1111-1111-1111-111111111111", "why?")

    assert "clarify" in reply.lower()
    search_spy.assert_not_called()


def test_generate_response_raw_mode_skips_llm_call(chat_service, mocker, monkeypatch):
    monkeypatch.setattr(settings, "rag_strategy", "raw")
    mocker.patch.object(MessageRepository, "get_conversation_history", return_value=[])
    mocker.patch.object(chat_service.embedding_service, "get_embedding", return_value=[0.1])
    mocker.patch.object(
        RunbookRepository, "search_similar_chunks",
        return_value=[("pods.md", "Restart a pod with kubectl delete pod.", 0.9)],
    )
    llm_spy = mocker.patch.object(chat_service.llm_client.chat.completions, "create")

    reply = chat_service.generate_response(None, "11111111-1111-1111-1111-111111111111", "how do I restart a pod")

    assert "pods.md" in reply
    llm_spy.assert_not_called()


def test_generate_response_synthesis_mode_appends_inline_citation_footer(chat_service, mocker, monkeypatch):
    monkeypatch.setattr(settings, "rag_strategy", "synthesis")
    mocker.patch.object(MessageRepository, "get_conversation_history", return_value=[])
    mocker.patch.object(chat_service.embedding_service, "get_embedding", return_value=[0.1])
    mocker.patch.object(
        RunbookRepository, "search_similar_chunks",
        return_value=[("pods.md", "Restart a pod with kubectl delete pod.", 0.9)],
    )
    mocker.patch.object(
        PromptRepository, "get_prompt_by_name",
        return_value=PromptTemplate(
            prompt_id="p1", name="Synthesis Mode", description=None,
            prompt_text="You are {assistant_name}.\n\n{context}",
            is_builtin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    )

    fake_completion = mocker.Mock()
    fake_completion.choices = [mocker.Mock(message=mocker.Mock(content="Restart it with kubectl [1]."))]
    mocker.patch.object(chat_service.llm_client.chat.completions, "create", return_value=fake_completion)

    reply = chat_service.generate_response(None, "11111111-1111-1111-1111-111111111111", "how do I restart a pod")

    assert "[1] pods.md" in reply
    assert "📚 **Source:**" not in reply  # per-claim footer replaces the generic one


def test_generate_response_blocks_credential_leak(chat_service, mocker, monkeypatch):
    monkeypatch.setattr(settings, "rag_strategy", "synthesis")
    mocker.patch.object(MessageRepository, "get_conversation_history", return_value=[])
    mocker.patch.object(chat_service.embedding_service, "get_embedding", return_value=[0.1])
    mocker.patch.object(
        RunbookRepository, "search_similar_chunks",
        return_value=[("pods.md", "Restart a pod with kubectl delete pod.", 0.9)],
    )
    mocker.patch.object(
        PromptRepository, "get_prompt_by_name",
        return_value=PromptTemplate(
            prompt_id="p1", name="Synthesis Mode", description=None,
            prompt_text="You are {assistant_name}.\n\n{context}",
            is_builtin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    )

    fake_completion = mocker.Mock()
    fake_completion.choices = [mocker.Mock(message=mocker.Mock(
        content="Use api_key=sk-1234567890abcdef to authenticate."
    ))]
    mocker.patch.object(chat_service.llm_client.chat.completions, "create", return_value=fake_completion)

    reply = chat_service.generate_response(None, "11111111-1111-1111-1111-111111111111", "how do I restart a pod")

    assert "blocked" in reply.lower()
    assert "sk-1234567890abcdef" not in reply


def test_generate_response_flags_dangerous_command(chat_service, mocker, monkeypatch):
    monkeypatch.setattr(settings, "rag_strategy", "synthesis")
    mocker.patch.object(MessageRepository, "get_conversation_history", return_value=[])
    mocker.patch.object(chat_service.embedding_service, "get_embedding", return_value=[0.1])
    mocker.patch.object(
        RunbookRepository, "search_similar_chunks",
        return_value=[("pods.md", "Restart a pod with kubectl delete pod.", 0.9)],
    )
    mocker.patch.object(
        PromptRepository, "get_prompt_by_name",
        return_value=PromptTemplate(
            prompt_id="p1", name="Synthesis Mode", description=None,
            prompt_text="You are {assistant_name}.\n\n{context}",
            is_builtin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    )

    fake_completion = mocker.Mock()
    fake_completion.choices = [mocker.Mock(message=mocker.Mock(content="Just run rm -rf / to clean up."))]
    mocker.patch.object(chat_service.llm_client.chat.completions, "create", return_value=fake_completion)

    reply = chat_service.generate_response(None, "11111111-1111-1111-1111-111111111111", "how do I restart a pod")

    assert "SAFETY WARNING" in reply
    assert "rm -rf /" in reply  # still shown, just flagged
