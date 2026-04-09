# Agents.md - SuperCopy Development Guide

This file provides comprehensive instructions for AI agents working on the SuperCopy project.

---

## 1. Project Overview

**SuperCopy** is a high-performance file utility for Windows that provides:

- A modern GUI for file copying and archive unpacking
- A command-line interface (CLI) for automation
- Multi-threaded file copying with optimized buffers
- Support for unpacking `.zip`, `.7z`, and `.rar` archives
- Real-time progress tracking with dual progress bars
- Optional SHA-256 checksum verification for data integrity

### Tech Stack

| Component | Technology |
|-----------|------------|
| GUI Framework | Python (`customtkinter`, `tkinter`) |
| CLI Wrapper | Node.js |
| Build Tool | PyInstaller |
| Archive Support | `py7zr` (7z), `zipfile` (zip), 7-Zip (RAR) |
| Package Manager | npm (Node.js), pip (Python) |

---

## 2. Useful Commands

### Development Commands

```bash
# Run the application in development mode
python supercopy.py

# Run via npm
npm start

# Run CLI with arguments
supercopy <source> <destination> --verify
supercopy <archive_path> <destination_path> --unpack
```

### Build Commands

```bash
# Build the executable (Windows)
build.bat

# Or manually with PyInstaller
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pyinstaller --name SuperCopy --onefile supercopy.py
```

### npm Commands

```bash
# Publish to npm (after building)
npm publish --access public

# Version bump and release
npm run release
```

---

## 3. Project Structure

```
supercopy/
├── supercopy.py          # Main Python application (GUI + CLI logic)
├── bin/
│   └── supercopy.js      # Node.js CLI entry point wrapper
├── package.json          # npm package configuration
├── requirements.txt      # Python dependencies
├── build.bat            # Build script for Windows
├── installer.nsi        # NSIS installer configuration
├── SuperCopy.spec       # PyInstaller specification
├── README.md            # User documentation
├── dist/
│   └── SuperCopy.exe    # Built executable (generated)
└── .gitignore           # Git ignore patterns
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

| Option | Description |
|--------|-------------|
| `-w, --workers` | Number of concurrent threads (default: based on CPU cores) |
| `-b, --buffer` | I/O buffer size in bytes |
| `--verify` | Perform SHA-256 checksum verification after copying |
| `--unpack` | Switch to archive unpacking mode |

### Archive Support

- **ZIP**: Native Python `zipfile` module
- **7z**: Python `py7zr` library
- **RAR**: Requires external `7z.exe` in system PATH

### Data Integrity

- Use `--verify` flag to enable SHA-256 checksum verification
- Verification happens after file copy and before completion
- Raises exception on checksum mismatch

---

## 6. Important Notes

### External Dependencies

- **7-Zip**: Required for RAR unpacking. Must be installed and available in system PATH.
  - Download from: <https://www.7-zip.org/download.html>

### Platform

- **Target OS**: Windows only (`win32`)
- **Architectures**: `x64`, `ia32`
- **Node.js**: Requires Node.js >= 14.0.0

### Distribution

- The application is distributed as an npm package: `@involvex/supercopy`
- The npm package wraps the PyInstaller-built executable
- Published with `preferGlobal: true` for system-wide CLI access

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

### Debug Mode

The application includes debug logging. Check `console_debug.log` for runtime errors.

---

## 9. Contributing

When making changes:

1. Test both GUI and CLI modes
2. Verify archive unpacking works for all supported formats
3. Test with `--verify` flag for data integrity checks
4. Build and test the executable before submitting
5. Update version in `package.json` for releases
