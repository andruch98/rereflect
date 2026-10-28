# Preview setup packaging

These reviewed sources configure only the existing isolated Mac preview. The user
runs install-openai.sh from that preview folder. No provider request is automatic.

For a downloadable package, copy these scripts and metadata, then generate
rereflect-app-source.tar.gz from the final committed source with git archive.
Generate update.json alongside it with commit, bases (supported prior source
commits, including 66e7ec4c61a147eced6eed05be45207725253ba6), and the archive sha256.
The original supported bases are 7519b93674d40f87e9915ae458ac503cd69e1d2d and
e19eb96cf0a19802d9bcc569c643845e36417032. Do not commit the generated archive,
update.json, private records, environment files, keys or test-run artifacts here.

Run the packaged verification/test_setup.py with BOOMSAY_SETUP_BASELINE pointing
to a copy of the original delivered preview skeleton. The test copies the actual
public baseline files and saved review bytes, but constructs only synthetic
credentials. No existing runtime.env or login credentials are copied or read.
Include the test result and its limitations in the private downloadable package.

The Docker runtime and real provider remain unverified by offline tests.
