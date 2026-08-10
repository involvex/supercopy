# SuperCopy

![Version](https://img.shields.io/badge/version-0.0.9-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

SuperCopy is a high-performance file utility for Windows. It started as a command-line tool to accelerate file copying and has now evolved into a full-featured desktop application with a graphical user interface (GUI).

It is designed to be significantly faster than the default Windows copy tool and now also supports unpacking for major archive formats.

---

## Features

- **Graphical User Interface (GUI):** A clean, modern, and easy-to-use interface for all copy and unpack operations.
- **High-Performance Copying:**
  - **Multi-Threaded:** Uses a pool of concurrent threads to copy multiple files in parallel.
  - **Optimized Buffers:** Uses a large I/O buffer to speed up the transfer of large files.
- **Archive Unpacking:** Unpack `.zip`, `.7z`, and `.rar` archives directly within the application.
- **Real-Time Progress:** Dual progress bars show file-count progress and total size progress for any operation.
- **Data Integrity Check:** Optional `--verify` flag in the CLI to perform a SHA-256 checksum on copied files.
- **Cross-Platform CLI:** Available as an npm package for global installation.
- **Shell Completions:** Tab completion support for PowerShell, Bash, and Zsh.

---

## Installation

### Via npm (Recommended)

To install SuperCopy globally via npm, you need Node.js (>=14.0.0) and npm installed on your system.

1. **Install Node.js & npm:** If you don't have them, download and install Node.js from [nodejs.org](https://nodejs.org/). npm is included with Node.js.

2. **Install SuperCopy:** Open your terminal (Command Prompt, PowerShell, Git Bash) and run:

   ```shell
   npm install -g @involvex/supercopy
   ```

3. **Usage:** After installation, you can launch the GUI by typing `supercopy` or use the CLI with arguments:

   ```shell
   supercopy
   supercopy --help
   supercopy <source> <destination> --unpack
   supercopy --version
   ```

### Windows Installer

A Windows installer (`.exe`) is available from the [GitHub Releases](https://github.com/involvex/supercopy/releases) page. The installer:
- Adds SuperCopy to your system PATH
- Creates Start Menu shortcuts
- Includes an uninstaller

### Prerequisites for RAR Support

**Important:** For `.rar` archive unpacking, you must have **7-Zip** installed and available in your system PATH.

- Download from: [7-Zip Official Website](https://www.7-zip.org/download.html)
- Ensure `7z.exe` is in your PATH (the installer typically does this automatically)

---

## Usage

### GUI Mode

Simply launch the SuperCopy application from your Start Menu or run `supercopy` without arguments.

1. **Select Source:** Click the "Browse" button to select a source file or directory.
2. **Select Destination:** Click the "Browse" button to select a destination directory.
3. **Choose Operation:**
   - If you select a normal file or folder, the main button will say **"Copy"**.
   - If you select a `.zip`, `.7z`, or `.rar` file, the button will automatically change to **"Unpack"**.
4. **Set Options:** Check "Verify files" if you want to ensure data integrity after copying (this option is disabled for unpacking).
5. **Start:** Click the "Copy" or "Unpack" button to begin. Progress will be displayed in real-time.

**Keyboard Shortcuts:**
- `Ctrl+O` - Browse source
- `Ctrl+D` - Browse destination
- `Enter` - Start operation

### Command-Line Mode

The original CLI is still available for scripting and automation.

#### Copy Syntax

```
supercopy <source> <destination> [options]
```

- **Arguments:**
  - `source`: The source file or directory to copy.
  - `destination`: The destination path.
- **Options:**
  - `-w, --workers`: Number of concurrent threads to use (default: CPU core count).
  - `-b, --buffer`: I/O buffer size in bytes (default: 1048576 = 1MB).
  - `--verify`: Verify file integrity after copying using SHA-256.
  - `-v, --version`: Show program's version number and exit.

#### Unpack Syntax

```
supercopy <archive_path> <destination_path> --unpack
```

- **Arguments:**
  - `archive_path`: The `.zip`, `.7z`, or `.rar` file to unpack.
  - `destination_path`: The folder where files will be extracted.
- **Required Flag:**
  - `--unpack`: Switches the tool to unpacking mode.

#### Shell Completions

SuperCopy supports shell completions for PowerShell, Bash, and Zsh.

**PowerShell**
```powershell
# Current session
supercopy completion powershell | Out-String | Invoke-Expression

# Permanent (add to $PROFILE)
supercopy completion powershell | Out-String | Invoke-Expression
# Or save to file and source in profile
supercopy completion powershell > $HOME\Documents\supercopy-completion.ps1
```

**Bash**
```bash
# Current session
source <(supercopy completion bash)

# Permanent (add to ~/.bashrc)
echo 'source <(supercopy completion bash)' >> ~/.bashrc
```

**Zsh**
```zsh
# Current session
source <(supercopy completion zsh)

# Permanent (add to ~/.zshrc)
echo 'source <(supercopy completion zsh)' >> ~/.zshrc
```

---

## Build from Source (for Developers)

If you wish to build the `SuperCopy.exe` executable yourself (e.g., to make changes or prepare a new version for npm publishing):

### Prerequisites

- Python 3.9+ installed and added to your system PATH.
- Node.js and npm installed (if you plan to publish to npm).
- 7-Zip installed for RAR support (see Prerequisites above).
- Basic understanding of command-line operations.

### Build Steps

1. **Clone the Repository:**

   ```shell
   git clone https://github.com/involvex/supercopy.git
   cd supercopy
   ```

2. **Run the Build Script:**

   Execute the `build.bat` script in the project root:

   ```shell
   build.bat
   ```

   This script will:
   - Create a Python virtual environment (`.venv`)
   - Install all Python dependencies (`customtkinter`, `tqdm`, `pyinstaller`, `py7zr`)
   - Run PyInstaller to create `dist\SuperCopy.exe`

3. **Locate the Executable:**

   The final executable, `SuperCopy.exe`, will be located in the `dist` directory.

4. **Create Windows Installer (Optional):**

   If you have NSIS installed, run:

   ```shell
   makensis installer.nsi
   ```

   This creates `SuperCopy-Installer.exe` in the project root.

### Development Mode

To run without building:

```shell
python supercopy.py
```

Or via npm:

```shell
npm start
```

---

## Project Structure

```
supercopy/
├── supercopy.py          # Main Python application (GUI + CLI logic)
├── bin/
│   └── supercopy.js      # Node.js CLI entry point wrapper
├── package.json          # npm package configuration
├── requirements.txt      # Python dependencies
├── build.bat            # Build script for Windows
├── installer.nsi        # NSIS installer configuration
├── SuperCopy.spec       # PyInstaller specification (generated)
├── README.md            # This file
├── CHANGELOG.md         # Release history
├── dist/
│   └── SuperCopy.exe    # Built executable (generated)
└── .gitignore           # Git ignore patterns
```

---

## CLI Options Reference

| Option | Alias | Description | Default |
|--------|-------|-------------|---------|
| `--unpack` | | Switch to archive unpacking mode | false |
| `--workers` | `-w` | Number of concurrent threads | CPU count |
| `--buffer` | `-b` | I/O buffer size in bytes | 1048576 (1MB) |
| `--verify` | | Enable SHA-256 verification after copy | false |
| `--version` | `-v` | Show version and exit | - |
| `--help` | `-h` | Show help message | - |

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `7z.exe not found` | Install 7-Zip and ensure it's in your system PATH. Restart your terminal after installation. |
| `ModuleNotFoundError: No module named 'customtkinter'` | Run `build.bat` to install dependencies, or manually: `pip install -r requirements.txt` |
| `Permission denied` errors | Run terminal as Administrator, or check file/folder permissions. |
| GUI doesn't launch | Ensure you're on Windows. The GUI uses Windows-specific APIs. |
| Antivirus flags the executable | This is a false positive. PyInstaller executables are sometimes flagged. Add an exception or build from source. |

### Debug Mode

The application includes debug logging. Check `console_debug.log` in the working directory for runtime errors.

---

## Contributing

When making changes:

1. Test both GUI and CLI modes
2. Verify archive unpacking works for all supported formats (`.zip`, `.7z`, `.rar`)
3. Test with `--verify` flag for data integrity checks
4. Build and test the executable before submitting
5. Update version in `package.json` for releases
6. Update `CHANGELOG.md` with your changes

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Support

- **Issues:** [GitHub Issues](https://github.com/involvex/supercopy/issues)
- **Discussions:** [GitHub Discussions](https://github.com/involvex/supercopy/discussions)
- **Sponsor:** [GitHub Sponsors](https://github.com/sponsors/involvex)