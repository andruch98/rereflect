"""Offline launch-contract checks. Run from this directory: python3 -m unittest."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import start as launcher


class LauncherTests(unittest.TestCase):
    def configuration(self):
        return {'owner': 'private-marker', 'password': 'example-only', 'jwt': 'example-only',
                'encryption': 'example-only', 'images': {service: {'image': service, 'platform': 'linux/amd64'}
                for service in ('postgres', 'redis', 'api', 'web', 'gateway')}}

    def test_compose_is_loopback_only_and_uses_branch_source(self):
        doc = launcher.compose_document(self.configuration(), 9)
        self.assertNotEqual(doc['name'], launcher.SOURCE)
        services = doc['services']
        self.assertEqual(services['gateway']['ports'], ['127.0.0.1:53114:3000'])
        self.assertTrue(doc['networks']['private']['internal'])
        for service in ('postgres', 'redis', 'api', 'web'):
            self.assertNotIn('ports', services[service])
            self.assertEqual(services[service]['networks'], ['private'])
            self.assertEqual(services[service]['pull_policy'], 'never')
        env = services['api']['environment']
        self.assertEqual(env['ASK_GENIUS_ENABLED'], 'false')
        self.assertEqual(env['BOOMSAY_SURVEY_SIMULATION'], 'true')
        self.assertEqual(env['SURVEY_PUBLIC_BASE_URL'], launcher.URL)
        self.assertEqual(env['BOOMSAY_PREVIEW_ORGANIZATION_ID'], '9')
        self.assertEqual(services['web']['environment']['NEXT_PUBLIC_API_URL'], launcher.URL)
        self.assertTrue(all(m['read_only'] for s in ('api', 'web') for m in services[s]['volumes']))
        self.assertTrue(any(m['target'].endswith('frontend-web/app') for m in services['web']['volumes']))

    def test_export_uses_same_read_only_source_snapshot_for_counts_and_dump(self):
        process = MagicMock()
        process.stdin = MagicMock()
        process.stdout = io.BytesIO(b'00000123-1|17|6|9\nsnapshot_done\n')
        process.__enter__.return_value = process

        def run(args, **kwargs):
            if 'pg_dump' not in args:
                return 'original_user'
            self.assertEqual(args[:3], ['docker', 'exec', launcher.SOURCE + '-postgres-1'])
            self.assertEqual(args[args.index('--snapshot') + 1], '00000123-1')
            self.assertEqual(args[-1], launcher.SOURCE_DB)
            self.assertIn('--no-owner', args)
            self.assertIn('--no-acl', args)
            kwargs['stdout'].write(b'example archive')

        with tempfile.TemporaryDirectory() as temp:
            with (patch.object(launcher, 'STATE', Path(temp)), patch.object(launcher.subprocess, 'Popen', return_value=process),
                  patch.object(launcher.select, 'select', return_value=([process.stdout], [], [])),
                  patch.object(launcher, 'command', side_effect=run),
                  patch.object(launcher, 'source_container', return_value=launcher.SOURCE + '-postgres-1')):
                metadata = launcher.snapshot()
                self.assertEqual(metadata, {'surveys': 17, 'reviews': 6, 'organization': 9})
                self.assertEqual((Path(temp) / 'source.dump').read_bytes(), b'example archive')
                self.assertIn(b'SELECT pg_export_snapshot()', process.stdin.write.call_args.args[0])
                self.assertIn(b'READ ONLY', process.stdin.write.call_args.args[0])
                self.assertEqual(launcher.snapshot(), metadata)

    def test_rejects_existing_foreign_volume(self):
        with patch.object(launcher, 'command', side_effect=['', launcher.PROJECT + '_data', 'foreign']):
            with self.assertRaisesRegex(launcher.PreviewError, 'database volume'):
                launcher.check_ownership('ours')

    def test_completed_database_is_never_restored_or_granted_again(self):
        with patch.object(launcher, 'sql', return_value='private-marker') as sql, patch.object(launcher, 'command') as cmd:
            launcher.prepare_database(self.configuration(), {})
            self.assertEqual(sql.call_count, 1)
            cmd.assert_not_called()

    def test_source_counts_guard_existing_work(self):
        with patch.object(launcher, 'sql', side_effect=['', '10', '5|4']) as sql, patch.object(launcher, 'command') as cmd:
            with self.assertRaisesRegex(launcher.PreviewError, 'counts differ'):
                launcher.prepare_database(self.configuration(), {'surveys': 17, 'reviews': 6, 'organization': 7})
            self.assertEqual(sql.call_count, 3)
            cmd.assert_not_called()

    def test_first_restore_commits_as_unit_and_limits_grant_to_cloned_account(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'source.dump').write_bytes(b'fake test archive')
            with (patch.object(launcher, 'STATE', Path(temp)), patch.object(launcher, 'command') as cmd,
                  patch.object(launcher, 'sql', side_effect=['', '0', '17|6', '9', '']) as sql):
                launcher.prepare_database(self.configuration(), {'surveys': 17, 'reviews': 6, 'organization': 9})
                restore = cmd.call_args.args[0]
                self.assertIn('-1', restore)
                self.assertIn('--no-acl', restore)
                self.assertIn('--no-owner', restore)
                self.assertEqual(restore[-1], launcher.DATABASE)
                final_sql = sql.call_args.args[0]
                self.assertIn(launcher.MANAGER, final_sql)
                self.assertIn(launcher.COMMUNITY, final_sql)
                self.assertIn('u.organization_id=9', final_sql)
                self.assertIn(launcher.URL + '/survey/', final_sql)


if __name__ == '__main__':
    unittest.main()
