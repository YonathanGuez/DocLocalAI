from openai import OpenAI
from psycopg import Connection
from app.config import settings
from app.repositories import SessionRepository, MessageRepository, RunbookRepository, PromptRepository
from app.services.embedding_service import EmbeddingService
from app.exceptions import LLMException


class ChatService:
    def __init__(self):
        self.llm_client = OpenAI(
            base_url=settings.llm_endpoint_url,
            api_key=settings.llm_api_token
        )
        self.embedding_service = EmbeddingService()

    def retrieve_context(self, conn: Connection, query: str) -> tuple[str, list[str], float]:
        """Retrieve relevant context from runbooks using vector search

        Returns:
            tuple: (context_text, list of source filenames, max_similarity_score)
        """
        query_vector = self.embedding_service.get_embedding(query)

        if not query_vector:
            return "", [], 0.0

        try:
            rows = RunbookRepository.search_similar_chunks(
                conn,
                query_vector,
                settings.top_k_context
            )

            if not rows:
                return "No runbooks indexed yet.", [], 0.0

            # Filter by similarity threshold
            relevant_rows = [(source, content, score) for source, content, score in rows
                            if score >= settings.similarity_threshold]

            if not relevant_rows:
                # No chunks meet the similarity threshold
                max_score = max([r[2] for r in rows]) if rows else 0.0
                return f"No relevant runbooks found (max similarity: {max_score:.2f}, threshold: {settings.similarity_threshold:.2f})", [], max_score

            # Extract unique source files from relevant results
            sources = list(set([r[0] for r in relevant_rows]))

            # Build context with source markers
            context = "\n\n".join([f"[Source: {r[0]}]\n{r[1]}" for r in relevant_rows])

            # Get max similarity score
            max_score = max([r[2] for r in relevant_rows])

            return context, sources, max_score
        except Exception as exc:
            return f"Context lookup skipped: {exc}", [], 0.0

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
        # Retrieve runbook context, sources, and similarity score
        context, sources, similarity = self.retrieve_context(conn, user_message)

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

        # Get conversation history
        history = MessageRepository.get_conversation_history(
            conn,
            session_id,
            settings.history_window_size
        )

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

            # Automatically append source citations if sources were used
            if sources:
                source_citation = f"\n\n*Relevance: {similarity:.1%}*"
                source_citation += "\n\n---\n📚 **Source:** " + ", ".join(sources)
                response += source_citation

            return response
        except Exception as e:
            raise LLMException(f"LLM completion failed: {str(e)}")

    def process_chat(
        self,
        conn: Connection,
        session_id: str,
        message: str
    ) -> tuple[str, str]:
        """Process a chat message end-to-end"""
        # Create/update session
        title_preview = message[:60] + ("..." if len(message) > 60 else "")
        SessionRepository.create_or_update(conn, session_id, title_preview)

        # Save user message
        MessageRepository.save_message(conn, session_id, "user", message)

        # Generate AI response
        assistant_reply = self.generate_response(conn, session_id, message)

        # Save assistant reply
        MessageRepository.save_message(
            conn,
            session_id,
            "assistant",
            assistant_reply,
            settings.llm_model_name
        )

        # Update session timestamp
        SessionRepository.touch_session(conn, session_id)

        return assistant_reply, settings.llm_model_name
