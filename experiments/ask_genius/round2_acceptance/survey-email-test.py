"""Run on the Mac, inside the existing preview directory. No stored API keys."""
import argparse
import getpass
import json
from pathlib import Path
import subprocess
import sys
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def backend(action, test_id, event_type='maintenance_completed'):
    result = subprocess.run(['docker', 'compose', '-f', 'compose.json', 'exec', '-T', 'api',
        'python', '-m', 'src.survey_email_preview', action, test_id, '--event-type', event_type], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'The preview command failed. Nothing sent.')
    return json.loads(result.stdout)


def send_once(test_id, key, call=backend, opener=None):
    data = call('reserve', test_id)
    request = urllib.request.Request('https://api.resend.com/emails',
        data=json.dumps(data['payload']).encode(), method='POST', headers={
            'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
            'Idempotency-Key': data['idempotency_key'], 'User-Agent': 'BoomSay-local-email-test/1'})
    try:
        opener = opener or urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=30) as response:
            receipt = json.load(response)
            if response.status != 200 or not isinstance(receipt.get('id'), str) or not receipt['id']:
                raise ValueError('No provider receipt')
    except Exception:
        try:
            call('failed', test_id)
        except Exception:
            pass  # Reservation still blocks repeats even if recording failed.
        raise ValueError('Sending failed or its outcome is uncertain. Do not start another test yet; check Resend Emails. Repeating this test is blocked.') from None
    try:
        call('accepted', test_id)
    except Exception:
        return 'Resend accepted the email, but the preview status could not be updated. Do not resend. Check your inbox and Resend Emails.'
    return 'Resend accepted the email. Check your Gmail inbox and spam folder; acceptance is not proof of delivery.'


def main():
    parser = argparse.ArgumentParser(description='One email per named fictional survey test.')
    parser.add_argument('action', choices=['prepare', 'send'])
    parser.add_argument('--test-id', default='first-test', help='Use a DIFFERENT name only to deliberately start another test.')
    parser.add_argument('--event-type', choices=['move_in_completed', 'maintenance_completed', 'lease_month_3',
        'lease_month_6', 'lease_month_9', 'lease_renewed', 'move_out_completed'], default='maintenance_completed')
    args = parser.parse_args()
    if not Path('compose.json').is_file() or not Path('private').is_dir():
        raise SystemExit('Run from ~/Downloads/boomsay-dashboard-preview.')
    try:
        def selected_backend(action, test_id):
            return backend(action, test_id, args.event_type)
        preview = selected_backend('prepare', args.test_id)
        payload = preview['payload']
        print('From:', payload['from'], '\nTo:', ', '.join(payload['to']))
        print('Subject:', payload['subject'], '\n\n' + payload['text'])
        print('\nStatus:', preview['status'])
        if args.action == 'prepare':
            print('Prepared only. No email sent. Open links on this Mac while Docker is running.')
            return
        if preview['status'] != 'simulated':
            raise ValueError('This test is suppressed or already attempted. No duplicate sent.')
        if not sys.stdin.isatty():
            raise ValueError('Run interactively in Terminal so the API key stays hidden.')
        if input('\nType SEND to send this one email: ') != 'SEND':
            print('Cancelled. Nothing sent.')
            return
        key = getpass.getpass('Paste Resend API key (hidden, not saved): ').strip()
        if not key.startswith('re_') or any(c.isspace() for c in key):
            raise ValueError('Key format not recognized. Nothing sent.')
        print(send_once(args.test_id, key, call=selected_backend))
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == '__main__':
    main()
