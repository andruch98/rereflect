"""Exercise the actual Mac runner without Docker, credentials or email."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).resolve().parents[2] / 'email_preview/test-survey.sh'
TYPES = ('move_in_completed', 'maintenance_completed', 'lease_month_3',
         'lease_month_6', 'lease_month_9', 'lease_renewed', 'move_out_completed')


class RunnerTests(unittest.TestCase):
    def test_all_types_use_unique_valid_ids_and_preserve_event_type(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            home = root / 'home'
            (home / 'Downloads/boomsay-dashboard-preview').mkdir(parents=True)
            binary = root / 'bin'
            binary.mkdir()
            capture = root / 'capture.json'
            python = binary / 'python3'
            python.write_text('#!' + sys.executable + '\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["CAPTURE"]).write_text(json.dumps(sys.argv[1:]))\n')
            python.chmod(0o700)
            env = {**os.environ, 'HOME': str(home), 'PATH': str(binary) + os.pathsep + os.environ['PATH'], 'CAPTURE': str(capture)}
            ids = []
            for event in TYPES:
                with self.subTest(event=event):
                    subprocess.run(['bash', str(RUNNER), event], env=env, check=True)
                    args = json.loads(capture.read_text())
                    self.assertEqual(args[1], 'send')
                    self.assertEqual(args[args.index('--event-type') + 1], event)
                    identity = args[args.index('--test-id') + 1]
                    self.assertIsNotNone(re.fullmatch(r'[a-z0-9-]{1,40}', identity))
                    ids.append(identity)
            self.assertEqual(len(set(ids)), len(TYPES))

    def test_unknown_type_is_rejected_before_invocation(self):
        result = subprocess.run(['bash', str(RUNNER), 'unknown'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Choose one', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
