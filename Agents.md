# Agents.md - SuperCopy Development Guide

This file provides comprehensive instructions for AI agents working on the SuperCopy project.

---

## 1. Project Overview

**SuperCopy** is a high-performance file utility for Windows that provides:

- A CLI-first copy/unpack tool (primary use case), with an optional GUI
- Multi-threaded file copying with filters, dry-run, conflict policy, retries
- Archive unpack/list for `.zip`, `.7z`, `.rar`, and tar variants
- Dual progress bars and optional SHA-256 verification
- Bun/npm shim launching `dist/SuperCopy.exe`

### Tech Stack

| Component       | Technology                                          |
| --------------- | --------------------------------------------------- |
| GUI Framework   | Python (`customtkinter`, `tkinter`) — lazy-imported |
| CLI Wrapper     | Bun/Node (`bin/supercopy.js`)                       |
| Build Tool      | PyInstaller                                         |
| Archive Support | `py7zr`, `zipfile`, `tarfile`, 7-Zip (RAR)          |
| Package Manager | npm / Bun, pip (Python)                             |

---

## 2. Useful Commands

### Development Commands

```bash
# CLI in development
python supercopy.py C:\src D:\dst --quiet

# Via Bun/npm shim (needs dist/SuperCopy.exe)
bun run build
bun link
supercopy C:\src D:\dst --verify

# Tests
python -m pytest tests -q
```

### Build Commands

```bash
# Full build (GUI + CLI), no pause — good for Bun/npm
bun run build
# or: build.bat --nopause

# Slim CLI-only exe (excludes customtkinter)
bun run build:cli
```

### npm / Bun Commands

```bash
bun add -g @involvex/supercopy
npm publish --access public
npm run release
```

---

## 3. Project Structure

```
supercopy/
├── supercopy.py          # CLI + engines (+ lazy GUI)
├── bin/supercopy.js      # Bun/Node shim → dist/SuperCopy.exe
├── tests/test_cli.py     # CLI unit tests
├── package.json
├── requirements.txt
├── build.bat             # --nopause / --cli supported
├── .npmignore            # ensures dist/SuperCopy.exe is published
├── installer.nsi
├── README.md
└── dist/SuperCopy.exe    # built artifact
```

---

## 4. Best Practices

### Python Development

1. **Virtual Environment**: Always use a virtual environment (`.venv`) for development

   ```bash
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

2. **Dependencies**: Add new dependencies to `requirements.txt`

   ```text
   customtkinter
   tqdm
   pyinstaller
   py7zr
   ```

3. **Error Handling**: Use try-except blocks for file operations and provide meaningful error messages

4. **Threading**: The copy engine uses `ThreadPoolExecutor` - ensure thread-safe progress updates

### GUI Development

1. **CustomTkinter**: Use `customtkinter` for modern UI styling, fallback to `tkinter` for basic components

2. **Thread Safety**: GUI updates must happen on the main thread; use `after()` or callbacks for progress updates

3. **Progress Bars**: Implement dual progress bars (file count + total size)

### Build & Release

1. **PyInstaller**: Use `--onefile` option for single executable output

2. **Version Management**: Update version in `package.json` before publishing

3. **Testing**: Test the built executable before publishing to npm

---

## 5. Guidelines

### CLI Behavior

The application supports two modes:

1. **GUI Mode** (default): Launch without arguments

   ```bash
   supercopy
   ```

2. **CLI Mode**: Process arguments automatically

   ```bash
   supercopy <source> <destination> [options]
   ```

### CLI Options

| Option                        | Description                     |
| ----------------------------- | ------------------------------- |
| `-w, --workers`               | Concurrent copy threads         |
| `-b, --buffer`                | I/O buffer bytes (must be >= 1) |
| `--verify`                    | SHA-256 verify after each copy  |
| `--unpack` / `--list`         | Unpack or list archives         |
| `--on-conflict`               | `overwrite` / `skip` / `update` |
| `--dry-run` / `-q` / `--json` | Scripting helpers               |
| `--exclude` / `--include`     | Glob filters                    |
| `--retries` / `--retry-wait`  | Transient I/O retries           |
| `--mirror` / `--move`         | Sync delete / move              |
| `--password`                  | Encrypted archives              |

Exit codes: `0` ok, `1` failure/errors, `2` bad args.

### Archive Support

- **ZIP / tar / tar.gz / tar.bz2 / tar.xz**: stdlib
- **7z**: `py7zr`
- **RAR**: external `7z.exe` on PATH

### Data Integrity

- `--verify` hashes source, copies, then verifies destination
- Checksum mismatch is recorded as a per-file error (non-zero exit)

---

## 6. Important Notes

### External Dependencies

- **7-Zip**: Required for RAR unpacking. Must be installed and available in system PATH.
  - Download from: <https://www.7-zip.org/download.html>

### Platform

- **Target OS**: Windows only (`win32`)
- **Architectures**: `x64`, `ia32`
- **Node.js / Bun**: Node >= 14 or Bun >= 1

### Distribution

- npm/Bun package `@involvex/supercopy` wraps `dist/SuperCopy.exe`
- `.npmignore` intentionally ships the exe (do not rely on `.gitignore` alone)

---

## 7. Code Style Guidelines

### Python

- Use meaningful variable and function names
- Add docstrings for classes and major functions
- Follow PEP 8 style conventions
- Use type hints where beneficial

### Example Structure

```python
class CopyEngine:
    """Encapsulates the core logic for high-performance file copying."""
    
    def get_file_list(self, source_dir):
        """Generates a list of all files and their total size."""
        # Implementation...
```

---

## 8. Troubleshooting

### Common Issues

1. **7z.exe not found**: Ensure 7-Zip is installed and in system PATH
2. **Import errors**: Ensure virtual environment is activated and dependencies installed
3. **Build failures**: Check Python version (3.9+ required) and PyInstaller compatibility

### Common CLI issues

1. Missing `dist/SuperCopy.exe`: run `bun run build`
2. `--buffer 0` rejected with exit `2`
3. Copy with per-file errors exits `1`

---

## 9. Contributing

When making changes:

1. Run `python -m pytest tests -q`
2. Test CLI copy, unpack, and `--json` / exit codes
3. Build with `bun run build` before publishing
4. Update `package.json` version and `CHANGELOG.md`
