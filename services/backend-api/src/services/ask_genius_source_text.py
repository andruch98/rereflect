"""Match typographic variants only against text from the authorized record."""
import re


def recovered_excerpt(original: str, candidate: str) -> str | None:
    if candidate in original:
        return candidate
    # Match the same words, in the same order and case, then return the original span.
    # Normalization never changes digits, negation, or other punctuation.
    chunks = re.findall(r"\s+|['‘’]|[^\s'‘’]+", candidate.strip())
    if not chunks:
        return None
    pattern = ''.join(r'\s+' if chunk.isspace() else "['‘’]" if chunk in "'‘’" else re.escape(chunk)
                      for chunk in chunks)
    matcher = re.compile(pattern)
    first = matcher.search(original)
    if first is None or matcher.search(original, first.start() + 1) is not None:
        return None
    return first.group()
