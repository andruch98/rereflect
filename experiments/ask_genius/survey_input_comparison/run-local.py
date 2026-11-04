"""Host launcher for a private four-question comparison package. Python standard library only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil


def main():
    package = Path(__file__).resolve().parent
    preview = Path.home() / 'Downloads/boomsay-dashboard-preview'
    if not (preview / 'compose.json').is_file():
        sys.exit('Existing local preview not found. No test requests sent.')
    if not shutil.which('docker'):
        sys.exit('Docker is not available. Start Docker Desktop first. Nothing sent.')
    manifest = json.loads((package / 'checksums.json').read_text())
    for name in ('replay.py', 'requests.json'):
        if hashlib.sha256((package / name).read_bytes()).hexdigest() != manifest[name]:
            sys.exit('Test package checksum mismatch. No test requests sent.')
    job = json.loads((package / 'requests.json').read_text())
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    results = package / ('results-' + stamp)
    results.mkdir()
    (results / 'requests.json').write_text(json.dumps(job, ensure_ascii=False, indent=2) + '\n')
    events = []
    print('Running at most four Ask Genius requests using your existing AI connection.', flush=True)
    print('Original chat history is held fixed; surveys and settings are not changed.', flush=True)
    command = ['docker', 'compose', '-f', 'compose.json', 'exec', '-T', 'api', 'python', '-c',
               (package / 'replay.py').read_text()]
    # A file supplies stdin, avoiding a pipe deadlock with the complete private job.
    with (results / 'requests.json').open() as stdin, (results / 'events.jsonl').open('w') as capture, \
            (results / 'runtime-stderr.txt').open('w') as stderr:
        process = subprocess.Popen(command, cwd=preview, stdin=stdin, stdout=subprocess.PIPE,
                                   stderr=stderr, text=True)
        for line in process.stdout:
            capture.write(line); capture.flush()
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(event)
            if event.get('kind') == 'attempt':
                print(f"Question {event['index']} of 4...", flush=True)
            elif event.get('kind') == 'result':
                print(event.get('answer') or 'Answer rejected; see the saved results.', flush=True)
            elif event.get('kind') == 'preflight_failure':
                print(event['reason'], flush=True)
            elif event.get('kind') == 'request_failure':
                print('Request failed: ' + event['error_type'] + '. No retry was made.', flush=True)
        process.wait()
    report = ['# BoomSay four-question comparison', '',
              'One new request per question, using the original frozen chat history. '
              'Baseline answers were captured earlier, not regenerated. '
              'Single-run differences do not prove causation or stable quality.', '',
              '## Results', '']
    for index, case in enumerate(job['cases'], 1):
        report += [f"### {index}. {case['question']}", '', '**Previous answer**', '',
                   case['baseline_response']['content'], '', '**Simplified-input answer**', '']
        result = next((e for e in events if e.get('kind') == 'result' and e['index'] == index), None)
        if result:
            report += [result.get('answer') or result['model_output'], '',
                       f"Software validation: {result['validation']}. "
                       f"Input/output tokens: {result['tokens_in']}/{result['tokens_out']}. Cost: unavailable.", '']
            if result.get('rejection_reason'):
                report += ['Rejection: ' + result['rejection_reason'], '']
        else:
            report += ['No model response captured for this case. See events.jsonl for errors/attempts.', '']
        report += ['Human factual assessment: pending.', '']
    report += ['## Review criteria', '', (package / 'REVIEW.txt').read_text(), '',
               'Complete inputs, raw model responses, validation results and failures: requests.json and events.jsonl. '
               'No API keys are included. Do not publish these private files.']
    (results / 'Comparison.md').write_text('\n'.join(report) + '\n')
    archive = package / ('BoomSay-Four-Question-Results-' + stamp + '.zip')
    from zipfile import ZipFile, ZIP_DEFLATED
    with ZipFile(archive, 'x', ZIP_DEFLATED) as bundle:
        for item in sorted(results.iterdir()):
            bundle.write(item, results.name + '/' + item.name)
    print('\nResults saved: ' + str(archive), flush=True)
    print('Send that ZIP back for review. Do not rerun yet.', flush=True)
    return process.returncode or (0 if any(e.get('kind') == 'complete' for e in events) else 1)


if __name__ == '__main__':
    sys.exit(main())
