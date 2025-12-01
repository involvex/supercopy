# SuperCopy

SuperCopy is a high-performance, command-line file and folder copy utility for Windows, designed to be significantly faster than the default copy tools, especially for large numbers of files.

It is built in Python and leverages multi-threading and optimized I/O buffers to maximize copy speed.

---

## Features

- **Multi-Threaded Copying:** Uses a pool of concurrent threads to copy multiple files in parallel, drastically reducing the time it takes to copy directories with thousands of small files.
- **Optimized Buffer Size:** Uses a large, 1MB I/O buffer to speed up the transfer of large files by minimizing disk read/write operations.
- **Real-Time Progress Bar:** Displays a detailed progress bar showing the number of files copied, progress percentage, and transfer rate.
- **Data Integrity Check:** Includes an optional `--verify` flag that performs a SHA-256 checksum on each file after it's copied to guarantee that the destination file is a perfect match to the source.
- **Simple Installation:** A basic batch script installer is provided to make the tool available system-wide from any terminal.
- **Robust Error Handling:** Reports a summary of any files that failed to copy at the end of the operation.

---

## Installation

A standalone executable (`SuperCopy.exe`) is created using PyInstaller. An installer script is provided to add it to your system's PATH.

1. Ensure you have run the build process to create `dist\SuperCopy.exe`.
2. Right-click on `install.bat` and select **"Run as administrator"**.
3. Follow the on-screen prompts. The script will copy the executable to `%LOCALAPPDATA%\SuperCopy` and add this directory to your user PATH environment variable.
4. **Important:** You must **restart your terminal** (Command Prompt, PowerShell, etc.) for the PATH changes to take effect.

After restarting your terminal, you can invoke the tool from any directory by simply typing `SuperCopy`.

---
## Usage

The tool is invoked from the command line with a source and a destination path.

### Syntax
```
SuperCopy <source> <destination> [options]
```

### Arguments
- `source`: The source file or directory to copy.
- `destination`: The destination path.
  - If the destination is a directory, the source file/folder will be copied *inside* it.
  - If the destination does not exist, it will be created.

### Options
- `-w, --workers`: The number of concurrent threads to use for copying.
  - *Default*: The number of CPU cores on your system.
- `-b, --buffer`: The buffer size for reading/writing files, in bytes.
  - *Default*: `1048576` (1MB).
- `--verify`: Verifies file integrity after copying using a SHA-256 checksum.
  - *Note*: This will significantly slow down the copy process but guarantees data integrity.

### Examples

**1. Copy a single file:**
```shell
SuperCopy "C:\Users\MyUser\Documents\report.docx" "D:\Backups\"
```

**2. Copy an entire directory:**
```shell
SuperCopy "C:\Users\MyUser\Pictures" "D:\Backups\MyPictures"
```

**3. Copy a directory using 16 worker threads:**
```shell
SuperCopy "C:\Project" "E:\Archives" --workers 16
```

**4. Copy a directory and verify the integrity of every file:**
```shell
SuperCopy "C:\ImportantData" "F:\VerifiedBackup" --verify
```

---
## Build from Source

If you wish to build the executable yourself:
1. Make sure you have Python installed.
2. Create and activate a virtual environment:
   ```shell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Install the required packages:
   ```shell
   pip install -r requirements.txt 
   ```
   (Note: You would need to create a `requirements.txt` file containing `tqdm` and `pyinstaller`).
4. Run the PyInstaller build command:
   ```shell
   pyinstaller --onefile --console --name SuperCopy supercopy.py
   ```
5. The final executable will be located in the `dist` directory.
