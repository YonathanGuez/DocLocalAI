import re

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


class RerankerService:
    """Re-ranks a broad recall set down to the final top-k.

    Uses lexical term-overlap scoring rather than a neural cross-encoder
    (e.g. ms-marco-MiniLM) so it runs anywhere with no extra model download
    or GPU/CPU inference cost. It still implements the same two-stage
    "broad recall -> precision re-rank" pattern to counter "Lost in the
    Middle" when the initial retrieval set is large.
    """

    def rerank(
        self,
        query: str,
        chunks: list[tuple[str, str, float]],
        top_k: int = 3,
    ) -> list[tuple[str, str, float]]:
        """Re-rank (source, content, original_score) tuples by query term overlap.

        Returns the top_k tuples as (source, content, rerank_score), best first.
        Falls back to original ordering when the query has no usable terms.
        """
        if not chunks:
            return []

        query_terms = _tokenize(query)
        if not query_terms:
            return chunks[:top_k]

        scored = []
        for source, content, original_score in chunks:
            content_terms = _tokenize(content)
            overlap = len(query_terms & content_terms) / len(query_terms)
            # Blend lexical overlap with the original retrieval score so a
            # strong semantic match isn't discarded for missing exact words.
            rerank_score = (0.7 * overlap) + (0.3 * original_score)
            scored.append((source, content, rerank_score))

        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:top_k]
