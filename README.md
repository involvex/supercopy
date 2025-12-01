# SuperCopy

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
- **Professional Installer:** A simple and clean installer for easy system setup.

---

## Installation

1.  Download the latest `SuperCopy-Installer.exe` from the project's releases page.
2.  Run the installer and follow the on-screen instructions.
3.  The installer will automatically add SuperCopy to your system PATH and create a Start Menu shortcut.
4.  You can now launch SuperCopy from the Start Menu or use the `supercopy` command in any terminal.

---

## Usage

### GUI Mode

Simply launch the SuperCopy application from your Start Menu.

1.  **Select Source:** Click the "Browse" button to select a source file or directory.
2.  **Select Destination:** Click the "Browse" button to select a destination directory.
3.  **Choose Operation:**
    -   If you select a normal file or folder, the main button will say **"Copy"**.
    -   If you select a `.zip`, `.7z`, or `.rar` file, the button will automatically change to **"Unpack"**.
4.  **Set Options:** Check "Verify files" if you want to ensure data integrity after copying (this option is disabled for unpacking).
5.  **Start:** Click the "Copy" or "Unpack" button to begin. Progress will be displayed in real-time.

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
  - `-w, --workers`: Number of concurrent threads to use.
  - `-b, --buffer`: I/O buffer size in bytes.
  - `--verify`: Verify file integrity after copying using SHA-256.

#### Unpack Syntax
```
supercopy <archive_path> <destination_path> --unpack
```
- **Arguments:**
  - `archive_path`: The `.zip`, `.7z`, or `.rar` file to unpack.
  - `destination_path`: The folder where files will be extracted.
- **Required Flag:**
  - `--unpack`: Switches the tool to unpacking mode.


---

## Build from Source

If you wish to build the executable yourself:

1.  **Install Python:** Make sure you have Python 3.9+ installed.
2.  **Install NSIS:** Download and install [NSIS (Nullsoft Scriptable Install System)](https://nsis.sourceforge.io/Download). Make sure its directory is added to your system's PATH.
3.  **Get UnRAR utility:**
    -   Download the "UnRAR for Windows" command-line tool from the [official RARLAB website](https://www.rarlab.com/rar_add.htm).
    -   Extract the contents and place `unrar.exe` inside the `assets` directory in the project root.
4.  **Run the Build Script:** Simply run the `build.bat` script.
    -   It will automatically create a virtual environment, install all Python dependencies, and run PyInstaller to create `dist\SuperCopy.exe`.
5.  **Compile the Installer:**
    -   After the build script is finished, right-click on `installer.nsi` and select "Compile NSIS Script".
    -   This will generate the final `SuperCopy-Installer.exe` in the project root directory.

