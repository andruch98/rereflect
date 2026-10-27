# Layout updater packaging

Copy `update-preview.py` and `README.txt` beside a final source archive named
`rereflect-app-source.tar.gz`. Do not package credentials or an existing preview.
After the application commit is final, generate `update.json` with its exact
40-character `commit`, the archive's SHA-256 `sha256`, and these supported `bases`:

- `7519b93674d40f87e9915ae458ac503cd69e1d2d`
- `e19eb96cf0a19802d9bcc569c643845e36417032`
- `66e7ec4c61a147eced6eed05be45207725253ba6`
- `4c117094a132b3f395140026336b25ee220ca862`

The source archive and manifest are intentionally absent from this directory:
they must reflect the final reviewed application commit. The updater changes
only `app/`, its source archive, `SOURCE.txt` and the archive checksum. It never
reads `runtime.env` or login files, and does not run Docker or model requests.

Run offline tests against the original delivered public preview skeleton:

```bash
BOOMSAY_LAYOUT_BASELINE=/path/to/known-original-preview python3 verification/test_update.py
```

Tests replace private content with synthetic records and credentials. Include
their final log in the distributable `verification/` folder; do not include
temporary fixtures, Python caches, or the baseline's private records.
