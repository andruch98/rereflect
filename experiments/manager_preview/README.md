# Test the manager preview on your Mac

Start Docker Desktop and leave your usual BoomSay preview running for the first launch. Extract the entire PR ZIP, open Terminal in its source folder, and run:

```sh
python3 experiments/manager_preview/start.py
```

The launcher takes a read-only snapshot of your Mac database, verifies the survey and feedback counts against that exact snapshot, then starts the PR in a separate database and Docker project.

Open **http://127.0.0.1:53114/agent-settings**. Sign in with your usual Mac preview password for `dashboard-preview@example.com`. Only the copy gives this account manager access for Lake House Apartments. The usual dashboard at port 53004 and your OVH deployment stay separate.

**Start here**

1. Walk through Review Responses. Choose automatic approval, keep the safety hold, and compare the two sample replies before you confirm.
2. In Surveys, adjust one invitation’s timing. Confirm, then reopen Current settings and edit a single choice.
3. Open Surveys and inspect a response needing review. Then open Reviews and draft or approve one response.

The private preview uses local reply examples and simulates survey emails. It has no provider keys or outbound publishing connection. Stored reviews, survey answers and prior Ask Genius chats come from the snapshot. New model-backed Ask Genius answers and live AI drafting require a connected provider outside this preview.

**Stop or resume**

```sh
python3 experiments/manager_preview/start.py stop
```

Run the start command again to resume with your test edits. The launcher never replaces an initialized copy with a fresh import. Keep the extracted source folder on your Mac while using the preview.

**If startup stops**

- Docker Desktop must use a local context. First launch needs your original preview’s five containers and their local images. The source PostgreSQL container must be running.
- If port 53114 belongs to another app, the launcher stops. It never stops other applications to free the port.
- A failed restore can be retried with the same start command. The restore is one PostgreSQL transaction. A completed restore with different counts stops for inspection.
- If the local website is still compiling, rerun the same start command. A successful launch checks the website, login page, and protected settings API. Your next check is a normal sign-in.

Private configuration and the snapshot live under `~/Library/Application Support/BoomSay/manager-preview-v1`. These local files contain account and survey data. Keep them on your Mac. The reusable ZIP contains source code only.
