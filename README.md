# SuperCopy

![Version](https://img.shields.io/badge/version-0.0.10-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

High-performance **Windows CLI** for multi-threaded file copy and archive unpacking. Optional GUI is available when launched with no arguments.

Designed to be faster and more scriptable than the default Windows copy dialog, with filters, dry-run, conflict policies, SHA-256 verify, and Bun/npm distribution.

---

## Features

- **Multi-threaded copy** with configurable workers and buffer size
- **Conflict policy:** `--on-conflict overwrite|skip|update`
- **Filters:** `--include` / `--exclude` globs
- **Dry-run, quiet, JSON** summaries for scripting
- **Metadata preservation** (mtime/attributes) by default
- **Retries** for locked / flaky I/O
- **Long-path** support via `\\?\` prefixes
- **Empty directories** recreated (disable with `--no-empty-dirs`)
- **Mirror / move** modes (`--mirror`, `--move`)
- **Archive unpack / list:** `.zip`, `.7z`, `.rar`, `.tar`, `.tar.gz`/`.tgz`, `.tar.bz2`, `.tar.xz`
- **Shell completions** for PowerShell, Bash, and Zsh (`supercopy` / `scpy`)
- **Optional GUI** when run with no arguments

---

## Installation

### Via Bun (recommended if you already use Bun)

```shell
bun add -g @involvex/supercopy
```

Or from a checkout:

```shell
bun run build        # full GUI+CLI exe
# bun run build:cli  # slimmer CLI-only exe
bun link
```

Requires a built `dist/SuperCopy.exe`. The Bun shim fails fast with build instructions if it is missing.

### Via npm

```shell
npm install -g @involvex/supercopy
```

Node.js >= 14 (or Bun >= 1) on Windows.

### Windows Installer

A Windows installer (`.exe`) is available from [GitHub Releases](https://github.com/involvex/supercopy/releases).

### Prerequisites for RAR Support

For `.rar` unpacking, install **7-Zip** and ensure `7z.exe` is on PATH: [7-Zip](https://www.7-zip.org/download.html).

---

## CLI usage

```shell
supercopy <source> <destination> [options]
scpy <source> <destination> [options]
```

### Copy examples

```shell
supercopy C:\data D:\backup
supercopy C:\data D:\backup --on-conflict skip
supercopy C:\data D:\backup --exclude "*.tmp" --exclude "node_modules"
supercopy C:\data D:\backup --dry-run --json
supercopy C:\data D:\backup --verify -w 8 -b 4194304
supercopy C:\data D:\backup --retries 3 --retry-wait 2
supercopy C:\data D:\backup --mirror --dry-run
```

### Unpack / list examples

```shell
supercopy archive.zip D:\out --unpack
supercopy archive.7z D:\out --unpack --password secret
supercopy archive.tar.gz D:\out --unpack
supercopy archive.zip --list
supercopy archive.zip --list --json
```

### Shell completions

```powershell
# PowerShell (current session)
supercopy completion powershell | Out-String | Invoke-Expression
```

```bash
source <(supercopy completion bash)
```

```zsh
source <(supercopy completion zsh)
```

---

## CLI options

| Option | Description | Default |
|--------|-------------|---------|
| `--unpack` | Extract archive to destination | off |
| `--list` | List archive contents (no extract) | off |
| `-w, --workers` | Concurrent copy threads | CPU count |
| `-b, --buffer` | I/O buffer bytes (must be >= 1) | 1048576 |
| `--verify` | SHA-256 verify after each copy | off |
| `--on-conflict` | `overwrite` / `skip` / `update` | overwrite |
| `--dry-run` | Do not write; show what would happen | off |
| `--exclude GLOB` | Exclude matching paths (repeatable) | |
| `--include GLOB` | Only include matching paths (repeatable) | |
| `-q, --quiet` | Suppress progress output | off |
| `--json` | Print JSON summary | off |
| `--retries N` | Retry transient I/O errors | 0 |
| `--retry-wait SEC` | Wait between retries | 1.0 |
| `--mirror` | Delete dest files not in source | off |
| `--move` | Move (copy then remove source) | off |
| `--no-empty-dirs` | Skip recreating empty directories | off |
| `--no-preserve-metadata` | Do not copy mtime/attributes | off |
| `--password` | Archive password (unpack/list) | |
| `-v, --version` | Show version | |
| `completion [shell]` | Emit completion script | powershell |

Exit codes: `0` success, `1` errors / failure, `2` invalid arguments (e.g. `--buffer 0`).

---

## GUI mode

Run `supercopy` with no arguments to open the desktop UI (browse source/destination, verify, unpack). Keyboard shortcuts: `Ctrl+O`, `Ctrl+D`, `Enter`.

---

## Build from source

```shell
git clone https://github.com/involvex/supercopy.git
cd supercopy
bun run build
# or: build.bat --nopause
# CLI-only slim build: bun run build:cli
```

Development without building:

```shell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
python supercopy.py C:\src D:\dst --quiet
python -m pytest tests -q
```

---

## Project structure

```
supercopy/
├── supercopy.py          # CLI + engines (+ lazy GUI)
├── bin/supercopy.js      # Bun/Node shim → dist/SuperCopy.exe
├── tests/test_cli.py     # CLI unit tests
├── package.json
├── requirements.txt
├── build.bat
├── installer.nsi
└── dist/SuperCopy.exe    # built artifact (published in npm package)
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `SuperCopy executable not found` | Run `bun run build` (or `npm run build`) so `dist/SuperCopy.exe` exists |
| `7z.exe not found` | Install 7-Zip and add it to PATH |
| `Buffer size must be >= 1` | Pass a positive `-b` value |
| Permission denied | Check ACLs or run elevated if needed |

---

## License

MIT License — see [LICENSE](LICENSE).

## Support

- [GitHub Issues](https://github.com/involvex/supercopy/issues)
- [Sponsors](https://github.com/sponsors/involvex)
