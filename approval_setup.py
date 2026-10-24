"""Explicit, reversible hook registration; never edits Codex trust or policies."""
import argparse
import copy
import json
import os
from pathlib import Path
import uuid


def hook_entry(provider, root):
    if provider not in ('codex', 'claude'):
        raise ValueError('Unsupported approval provider')
    root = Path(root).resolve()
    python = (root / '.venv/Scripts/python.exe').as_posix()
    helper = (root / 'permission_hook.py').as_posix()
    command = f'"{python}" "{helper}" {provider}'
    entry = {'type': 'command', 'command': command, 'timeout': 130}
    if provider == 'codex':
        # Codex uses PowerShell on this install; its Windows override needs &.
        quote = lambda value: "'" + value.replace("'", "''") + "'"
        entry['commandWindows'] = f'& {quote(python)} {quote(helper)} {provider}'
    return entry


def merge_hooks(original, entry):
    if not isinstance(original, dict):
        raise ValueError('Hook configuration must be an object')
    result = copy.deepcopy(original)
    hooks = result.setdefault('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('Invalid hook configuration')
    groups = hooks.setdefault('PermissionRequest', [])
    if not isinstance(groups, list) or any(not isinstance(group, dict) for group in groups):
        raise ValueError('Invalid PermissionRequest configuration')
    if any(not isinstance(group.get('hooks'), list) or
           any(not isinstance(handler, dict) for handler in group['hooks']) for group in groups):
        raise ValueError('Invalid PermissionRequest handlers')
    if any(entry == handler for group in groups for handler in group.get('hooks', [])):
        return result
    groups.append({'matcher': '*', 'hooks': [copy.deepcopy(entry)]})
    return result


def install_hook(target, entry):
    """Back up exact bytes, then replace atomically only if the source is unchanged."""
    target = Path(target)
    existed = target.exists()
    original = target.read_bytes() if existed else b'{}'
    try:
        updated = merge_hooks(json.loads(original.decode('utf-8-sig')), entry)
    except (UnicodeError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid hook configuration; original preserved') from error
    if updated == json.loads(original.decode('utf-8-sig')):
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    stamp = uuid.uuid4().hex
    backup = target.with_name(target.name + '.daisy-backup-' + stamp)
    with backup.open('xb') as stream:
        stream.write(original)
    temporary = target.with_name(target.name + '.daisy-update-' + stamp)
    try:
        with temporary.open('xb') as stream:
            stream.write((json.dumps(updated, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        if target.exists() != existed or (existed and target.read_bytes() != original):
            raise OSError('Hook configuration changed during setup; original preserved')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--install', action='store_true', help='Back up and add the hooks')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.install:
        for relative in ('.venv/Scripts/python.exe', 'permission_hook.py', 'dist/Daisy.exe'):
            if not (root / relative).is_file():
                raise ValueError('Install and verify Daisy before registering its hooks')
    destinations = {'codex': Path.home() / '.codex/hooks.json',
                    'claude': Path.home() / '.claude/settings.json'}
    for provider, target in destinations.items():
        entry = hook_entry(provider, root)
        if args.install:
            backup = install_hook(target, entry)
            print(f'{provider}: registered; backup {backup}' if backup else f'{provider}: already registered')
        else:
            print(json.dumps({provider: entry}, indent=2))
    print('Codex: review and trust the Daisy hook in /hooks; never bypass trust.')
    print('Reload/new sessions may be required. Claude Code only; native prompts remain the fallback.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
