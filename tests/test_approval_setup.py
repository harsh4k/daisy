"""Hook setup adds only Daisy, preserves policies and never fabricates trust."""
import json
from pathlib import Path
import tempfile
import unittest


class ApprovalSetupTests(unittest.TestCase):
    def test_merge_keeps_other_hooks_and_is_idempotent(self):
        from approval_setup import hook_entry, merge_hooks
        original = {'permissions': {'deny': ['Bash(rm *)']}, 'hooks': {
            'PermissionRequest': [{'hooks': [{'type': 'command', 'command': 'existing-policy'}]}],
            'PreToolUse': [{'hooks': [{'command': 'guard'}]}]}}
        entry = hook_entry('codex', Path('X:/Apps/DynamicIsland'))
        merged = merge_hooks(original, entry)
        self.assertEqual(merged['permissions'], original['permissions'])
        self.assertEqual(merged['hooks']['PreToolUse'], original['hooks']['PreToolUse'])
        self.assertEqual(merged['hooks']['PermissionRequest'][0], original['hooks']['PermissionRequest'][0])
        self.assertEqual(merge_hooks(merged, entry), merged)
        self.assertEqual(len(original['hooks']['PermissionRequest']), 1)
        self.assertNotIn('trusted_hash', json.dumps(merged))
        self.assertNotIn('bypass', json.dumps(merged))

    def test_bad_configuration_is_never_overwritten_and_backup_is_exact(self):
        from approval_setup import install_hook
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'settings.json'
            target.write_bytes(b'{broken')
            with self.assertRaises(ValueError):
                install_hook(target, {'type': 'command', 'command': 'fixture'})
            self.assertEqual(target.read_bytes(), b'{broken')
            original = b'{"keep": "original"}\n'
            target.write_bytes(original)
            backup = install_hook(target, {'type': 'command', 'command': 'fixture'})
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(json.loads(target.read_bytes())['keep'], 'original')

    def test_invalid_nested_handlers_are_rejected_without_writes(self):
        from approval_setup import install_hook
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'hooks.json'
            for handlers in ('invalid', None, [1], [{'command': 'existing'}, None]):
                original = json.dumps({'hooks': {'PermissionRequest': [{'hooks': handlers}]}}).encode()
                target.write_bytes(original)
                with self.assertRaises(ValueError):
                    install_hook(target, {'type': 'command', 'command': 'fixture'})
                self.assertEqual(target.read_bytes(), original)
            self.assertEqual(list(Path(folder).glob('*.daisy-backup-*')), [])
