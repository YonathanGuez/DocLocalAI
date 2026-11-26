import re

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_SUFFIXES = ("ing", "ed", "es", "s")


def _stem(word: str) -> str:
    """Strip common suffixes so e.g. "restart"/"restarts"/"restarting" match.

    Deliberately crude (no real morphology) — just enough to stop plural/verb
    forms from being treated as unrelated tokens during overlap scoring.
    """
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> list[str]:
    return [_stem(w) for w in _WORD_PATTERN.findall(text.lower())]


def _tokenize(text: str) -> set[str]:
    return set(_tokens(text))


def _proximity_score(content_tokens: list[str], matched_terms: set[str]) -> float:
    """How tightly the matched query terms cluster together in the content.

    1.0 means every matched term occurs back-to-back somewhere (a real phrase
    match, e.g. "restart the pod"); a lower score means the terms only occur
    scattered far apart (e.g. "restart" and "pod" showing up in unrelated
    sentences of a long chunk). This stops a chunk that merely contains both
    words *somewhere* from outscoring a chunk where they form an actual phrase.
    """
    if len(matched_terms) <= 1:
        return 1.0

    positions = [i for i, tok in enumerate(content_tokens) if tok in matched_terms]
    if not positions:
        return 0.0

    need = len(matched_terms)
    counts: dict[str, int] = {}
    have = 0
    left = 0
    best_window = None

    for right, idx in enumerate(positions):
        term = content_tokens[idx]
        counts[term] = counts.get(term, 0) + 1
        if counts[term] == 1:
            have += 1
        while have == need:
            window = positions[right] - positions[left] + 1
            if best_window is None or window < best_window:
                best_window = window
            left_term = content_tokens[positions[left]]
            counts[left_term] -= 1
            if counts[left_term] == 0:
                have -= 1
            left += 1

    if best_window is None:
        return 0.0
    return min(1.0, need / best_window)


class RerankerService:
    """Re-ranks a broad recall set down to the final top-k.

    Uses lexical term-overlap + proximity scoring rather than a neural
    cross-encoder (e.g. ms-marco-MiniLM) so it runs anywhere with no extra
    model download or GPU/CPU inference cost. It still implements the same
    two-stage "broad recall -> precision re-rank" pattern to counter
    "Lost in the Middle" when the initial retrieval set is large.
    """

    def rerank(
        self,
        query: str,
        chunks: list[tuple[str, str, float]],
        top_k: int = 3,
    ) -> list[tuple[str, str, float]]:
        """Re-rank (source, content, original_score) tuples by query term overlap
        weighted by how close together those terms appear in the content.

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
            content_tokens = _tokens(content)
            matched_terms = query_terms & set(content_tokens)
            overlap = len(matched_terms) / len(query_terms)
            proximity = _proximity_score(content_tokens, matched_terms) if matched_terms else 0.0
            lexical_score = overlap * proximity

            # Lexical/proximity match is the primary signal — a real phrase
            # match should win even against a much higher original retrieval
            # score. The original score only breaks ties / helps when there's
            # no exact lexical match at all (pure semantic relevance).
            rerank_score = (0.85 * lexical_score) + (0.15 * original_score)
            scored.append((source, content, rerank_score))

        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:top_k]
