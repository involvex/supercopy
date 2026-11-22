# GEMINI.md

## Project Overview
SuperCopy is a Windows CLI-first file utility for multi-threaded copying and archive unpacking, with an optional GUI.

- **Purpose:** Fast copy/unpack with scripting features (filters, dry-run, JSON, conflict policy).
- **Core Technology:** Python 3.9+
- **GUI Framework:** `customtkinter` (lazy-imported; optional).
- **CLI Engine:** `argparse` + `tqdm`; Bun/Node shim in `bin/supercopy.js`.
- **Copy Engine:** `ThreadPoolExecutor`, long paths, metadata preserve, retries, mirror/move.
- **Unpack Engine:** `zipfile`, `tarfile`, `py7zr`, external `7z.exe` for RAR.
- **Distribution:** `@involvex/supercopy` (npm/Bun) + NSIS installer.

## Directory Structure
- `supercopy.py`: CLI + engines + lazy GUI.
- `bin/supercopy.js`: Bun/Node wrapper → `dist/SuperCopy.exe` (fails fast if missing).
- `tests/test_cli.py`: pytest coverage for CLI behavior.
- `build.bat`: `--nopause`, `--cli` (slim build).
- `.npmignore`: publishes `dist/SuperCopy.exe` despite gitignore.
- `package.json`, `requirements.txt`, `installer.nsi`.

## Building and Running

```shell
bun run build          # full
bun run build:cli      # slim CLI
python supercopy.py C:\src D:\dst --quiet
python -m pytest tests -q
```

## Development Conventions
- Prefer CLI reliability (exit codes, stderr errors) over GUI polish.
- Do not load GUI modules on the CLI import path.
- Keep `.npmignore` aligned so published installs include the exe.

## TODO / Future Improvements
- [x] Automated unit tests (`tests/`, `npm test`)
- [ ] Add linting for Python (`ruff` or `black`)
- [ ] Bundle or document shipping `7z.exe` for RAR
