"""Select exact private IDs; emit normalized AI/fallback CSVs and a manifest."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path


def prepare(csv_path, ids_path, output, id_column, text_column, rating_column):
    ids = json.loads(Path(ids_path).read_text())
    if not isinstance(ids, list) or len(ids) != 6 or any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != 6:
        raise ValueError("IDs file must be a JSON array of exactly six distinct source IDs")
    with Path(csv_path).open(newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("Missing or duplicate CSV headers")
        for column in (id_column, text_column, rating_column):
            if column not in reader.fieldnames:
                raise ValueError("Missing column: " + column)
        rows = list(reader)
    selected = []
    for source_id in ids:
        matches = [r for r in rows if r[id_column] == source_id]
        if len(matches) != 1:
            raise ValueError("Each requested ID must occur exactly once; found " + str(len(matches)))
        row = matches[0]
        if row[text_column] is None or row[rating_column] is None:
            raise ValueError("Malformed row with missing text/rating cell")
        # Permit typical CSV numeric representation without guessing named ratings.
        raw_rating = row[rating_column].strip()
        if raw_rating not in {str(i) for i in range(1, 6)} | {str(i)+'.0' for i in range(1, 6)}:
            raise ValueError("Unusable star rating")
        selected.append({"source_id": source_id, "star_rating": int(float(raw_rating)), "text": row[text_column]})
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    manifest = {"source_sha256": hashlib.sha256(Path(csv_path).read_bytes()).hexdigest(),
                "source_headers": reader.fieldnames, "records": selected}
    (out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    for mode in ('ai', 'fallback'):
        with (out/(mode+'.csv')).open('w', newline='', encoding='utf-8') as target:
            writer = csv.DictWriter(target, fieldnames=['text', 'star_rating', 'source_external_id', 'source'])
            writer.writeheader()
            for record in selected:
                writer.writerow({'text':record['text'], 'star_rating':record['star_rating'],
                                 'source_external_id':record['source_id'], 'source':'apartment_review_'+mode})
    for p in out.iterdir(): os.chmod(p, 0o600)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('csv', 'ids', 'output', 'id-column', 'text-column', 'rating-column'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    prepare(args.csv, args.ids, args.output, args.id_column, args.text_column, args.rating_column)
