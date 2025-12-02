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

---

## Installation

To install SuperCopy globally via npm, you need Node.js and npm installed on your system.

1.  **Install Node.js & npm:** If you don't have them, download and install Node.js from [nodejs.org](https://nodejs.org/). npm is included with Node.js.
2.  **Install SuperCopy:** Open your terminal (Command Prompt, PowerShell, Git Bash) and run:
    ```shell
    npm install -g @involvex/supercopy
    ```
3.  **Usage:** After installation, you can launch the GUI by typing `supercopy` or use the CLI with arguments:
    ```shell
    supercopy
    supercopy --help
    supercopy <source> <destination> --unpack
    ```

---

## Usage

### GUI Mode

Simply launch the SuperCopy application from your Start Menu.

1.  **Select Source:** Click the "Browse" button to select a source file or directory.
2.  **Select Destination:** Click the "Browse" button to select a destination directory.
3.  **Choose Operation:**
    - If you select a normal file or folder, the main button will say **"Copy"**.
    - If you select a `.zip`, `.7z`, or `.rar` file, the button will automatically change to **"Unpack"**.
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

## Build from Source (for Developers)

If you wish to build the `SuperCopy.exe` executable yourself (e.g., to make changes or prepare a new version for npm publishing):

1.  **Prerequisites:**
    - Python 3.9+ installed and added to your system PATH.
    - Node.js and npm installed (if you plan to publish to npm).
    - Basic understanding of command-line operations.
2.  **Clone the Repository:**
    ```shell
    git clone <your-repo-url>
    cd supercopy
    ```
3.  **Prepare 7-Zip (for unpacking .rar files):**
    - The SuperCopy application relies on `7z.exe` being available in your system's PATH for RAR unpacking.
    - If you do not have 7-Zip installed, download it from the [official 7-Zip website](https://www.7-zip.org/download.html) and install it. Ensure its executable directory is added to your system's PATH.
4.  **Run the Build Script:**
    - Execute the `build.bat` script in the project root:
    ```shell
    build.bat
    ```

    - This script will automatically create a Python virtual environment, install all Python dependencies (`customtkinter`, `tqdm`, `pyinstaller`, `py7zr`), and run PyInstaller to create `dist\SuperCopy.exe`.
5.  **Locate the Executable:**
    - The final executable, `SuperCopy.exe`, will be located in the `dist` directory.
