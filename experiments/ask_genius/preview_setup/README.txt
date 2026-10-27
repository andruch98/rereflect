BOOMSAY ASK GENIUS — OPENAI GPT-4.1 MINI SETUP

This update includes the Ask Genius application, centered review table and local
OpenAI setup. It works directly from your existing saved-review preview; you do
not need to install the earlier Ask Genius ZIP first.

ONE COMMAND ON YOUR MAC
1. Start Docker Desktop and unzip this folder. Keep your existing preview folder.
2. Open Terminal in the existing boomsay-dashboard-preview folder.
3. Type bash followed by a space, drag install-openai.sh from THIS update folder
   into Terminal, and press Enter.
4. Paste your OpenAI API key at the hidden prompt and press Enter. Characters
   will not appear. Never paste the key into this chat. Use your OpenAI API key,
   not your ChatGPT password; API usage is billed separately.
5. When startup finishes, visit http://127.0.0.1:53004/ask-genius and use your
   existing preview login. A submitted question makes one paid model request.

The command is equivalent to:
  bash /path/to/boomsay-ask-genius-openai-setup/install-openai.sh
Run it from the EXISTING preview folder, not from the downloaded update folder.
You can also pass the existing preview folder as the command's second argument.

The script validates this exact private preview, updates the app if needed,
saves a separate ASK_GENIUS_API_KEY with private file permissions, selects
OpenAI gpt-4.1-mini, and starts the preview. Existing login, saved original
reviews/analysis, database volume and blocked analysis ledger are retained.
No worker is added or started. There is no model call merely to save the key,
build/start the app, log in, or check configuration. No automatic paid test runs.

If you have already installed this update, rerunning is safe. Press Enter at
the hidden prompt to keep the existing Ask Genius key, or paste a replacement.
Canceling or entering an invalid key leaves application/config files unchanged.
The script never borrows an OPENAI_API_KEY from another project or environment.
Run one installer at a time; simultaneous setup commands are unsupported.

NETWORK AND SECRET HANDLING
Only the API application service gains a normal Docker outbound network so it
can contact OpenAI. This is not a domain-restricted firewall. Database, Redis
and web stay on the internal network. The pre-existing loopback-only gateway
keeps its existing network. Both browser ports remain local to your Mac.
The official OpenAI URL is explicit in the application; no endpoint is inferred
from production settings. The prompt sends the six saved reviews, saved analysis,
calculated aggregates, question and bounded conversation history to OpenAI.

The key is stored in private/runtime.env and loaded by the API container.
People with access to your Mac account or Docker can access container secrets.
Do not share that file, inspect/dump container environments, or paste Docker
Compose's resolved configuration into chat. A Docker build-context allowlist
excludes private files, Compose configuration and source backups from images.
No credentials are included in this update ZIP or its tests. The source backup
does not copy runtime.env or login files. Existing scripts and all checksums are
validated before changes; unexpected layouts fail closed instead of being reset.

VERIFICATION AND LIMITS
Local tests use synthetic keys, disposable folders and no provider/network calls.
They verify private-file preservation, source update/repeat, network boundaries,
hidden/canceled input, invalid inputs/layouts, symlinks, checksum checks and rollback.
See verification/setup-tests.log and verification/SETUP_TESTS.txt.
Docker is unavailable in the preparation workspace. Full Docker startup, actual
Mac terminal behavior, OpenAI connectivity/key validity, model availability,
live answer quality and PostgreSQL advisory locks remain unverified here.
Startup checks all six original records and authenticated configuration locally.
The configuration check does not contact OpenAI or establish answer quality.

If startup fails after setup succeeds, keep the folder/data and rerun the same
command. Do not delete the database volume. Ordinary write failures roll back
configuration; a forced shutdown/power loss across several files is not a full
filesystem transaction and may require recovery from the preserved source backup.

MODEL LIFECYCLE
Your selected model is exactly gpt-4.1-mini. No automatic model substitution is
enabled. OpenAI's deprecations notice currently lists January 14, 2027 as its
shutdown date: https://developers.openai.com/api/docs/deprecations
After that, a separately approved model change will be needed. This is a pilot
configuration, not a production deployment. Nothing is merged or deployed by
running this local update.
