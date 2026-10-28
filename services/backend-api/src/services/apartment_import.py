"""Validate the private normalized experiment CSV without losing text."""


def validate_rows(rows):
    if len(rows) != 6:
        raise ValueError("Apartment experiment requires exactly six rows")
    result, seen, sources = [], set(), set()
    required = {"text", "star_rating", "source_external_id", "source"}
    for row in rows:
        if set(row) != required or any(value is None for value in row.values()):
            raise ValueError("Use only text, star_rating, source_external_id, source columns")
        source_id = row["source_external_id"]
        if not source_id or len(source_id) > 255 or source_id in seen:
            raise ValueError("Source IDs must be nonempty and unique")
        if row["star_rating"] not in {"1", "2", "3", "4", "5"}:
            raise ValueError("Star rating must be an integer from 1 to 5")
        if row["source"] not in {"apartment_review_ai", "apartment_review_fallback"}:
            raise ValueError("Invalid apartment experiment source")
        seen.add(source_id)
        sources.add(row["source"])
        result.append(dict(row, star_rating=int(row["star_rating"])))
    if len(sources) != 1:
        raise ValueError("Import AI and fallback runs separately")
    return result
