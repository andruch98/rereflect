"""Read local config status after startup. Never calls the model provider."""
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

root = Path(sys.argv[1]).resolve()
base = 'http://127.0.0.1:58004'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    login = json.loads((root / 'private/local-login.json').read_text())
    request = urllib.request.Request(base + '/api/v1/auth/login', data=json.dumps(login).encode(),
                                     headers={'Content-Type': 'application/json'})
    token = json.load(opener.open(request, timeout=15))['access_token']
    request = urllib.request.Request(base + '/api/v1/ask-genius/status',
                                     headers={'Authorization': 'Bearer ' + token})
    status = json.load(opener.open(request, timeout=15))
    if status.get('ready') is not True:
        raise ValueError('Not configured')
except (OSError, ValueError, KeyError, TypeError):
    raise SystemExit('The local Ask Genius configuration check did not pass. Keep your preview and retry startup; no model request was made.') from None
print('Authenticated local Ask Genius configuration check passed. This does not test OpenAI connectivity or key validity.')
