# Backend CI dependency and test-isolation correction

Authorized 3 November 2026. No merge, deployment, Mac update, real email or model
request. Existing draft PR #6 continues to target the survey feature branch.

## Evidence and root causes

Run https://github.com/andruch98/rereflect/actions/runs/41740736434 at ae9e2283
finished with 5 failed, 5665 passed, 17 skipped and 1 xfailed backend tests.
Worker and frontend passed. The previous collection collision is resolved.

Four feedback-creation tests failed with Kombu VersionMismatch: redis-py >=6.1.0
required, installed 5.0.1. Backend requirements allowed Kombu 5.7.0 to resolve.
The worker already pins compatible Kombu 5.3.4. Pin the backend to that same
version; do not upgrade the whole queue stack or suppress dispatch errors.

The survey credential-preservation assertion failed only after JWT import tests.
The helper restored sys.modules but not the auth attribute on the parent package.
The survey test patched the temporary module, while initialize_demo imported the
original module. Restore both references, including the originally absent case.
No production login/password code changed and this is not evidence of user data
being overwritten.

## Bounded verification and stopping criteria

From services/backend-api using the isolated existing Python 3.12 environment:

1. Before fix: `JWT_SECRET=isolated-ci-test-secret DATABASE_URL=sqlite:// python
   -m pytest --noconftest tests/test_jwt_secret_required.py
   tests/surveys_offline/test_demo_guard.py::test_demo_init_retains_existing_credentials_and_creates_no_completed_fixture -q`
   reproduced 1 failed, 5 passed. See baseline-auth.txt.
2. Broker regression on Kombu 5.7.0: `python -m pytest --noconftest
   tests/test_broker_dependency_compatibility.py -q` reproduced VersionMismatch.
   Same test passes on 5.3.4. No Redis connection or task dispatch is made by this
   targeted version-gate test. See baseline-broker.txt and after-broker-final.txt.
3. Final: `JWT_SECRET=isolated-ci-test-secret DATABASE_URL=sqlite:// python -m
   pytest --confcutdir=tests/surveys_offline tests/test_broker_dependency_compatibility.py
   tests/test_jwt_secret_required.py tests/surveys_offline -q`: 42 passed, 4 skipped.
   The skips need PostgreSQL. See final-combined.txt for full test output.
4. Attempting the four actual feedback tests locally stopped loading root
   conftest because Authlib is absent. No authentication stubs or application
   bypasses were added. GitHub's fully provisioned suite is the integration gate.
   See after-feedback.txt. Full CI remains pending when this record is written.

An initial version of the new broker test used None as a channel object and
failed with AttributeError; corrected to an uninitialized real Channel with an
empty key prefix. That unsuccessful test attempt is retained in after-broker.txt.
All captured local command logs are in this directory. The upstream full job
log remains on GitHub; it is not duplicated here. No model inputs/outputs, token
usage or costs apply: zero model requests. Assessment: narrow failures reproduced
and repaired locally; do not claim a full integration pass before CI completes.

Stop after one full CI run if green. If another unrelated failure appears,
report it before expanding scope. Optional warnings/wording remain deferred.
