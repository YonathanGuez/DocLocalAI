from openai import OpenAI
import httpx
from psycopg import Connection
from app.config import settings
from app.repositories import SessionRepository, MessageRepository, RunbookRepository, PromptRepository
from app.services.embedding_service import EmbeddingService
from app.services.reranker_service import RerankerService
from app.services.citations import build_context_with_citations, extract_citations, format_citations_footer
from app.schemas.response_schema import BusinessRuleValidator
from app.services.query_router import QueryType, extract_metadata_filter, route_query
from app.services.query_transform import build_rewrite_prompt, expand_query, is_ambiguous, needs_history_rewrite
from app.exceptions import LLMException

CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"


class ChatService:
    def __init__(self):
        http_client = httpx.Client(verify=False)
        self.llm_client = OpenAI(
            base_url=settings.llm_endpoint_url,
            api_key=settings.llm_api_token,
            http_client=http_client
        )
        self.embedding_service = EmbeddingService()
        self.reranker = RerankerService()

    def retrieve_context(
        self, conn: Connection, query: str, history: list[dict] | None = None
    ) -> tuple[str, list[str], float, dict[str, tuple[str, str]]]:
        """Retrieve relevant context from runbooks, routing the query first.

        Returns:
            tuple: (context_text, list of source filenames, max_similarity_score, chunk_map)
            chunk_map maps "[N]" citation markers to (source, content) for inline citations.
        """
        history = history or []
        query_type = route_query(query)

        try:
            if query_type == QueryType.LIST_SOURCES:
                sources_rows = RunbookRepository.get_distinct_sources(conn)
                if not sources_rows:
                    return "No runbooks indexed yet.", [], 0.0, {}
                context = "Available runbooks:\n" + "\n".join(
                    f"- {src} ({count} sections)" for src, count in sources_rows
                )
                return context, [row[0] for row in sources_rows], 1.0, {}

            # Resolve pronoun references against recent history before embedding
            if needs_history_rewrite(query, history):
                query = self._rewrite_standalone_query(query, history)

            threshold = settings.similarity_threshold
            if query_type == QueryType.METADATA_FILTER:
                source_filter = extract_metadata_filter(query)
                query_vector = self.embedding_service.get_embedding(query)
                if not query_vector or not source_filter:
                    return "", [], 0.0, {}
                rows = RunbookRepository.search_similar_chunks_by_source(
                    conn, query_vector, source_filter, settings.top_k_context
                )
            else:
                rows, reranked = self._vector_search_with_expansion(conn, query)
                # Reranked scores are a lexical/RRF blend, not raw cosine
                # similarity, so they need their own threshold scale.
                if reranked:
                    threshold = settings.rerank_threshold

            if not rows:
                return "No runbooks indexed yet.", [], 0.0, {}

            # Filter by similarity threshold
            relevant_rows = [(source, content, score) for source, content, score in rows
                            if score >= threshold]

            if not relevant_rows:
                # No chunks meet the similarity threshold
                max_score = max([r[2] for r in rows]) if rows else 0.0
                return f"No relevant runbooks found (max similarity: {max_score:.2f}, threshold: {threshold:.2f})", [], max_score, {}

            # Extract unique source files from relevant results
            sources = list(set([r[0] for r in relevant_rows]))

            # Build context with inline [N] citation markers
            context, chunk_map = build_context_with_citations(relevant_rows)

            # Get max similarity score
            max_score = max([r[2] for r in relevant_rows])

            return context, sources, max_score, chunk_map
        except Exception as exc:
            return f"Context lookup skipped: {exc}", [], 0.0, {}

    def _vector_search_with_expansion(
        self, conn: Connection, query: str
    ) -> tuple[list[tuple[str, str, float]], bool]:
        """Search the base query plus a few synonym expansions, merging by best score.

        Retrieves a broad recall set (hybrid BM25+vector when enabled) and
        narrows it to top_k_context with lexical re-ranking when enabled.

        Returns: (rows, was_reranked)
        """
        best_by_key: dict[tuple[str, str], tuple[str, str, float]] = {}
        recall_k = settings.initial_retrieval_k if settings.enable_reranker else settings.top_k_context

        for variant in expand_query(query):
            query_vector = self.embedding_service.get_embedding(variant)
            if not query_vector:
                continue

            rows = None
            if settings.enable_hybrid_search:
                try:
                    rows = RunbookRepository.hybrid_search(conn, variant, query_vector, recall_k)
                except Exception:
                    rows = None
            if rows is None:
                rows = RunbookRepository.search_similar_chunks(conn, query_vector, recall_k)

            for source, content, score in rows:
                key = (source, content)
                if key not in best_by_key or score > best_by_key[key][2]:
                    best_by_key[key] = (source, content, score)

        merged = sorted(best_by_key.values(), key=lambda r: r[2], reverse=True)[:recall_k]

        if settings.enable_reranker and merged:
            return self.reranker.rerank(query, merged, top_k=settings.top_k_context), True

        return merged[:settings.top_k_context], False

    def _rewrite_standalone_query(self, query: str, history: list[dict]) -> str:
        """Use the LLM to resolve pronoun references against recent history."""
        try:
            prompt = build_rewrite_prompt(query, history)
            response = self.llm_client.chat.completions.create(
                model=settings.llm_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=100,
            )
            rewritten = response.choices[0].message.content.strip()
            return rewritten or query
        except Exception:
            return query

    def format_raw_retrieval(self, context: str, sources: list[str], similarity: float) -> str:
        """Format response with ONLY source references (no content chunks)

        For small models, we return only the source document names,
        letting users click to view the full runbook content.
        """
        if not sources:
            return (
                "❌ **I don't have runbooks on this subject.**\n\n"
                f"The closest match I found had a similarity of {similarity:.1%}, "
                f"which is below the relevance threshold of {settings.similarity_threshold:.1%}.\n\n"
                "💡 **Suggestions:**\n"
                "- Try rephrasing your question\n"
                "- Upload relevant runbooks via the sidebar\n"
                "- Ask about OpenShift pods, networking, or troubleshooting topics"
            )

        if "No runbooks indexed" in context:
            return "⚠️ **No runbooks have been uploaded yet.**\n\nPlease upload runbooks via the sidebar to get started."

        # Return ONLY source references, not the actual content
        if len(sources) == 1:
            result = f"✅ I found relevant information in this runbook:\n\n📄 **{sources[0]}**"
        else:
            result = "✅ I found relevant information in these runbooks:\n\n"
            result += "\n".join([f"📄 **{source}**" for source in sources])

        result += f"\n\n💡 Click the source button below to view the full runbook content."
        result += f"\n\n*Relevance: {similarity:.1%}*"
        result += "\n\n---\n📚 **Source:** " + ", ".join(sources)

        return result

    def generate_response(
        self,
        conn: Connection,
        session_id: str,
        user_message: str
    ) -> str:
        """Generate AI response for user message"""
        # Get conversation history up front so it can inform query rewriting
        history = MessageRepository.get_conversation_history(
            conn,
            session_id,
            settings.history_window_size
        )

        # Ask for clarification on truly vague queries we can't resolve from history
        if is_ambiguous(user_message) and not needs_history_rewrite(user_message, history):
            return (
                "🤔 **Could you clarify your question?**\n\n"
                "Your question is quite broad. Try asking about a specific topic, "
                "command, or error you're seeing."
            )

        # Retrieve runbook context, sources, similarity score, and citation map
        context, sources, similarity, chunk_map = self.retrieve_context(conn, user_message, history)

        # List/browse queries are answered directly from the retrieved listing;
        # routing them through the LLM risks it misreading the listing as "no docs".
        if route_query(user_message) == QueryType.LIST_SOURCES and sources:
            return (
                "📚 **Here are the runbooks I have access to:**\n\n"
                + "\n".join(f"- {source}" for source in sources)
            )

        # If no relevant sources found, return helpful message
        if not sources:
            return (
                "❌ **I don't have runbooks on this subject.**\n\n"
                f"The closest match I found had a similarity of {similarity:.1%}, "
                f"which is below the relevance threshold of {settings.similarity_threshold:.1%}.\n\n"
                "💡 **Suggestions:**\n"
                "- Try rephrasing your question\n"
                "- Upload relevant runbooks via the sidebar\n"
                "- Ask about OpenShift pods, networking, or troubleshooting topics"
            )

        if "No runbooks indexed" in context:
            return "⚠️ **No runbooks have been uploaded yet.**\n\nPlease upload runbooks via the sidebar to get started."

        # Build system prompt using template from database
        assistant_name = settings.app_title.split("—")[0].strip() if "—" in settings.app_title else settings.app_title

        # Determine which prompt template to use
        prompt_name = None
        if settings.active_prompt:
            # Use explicitly set prompt
            prompt_name = settings.active_prompt
        elif settings.rag_strategy == "synthesis":
            prompt_name = "Synthesis Mode"
        elif settings.rag_strategy == "raw":
            prompt_name = "Raw Mode"
        else:  # auto
            # Detect small models by name pattern
            model_lower = settings.llm_model_name.lower()
            small_model_patterns = ["0.5b", "1b", "1.5b", "tiny", "small"]
            if any(pattern in model_lower for pattern in small_model_patterns):
                prompt_name = "Raw Mode"
            else:
                prompt_name = "Synthesis Mode"

        # Special handling for Raw Mode: return source references only (no LLM call)
        if prompt_name == "Raw Mode":
            return self.format_raw_retrieval(context, sources, similarity)

        # For all other modes (Synthesis Mode or custom prompts), proceed with LLM call
        # Load prompt template from database
        try:
            prompt_template = PromptRepository.get_prompt_by_name(conn, prompt_name)
            if prompt_template:
                # Format the template with variables
                system_prompt = prompt_template.prompt_text.format(
                    assistant_name=assistant_name,
                    context=context
                )
            else:
                # Fallback to Raw Mode if template not found
                system_prompt = (
                    f"You are {assistant_name}. Answer ONLY based on the documentation below.\n\n"
                    f"{context}\n\nQuestion: "
                )
        except Exception as e:
            # Fallback on error
            system_prompt = (
                f"You are {assistant_name}. Answer ONLY based on the documentation below.\n\n"
                f"{context}\n\nQuestion: "
            )

        messages = [{"role": "system", "content": system_prompt}] + history

        # Call LLM for synthesis
        try:
            completion = self.llm_client.chat.completions.create(
                model=settings.llm_model_name,
                messages=messages,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
            )
            response = completion.choices[0].message.content

            # Block responses that leak credentials or suggest destructive commands,
            # even though the documentation is the only source the model was given.
            leaked_credential = BusinessRuleValidator.find_credential_leak(response)
            if leaked_credential:
                return "❌ Response blocked: may contain sensitive credentials."

            dangerous_command = BusinessRuleValidator.find_dangerous_command(response)
            if dangerous_command:
                response = f"⚠️ **SAFETY WARNING:** response contained a potentially destructive command and was flagged.\n\n{response}"

            # Prefer per-claim [N] citations when the model actually used them,
            # otherwise fall back to a generic source list.
            citation_details = extract_citations(response, chunk_map)
            footer = format_citations_footer(citation_details)
            if sources:
                response += f"\n\n*Relevance: {similarity:.1%}*"
                if footer:
                    response += footer
                else:
                    response += "\n\n---\n📚 **Source:** " + ", ".join(sources)

            return response
        except Exception as e:
            print(f"❌ LLM error: {e}")
            import traceback
            traceback.print_exc()
            raise LLMException(f"LLM completion failed: {str(e)}")

    def process_chat(
        self,
        conn: Connection,
        session_id: str,
        message: str
    ) -> tuple[str, str]:
        """Process a chat message end-to-end"""
        try:
            # Create/update session
            print(f"📝 Creating/updating session {session_id}")
            title_preview = message[:60] + ("..." if len(message) > 60 else "")
            SessionRepository.create_or_update(conn, session_id, title_preview)
            print(f"✅ Session created/updated")

            # Save user message
            print(f"💬 Saving user message")
            MessageRepository.save_message(conn, session_id, "user", message)
            print(f"✅ User message saved")

            # Generate AI response
            print(f"🤖 Generating AI response")
            assistant_reply = self.generate_response(conn, session_id, message)
            print(f"✅ AI response generated: {assistant_reply[:100]}...")

            # Save assistant reply
            print(f"💾 Saving assistant reply")
            MessageRepository.save_message(
                conn,
                session_id,
                "assistant",
                assistant_reply,
                settings.llm_model_name
            )
            print(f"✅ Assistant reply saved")

            # Update session timestamp
            print(f"⏰ Updating session timestamp")
            SessionRepository.touch_session(conn, session_id)
            print(f"✅ Session timestamp updated")

            return assistant_reply, settings.llm_model_name
        except Exception as e:
            print(f"❌ Error in process_chat: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
