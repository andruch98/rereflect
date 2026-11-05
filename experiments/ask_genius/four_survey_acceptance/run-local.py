"""Mac launcher; Python standard library only. Never install or edit the local preview."""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED


def report(events, questions, source, exit_code):
    preflight = next((e for e in events if e.get('kind') == 'preflight'), {})
    lines = ['# Ask Genius: four new survey submissions', '',
        'PR #12 application commit: ' + source['application_commit'],
        'Software run: ' + ('completed' if exit_code == 0 else 'stopped / incomplete'),
        'Human factual assessment: pending. Passing JSON/source validation does not prove accuracy.', '',
        'Only the four named November 5 submissions were copied into an isolated diagnostic database. '
        'The actual PR12 question route ran there with the existing configured AI. '
        'This does not install PR12, add chats to your dashboard, or test browser sharing. '
        'There is no old-version baseline for these four records.', '',
        '## Questions and answers', '']
    for index, (group, question) in enumerate(questions, 1):
        event = next((e for e in events if e.get('kind') == 'result' and e['index'] == index), None)
        lines += [f'### {index}. {question}', '', 'Chat: ' + group, '']
        if event:
            response = event.get('response') or {}
            lines += [response.get('answer', 'No accepted answer; see failure below.'), '',
                'Status: ' + event['status'],
                'Input/output tokens: ' + str(event['tokens_in']) + '/' + str(event['tokens_out']),
                'Cost: unavailable.', 'Human assessment: pending.', '']
            if event.get('failure'):
                lines += ['Failure: ' + json.dumps(event['failure'], ensure_ascii=False), '']
        else:
            lines += ['Not run / no response captured.', '']
    lines += ['## Original submitted answers', '']
    for record in preflight.get('evidence', {}).get('surveys', []):
        lines += ['### ' + record['survey_type_label'] + ' — ' + record['survey_id'],
                  'Submitted: ' + str(record['submitted_at']), '']
        for question in record['questions']:
            value = question.get('answer_label')
            if value is None or value == '':
                value = '(No answer/comment provided)'
            lines += [question['text'], '', str(value), '']
    lines += ['## Review checklist', '',
        '- Count exactly 4: maintenance 2, pre-renewal 1, move-in 1.',
        '- Compare every rating, resolution status, reason and quotation with the original answers above.',
        '- Flag low individual scores even if the overall rating is positive.',
        '- Keep resolved, partially resolved, unresolved and unknown distinct.',
        '- Mention any reported safety concern without inventing one.',
        '- Explain mixed feedback fairly; do not assume rent value, delays or causes absent from the data.',
        '- Treat the historical example bank as guidance, not evidence about these four submissions.',
        '- Follow-ups must refer to the correct survey; ask for clarification if ambiguous.',
        '- Compare questions 8/13 and 11/14 for facts lost through conversation history.',
        '- Separate factual errors and broken workflows from optional wording polish.', '',
        'Complete actual model messages, raw outputs, tokens, software rejection reasons and failures '
        'are in events.jsonl. The source package is included for reproducibility. '
        'This private report includes survey context and resident comments. API keys and live survey links are not exported.']
    return '\n'.join(lines) + '\n'


def main():
    package = Path(__file__).resolve().parent
    preview = Path.home() / 'Downloads/boomsay-dashboard-preview'
    if not (preview / 'compose.json').is_file() or not shutil.which('docker'):
        sys.exit('Start the existing BoomSay preview in Docker Desktop first. No test requests sent.')
    hashes = json.loads((package / 'checksums.json').read_text())
    for name in ('bootstrap.py', 'pr12-source.zip', 'questions.json', 'source.json'):
        if hashlib.sha256((package / name).read_bytes()).hexdigest() != hashes[name]:
            sys.exit('Package checksum mismatch. No test requests sent.')
    if (package / 'TEST-STARTED.txt').exists():
        sys.exit('This package has already been started. Review its saved results before another paid run.')
    ready = subprocess.run(['docker', 'compose', '-f', 'compose.json', 'exec', '-T', 'api',
                            'python', '-c', 'print("ready")'], cwd=preview, capture_output=True, text=True)
    if ready.returncode != 0 or ready.stdout.strip() != 'ready':
        sys.exit('The local preview API is not running. Start it with bash start-local.sh, then try again. Nothing sent.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    results = package / ('results-' + stamp)
    results.mkdir(mode=0o700)
    questions = json.loads((package / 'questions.json').read_text())
    source = json.loads((package / 'source.json').read_text())
    for name in ('source.json', 'questions.json', 'pr12-source.zip', 'bootstrap.py', 'run-local.py', 'checksums.json'):
        shutil.copyfile(package / name, results / name)
    (package / 'TEST-STARTED.txt').write_text(str(results) + '\n')
    events = []
    print('Testing 14 questions against exactly 4 new submissions using PR #12.', flush=True)
    print('Your existing AI connection is used; normal model charges apply. No automatic retries.', flush=True)
    print('Answers will appear below. Your preview and saved records stay unchanged.\n', flush=True)
    payload = {'archive': base64.b64encode((package / 'pr12-source.zip').read_bytes()).decode(),
               'sha256': hashes['pr12-source.zip']}
    command = ['docker', 'compose', '-f', 'compose.json', 'exec', '-T', 'api', 'python', '-c',
               (package / 'bootstrap.py').read_text()]
    code = 1
    try:
        with tempfile.TemporaryFile(mode='w+') as stdin, (results / 'events.jsonl').open('w') as capture:
            json.dump(payload, stdin); stdin.seek(0)
            process = subprocess.Popen(command, cwd=preview, stdin=stdin, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, text=True)
            try:
                for line in process.stdout:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    capture.write(json.dumps(event, ensure_ascii=False) + '\n'); capture.flush()
                    events.append(event)
                    if event.get('kind') == 'attempt':
                        print(f"{event['index']}/14. {event['question']}", flush=True)
                    elif event.get('kind') == 'result':
                        print((event.get('response') or {}).get('answer') or 'Stopped: answer failed; see report.', flush=True)
                        print('', flush=True)
                    elif event.get('kind') == 'preflight_failure':
                        print(event['reason'], flush=True)
                code = process.wait()
            except KeyboardInterrupt:
                process.terminate(); process.wait()
                events.append({'kind': 'interrupted', 'reason': 'User stopped the local launcher; last request may be incomplete.'})
                capture.write(json.dumps(events[-1]) + '\n')
    finally:
        complete = any(e.get('kind') == 'complete' for e in events)
        code = code or (0 if complete else 1)
        (results / 'Ask-Genius-Results.md').write_text(report(events, questions, source, code))
        archive = package / ('Ask-Genius-Results-' + stamp + '.zip')
        with ZipFile(archive, 'x', ZIP_DEFLATED) as bundle:
            for item in sorted(results.iterdir()):
                bundle.write(item, results.name + '/' + item.name)
        print('\nSend this ZIP back for review:\n' + str(archive), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
