# Daisy

## Project

Personal Windows desktop overlay built with Python 3.12, PyQt6, QtAwesome,
psutil, Pillow, requests and winsdk. Repository: https://github.com/harsh4k/daisy.

## Commands

- Install dependencies: `python -m pip install -r requirements.txt`
- Run: `python main.py`
- Tests: `python -m unittest discover -s tests`
- Build: install `requirements-build.txt`, then `powershell -File build_exe.ps1`
- Required gate: `node ~/.agents/gates/verify.mjs`

## Layout and boundaries

- `main.py` owns the overlay; `desktop_entry.py` owns app startup/shutdown.
- `app_runtime.py` owns the instance lock and opt-in Windows startup.
- `install.ps1` and `uninstall.ps1` manage per-user installation.
- `.github/workflows/release.yml` tests and packages tagged releases.
- Read `design.md` before UI changes; tokens live in `ui_tokens.py` and
  `theme_tokens.py`.
- Settings live in `config.json` beside the executable. Preserve them on update.
- Installer tests in `tests/test_installer.py` mock Windows shortcuts, registry,
  and process enumeration; their file operations stay inside test directories.
- Avoid changing a real installation, startup entry, or shortcut in tests.

## Current evidence and issues

- Remote baseline e9795bf: 387 unit tests passed on Windows/Python 3.12.
- Published v1.0.10 matches remote main; both located installations match its
  executable hash.
- Installer regressions cover custom-directory uninstall and bundled notices.
- No deployment, database, CMS, payments, or Sentry configuration is declared.
- Several existing UI modules exceed 300 lines. Do not split unrelated modules
  during an installer change.
