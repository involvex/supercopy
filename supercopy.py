import os
import shutil
import argparse
import sys
import hashlib
import zipfile
import py7zr
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import ctypes
import json  # Added json import

# --- HELPER FUNCTIONS ---


def get_version_from_package_json():
    # Determine the base path for package.json
    if getattr(sys, "frozen", False):
        # Running in a bundled executable (SuperCopy.exe is in dist/)
        # package.json is in the parent of the parent of dist/ (i.e., project root)
        exe_dir = os.path.dirname(sys.executable)
        package_json_path = os.path.join(exe_dir, "..", "package.json")
    else:
        # Running as a Python script
        # package.json is in the project root
        package_json_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "package.json"
        )

    try:
        with open(package_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("version", "Unknown Version")
    except (FileNotFoundError, json.JSONDecodeError):
        return "Unknown Version"


# --- CORE ENGINE ---


class CopyEngine:
    """Encapsulates the core logic for high-performance file copying."""

    def get_file_list(self, source_dir):
        """Generates a list of all files and their total size."""
        file_list = []
        total_size = 0
        for root, _, files in os.walk(source_dir):
            for file in files:
                source_path = os.path.join(root, file)
                relative_path = os.path.relpath(root, source_dir)
                try:
                    file_size = os.path.getsize(source_path)
                    total_size += file_size
                    file_list.append((source_path, relative_path, file, file_size))
                except OSError:
                    continue
        return file_list, total_size

    def _copy_file_task(
        self, source_path, dest_path, buffer_size, verify, progress_callback
    ):
        """The actual file copy operation performed by a worker thread."""
        try:
            original_checksum = None
            if verify:
                sha256 = hashlib.sha256()
                with open(source_path, "rb") as f:
                    while chunk := f.read(buffer_size):
                        sha256.update(chunk)
                original_checksum = sha256.hexdigest()

            with open(source_path, "rb") as fsrc, open(dest_path, "wb") as fdest:
                while chunk := fsrc.read(buffer_size):
                    fdest.write(chunk)

            if verify and original_checksum:
                if not self._verify_checksum(dest_path, original_checksum):
                    raise Exception("Checksum mismatch")

            file_size = os.path.getsize(dest_path)
            progress_callback("file", file_size)
            return (source_path, None)
        except Exception as e:
            progress_callback("file", 0)
            return (source_path, str(e))

    def _verify_checksum(self, file_path, original_checksum):
        """Verifies the SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(4096):
                    sha256.update(chunk)
            return sha256.hexdigest() == original_checksum
        except Exception:
            return False

    def run_copy(
        self, source, destination, workers, buffer_size, verify, progress_callback
    ):
        """Executes the copy operation for a source file or directory."""
        errors = []
        source = os.path.abspath(source)
        destination = os.path.abspath(destination)

        if not os.path.exists(source):
            raise FileNotFoundError(f"Source path '{source}' does not exist.")

        if os.path.isdir(source):
            if os.path.exists(destination) and not os.path.isdir(destination):
                raise ValueError(f"Cannot copy a directory to a file '{destination}'.")

            dest_dir = (
                os.path.join(destination, os.path.basename(source))
                if os.path.isdir(destination) and os.path.basename(source) != ""
                else destination
            )

            file_list, total_size = self.get_file_list(source)

            if not file_list:
                progress_callback("finish", 0)
                return []

            progress_callback("start", {"files": len(file_list), "bytes": total_size})

            required_dirs = {
                os.path.join(dest_dir, rel_path) for _, rel_path, _, _ in file_list
            }
            for d in required_dirs:
                os.makedirs(d, exist_ok=True)

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self._copy_file_task,
                        src_path,
                        os.path.join(dest_dir, rel_path, file_name),
                        buffer_size,
                        verify,
                        progress_callback,
                    )
                    for src_path, rel_path, file_name, _ in file_list
                }

                for future in as_completed(futures):
                    path, error = future.result()
                    if error:
                        errors.append((path, error))
        else:  # It's a single file
            if os.path.isdir(destination):
                dest_file = os.path.join(destination, os.path.basename(source))
            else:
                dest_file = destination
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)

            file_size = os.path.getsize(source)
            progress_callback("start", {"files": 1, "bytes": file_size})

            _, error = self._copy_file_task(
                source, dest_file, buffer_size, verify, progress_callback
            )
            if error:
                errors = [(source, error)]

        progress_callback("finish", 0)
        return errors


class UnpackEngine:
    """Encapsulates the logic for unpacking various archive formats."""

    def run_unpack(self, archive_path, destination_path, progress_callback):
        archive_path = os.path.abspath(archive_path)
        destination_path = os.path.abspath(destination_path)

        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive path '{archive_path}' does not exist.")

        os.makedirs(destination_path, exist_ok=True)

        _, ext = os.path.splitext(archive_path)
        ext = ext.lower()

        if ext == ".zip":
            self._unpack_zip(archive_path, destination_path, progress_callback)
        elif ext == ".7z":
            self._unpack_7z(archive_path, destination_path, progress_callback)
        elif ext == ".rar":
            self._unpack_rar(archive_path, destination_path, progress_callback)
        else:
            raise ValueError(f"Unsupported archive format: {ext}")

        progress_callback("finish", 0)

    def _unpack_zip(self, archive_path, dest_path, callback):
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            members = zip_ref.infolist()
            total_size = sum(f.file_size for f in members)
            callback("start", {"files": len(members), "bytes": total_size})

            for member in members:
                zip_ref.extract(member, dest_path)
                callback("file", member.file_size)

    def _unpack_7z(self, archive_path, dest_path, callback):
        with py7zr.SevenZipFile(archive_path, mode="r") as z:
            members = z.list()
            total_size = sum(f.uncompressed for f in members if not f.is_directory)
            callback("start", {"files": len(members), "bytes": total_size})

            z.extractall(path=dest_path)
            for f in members:
                callback("file", f.uncompressed if not f.is_directory else 0)

    def _unpack_rar(self, archive_path, dest_path, callback):
        total_size = 1
        total_files = 1
        callback("start", {"files": total_files, "bytes": total_size})

        try:
            if getattr(sys, "frozen", False):
                exe_dir = os.path.dirname(sys.executable)
            else:
                exe_dir = os.path.dirname(os.path.abspath(__file__))

            tool_path = "7z"
            if os.path.exists(os.path.join(exe_dir, "7z.exe")):
                tool_path = os.path.join(exe_dir, "7z.exe")

            command = [tool_path, "x", archive_path, f"-o{dest_path}", "-y"]

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                check=False,
            )

            if result.returncode != 0:
                raise Exception(
                    f"7-Zip failed to unpack {archive_path}. Error: {result.stderr}"
                )

            callback("file", total_size)

        except FileNotFoundError:
            raise Exception(
                "7z.exe not found. Ensure it is in the application directory or in your system's PATH."
            )
        except Exception as e:
            raise Exception(f"Unpacking .rar files failed. Error: {e}")


class SuperCopyApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SuperCopy - High Performance File Operations")
        self.geometry("750x650")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=1)

        self.source_path = tk.StringVar()
        self.dest_path = tk.StringVar()
        self.verify_files = tk.BooleanVar()
        self.is_unpack_mode = False
        self.is_running = False

        # Main container with padding
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=0, columnspan=3, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(1, weight=1)

        # Header Section
        self.header_frame = ctk.CTkFrame(self.main_frame, height=100, corner_radius=15)
        self.header_frame.grid(row=0, column=0, columnspan=3, padx=0, pady=(0, 20), sticky="ew")
        self.header_frame.grid_propagate(False)
        
        # Add a subtle gradient-like effect using multiple labels
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text=" SuperCopy", 
            font=ctk.CTkFont(size=32, weight="bold")
        )
        self.title_label.pack(pady=(20, 5))
        
        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="High-Performance File Copying & Archive Unpacking",
            font=ctk.CTkFont(size=14),
            text_color="lightgray"
        )
        self.subtitle_label.pack()
        
        # Version info
        version = get_version_from_package_json()
        self.version_label = ctk.CTkLabel(
            self.header_frame,
            text=f"Version {version}",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.version_label.pack()

        # Source Section Card
        self.source_card = ctk.CTkFrame(self.main_frame)
        self.source_card.grid(row=1, column=0, columnspan=3, padx=0, pady=(0, 15), sticky="ew")
        
        self.source_title = ctk.CTkLabel(
            self.source_card, 
            text="📁 Source Location", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.source_title.pack(pady=(15, 10))
        
        source_inner_frame = ctk.CTkFrame(self.source_card, fg_color="transparent")
        source_inner_frame.pack(fill="x", padx=20, pady=(0, 15))
        source_inner_frame.grid_columnconfigure(1, weight=1)
        
        self.source_entry = ctk.CTkEntry(
            source_inner_frame, 
            textvariable=self.source_path,
            placeholder_text="Select source file or folder..."
        )
        self.source_entry.grid(row=0, column=1, padx=(10, 5), pady=5, sticky="ew")
        self.source_button = ctk.CTkButton(
            source_inner_frame, 
            text="Browse", 
            command=self.browse_source,
            width=80
        )
        self.source_button.grid(row=0, column=2, padx=5, pady=5)

        # Destination Section Card
        self.dest_card = ctk.CTkFrame(self.main_frame)
        self.dest_card.grid(row=2, column=0, columnspan=3, padx=0, pady=(0, 15), sticky="ew")
        
        self.dest_title = ctk.CTkLabel(
            self.dest_card, 
            text="📍 Destination Location", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.dest_title.pack(pady=(15, 10))
        
        dest_inner_frame = ctk.CTkFrame(self.dest_card, fg_color="transparent")
        dest_inner_frame.pack(fill="x", padx=20, pady=(0, 15))
        dest_inner_frame.grid_columnconfigure(1, weight=1)
        
        self.dest_entry = ctk.CTkEntry(
            dest_inner_frame, 
            textvariable=self.dest_path,
            placeholder_text="Select destination folder..."
        )
        self.dest_entry.grid(row=0, column=1, padx=(10, 5), pady=5, sticky="ew")
        self.dest_button = ctk.CTkButton(
            dest_inner_frame, 
            text="Browse", 
            command=self.browse_destination,
            width=80
        )
        self.dest_button.grid(row=0, column=2, padx=5, pady=5)

        # Options Section Card
        self.options_card = ctk.CTkFrame(self.main_frame)
        self.options_card.grid(row=3, column=0, columnspan=3, padx=0, pady=(0, 20), sticky="ew")
        
        self.options_title = ctk.CTkLabel(
            self.options_card, 
            text="⚙️ Options", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.options_title.pack(pady=(15, 10))
        
        self.options_inner_frame = ctk.CTkFrame(self.options_card, fg_color="transparent")
        self.options_inner_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        self.verify_checkbox = ctk.CTkCheckBox(
            self.options_inner_frame,
            text="✅ Verify files after copy (slower but more secure)",
            variable=self.verify_files,
            font=ctk.CTkFont(size=14)
        )
        self.verify_checkbox.pack(anchor="w", pady=5)

        # Action Button Section
        self.action_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.action_frame.grid(row=4, column=0, columnspan=3, padx=0, pady=(0, 20), sticky="ew")
        
        self.action_button = ctk.CTkButton(
            self.action_frame, 
            text="🚀 Start Operation", 
            command=self.start_operation,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.action_button.pack(fill="x", pady=10)

        # Progress Section Card
        self.progress_card = ctk.CTkFrame(self.main_frame)
        self.progress_card.grid(row=5, column=0, columnspan=3, padx=0, pady=(0, 10), sticky="ew")
        
        self.progress_title = ctk.CTkLabel(
            self.progress_card, 
            text="📊 Progress", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.progress_title.pack(pady=(15, 10))
        
        self.status_label = ctk.CTkLabel(
            self.progress_card, 
            text="Ready to start", 
            font=ctk.CTkFont(size=14),
            anchor="w"
        )
        self.status_label.pack(fill="x", padx=20, pady=(0, 10))
        
        # File progress
        self.files_frame = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        self.files_frame.pack(fill="x", padx=20, pady=(0, 5))
        
        self.pbar_files_label = ctk.CTkLabel(self.files_frame, text="📄 Files Progress:", anchor="w")
        self.pbar_files_label.pack(anchor="w")
        
        self.pbar_files = ctk.CTkProgressBar(self.progress_card, height=20)
        self.pbar_files.pack(fill="x", padx=20, pady=(0, 10))
        self.pbar_files.set(0)
        
        # Size progress
        self.size_frame = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        self.size_frame.pack(fill="x", padx=20, pady=(0, 5))
        
        self.pbar_bytes_label = ctk.CTkLabel(self.size_frame, text="💾 Data Progress:", anchor="w")
        self.pbar_bytes_label.pack(anchor="w")
        
        self.pbar_bytes = ctk.CTkProgressBar(self.progress_card, height=20)
        self.pbar_bytes.pack(fill="x", padx=20, pady=(0, 15))
        self.pbar_bytes.set(0)

        # Configure main window grid
        self.grid_rowconfigure(0, weight=1)

        self.source_path.trace_add("write", self.update_ui_mode)
        
        # Add keyboard shortcuts
        self.bind('<Control-o>', lambda e: self.browse_source())
        self.bind('<Control-d>', lambda e: self.browse_destination())
        self.bind('<Return>', lambda e: self.start_operation() if not self.is_running else None)
        
        # Center window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        # Set minimum window size
        self.minsize(650, 600)

    def browse_source(self):
        current_path = self.source_path.get()
        try:
            is_file = os.path.isfile(current_path)
        except Exception:
            is_file = False

        if is_file or any(
            current_path.lower().endswith(ext) for ext in [".zip", ".rar", ".7z"]
        ):
            path = filedialog.askopenfilename(title="Select a source file")
        else:
            path = filedialog.askdirectory(title="Select a source folder")

        if path:
            self.source_path.set(path)

    def browse_destination(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_path.set(path)

    def update_ui_mode(self, *args):
        source = self.source_path.get()
        is_archive = any(
            source.lower().endswith(ext) for ext in [".zip", ".rar", ".7z"]
        )

        if is_archive:
            self.is_unpack_mode = True
            self.action_button.configure(text="📦 Unpack Archive")
            self.verify_checkbox.configure(state="disabled")
            self.source_title.configure(text="📦 Archive File")
            self.progress_title.configure(text="📦 Unpacking Progress")
        else:
            self.is_unpack_mode = False
            self.action_button.configure(text=" Start Copy")
            self.verify_checkbox.configure(state="normal")
            self.source_title.configure(text="📁 Source Location")
            self.progress_title.configure(text="📊 Progress")

    def set_ui_state(self, is_running):
        state = "disabled" if is_running else "normal"
        self.source_entry.configure(state=state)
        self.dest_entry.configure(state=state)
        self.source_button.configure(state=state)
        self.dest_button.configure(state=state)
        self.verify_checkbox.configure(
            state=state if not self.is_unpack_mode else "disabled"
        )
        self.action_button.configure(state=state)
        if is_running:
            self.action_button.configure(text="⚡ Processing...")
        else:
            self.update_ui_mode()

    def gui_progress_callback(self, event_type, data):
        if event_type == "start":
            self.total_files = data["files"]
            self.total_bytes = data["bytes"]
            self.copied_files = 0
            self.copied_bytes = 0
            self.pbar_files.set(0)
            self.pbar_bytes.set(0)
            
            if self.is_unpack_mode:
                status_text = f"🗂️ Starting unpacking... Found {self.total_files} items"
            else:
                status_text = f"📋 Starting copy... Found {self.total_files} files"
            
            if self.total_bytes > 0:
                size_mb = self.total_bytes / (1024 * 1024)
                if size_mb > 1024:
                    size_text = f" ({size_mb/1024:.1f} GB)"
                else:
                    size_text = f" ({size_mb:.1f} MB)"
                status_text += size_text
            
            self.status_label.configure(text=status_text)

        elif event_type == "file":
            self.copied_files += 1
            self.copied_bytes += data

            file_progress = (
                self.copied_files / self.total_files if self.total_files > 0 else 0
            )
            byte_progress = (
                self.copied_bytes / self.total_bytes if self.total_bytes > 0 else 0
            )

            self.pbar_files.set(file_progress)
            self.pbar_bytes.set(byte_progress)

            # Calculate speed and ETA
            elapsed_time = time.time() - getattr(self, 'start_time', time.time())
            if elapsed_time > 0:
                bytes_per_second = self.copied_bytes / elapsed_time
                if bytes_per_second > 0:
                    remaining_bytes = self.total_bytes - self.copied_bytes
                    eta_seconds = remaining_bytes / bytes_per_second
                    
                    if eta_seconds < 60:
                        eta_text = f" - ETA: {eta_seconds:.0f}s"
                    elif eta_seconds < 3600:
                        eta_text = f" - ETA: {eta_seconds/60:.0f}m"
                    else:
                        eta_text = f" - ETA: {eta_seconds/3600:.1f}h"
                else:
                    eta_text = ""
            else:
                eta_text = ""

            if self.is_unpack_mode:
                status_text = f"📦 Extracted: {self.copied_files}/{self.total_files} files{eta_text}"
            else:
                status_text = f"📋 Copied: {self.copied_files}/{self.total_files} files{eta_text}"

            self.status_label.configure(text=status_text)

        elif event_type == "finish":
            if self.is_unpack_mode:
                self.status_label.configure(text="✅ Archive unpacking completed successfully!")
            else:
                self.status_label.configure(text="✅ File copying completed successfully!")
            self.set_ui_state(False)

    def start_operation(self):
        source = self.source_path.get()
        dest = self.dest_path.get()

        if not source or not dest:
            self.status_label.configure(
                text="❌ Error: Please select both source and destination paths."
            )
            return

        # Validate source exists
        if not os.path.exists(source):
            self.status_label.configure(
                text=f"❌ Error: Source path does not exist: {source}"
            )
            return

        # Validate destination directory
        dest_dir = os.path.dirname(dest) if os.path.isfile(dest) else dest
        if dest_dir and not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except Exception as e:
                self.status_label.configure(
                    text=f"❌ Error: Cannot create destination directory: {e}"
                )
                return

        self.start_time = time.time()
        self.set_ui_state(True)

        thread_args = (source, dest, self.gui_progress_callback)
        if self.is_unpack_mode:
            engine = UnpackEngine()
            thread = threading.Thread(target=self._safe_run_unpack, args=thread_args)
        else:
            engine = CopyEngine()
            # Note: GUI doesn't have a workers setting, defaults to os.cpu_count()
            full_args = (
                source,
                dest,
                os.cpu_count() or 4,
                1048576,
                self.verify_files.get(),
                self.gui_progress_callback,
            )
            thread = threading.Thread(target=self._safe_run_copy, args=full_args)

        thread.daemon = True
        thread.start()

    def _safe_run_copy(self, source, dest, workers, buffer_size, verify, callback):
        """Wrapper for safe copy operation with error handling."""
        try:
            engine = CopyEngine()
            errors = engine.run_copy(source, dest, workers, buffer_size, verify, callback)
            if errors:
                # Schedule error reporting in main thread
                self.after(0, lambda: self._show_errors(errors))
        except Exception as e:
            self.after(0, lambda: self._show_operation_error(str(e)))

    def _safe_run_unpack(self, source, dest, callback):
        """Wrapper for safe unpack operation with error handling."""
        try:
            engine = UnpackEngine()
            engine.run_unpack(source, dest, callback)
        except Exception as e:
            self.after(0, lambda: self._show_operation_error(str(e)))

    def _show_errors(self, errors):
        """Display errors in the UI."""
        self.set_ui_state(False)
        error_count = len(errors)
        self.status_label.configure(
            text=f"⚠️ Operation completed with {error_count} errors. Check console for details."
        )
        
        # Log errors to console
        print(f"\n⚠️ Copy Operation completed with {error_count} errors:")
        for path, msg in errors:
            print(f"  ❌ {path}: {msg}")
        print("-" * 50)

    def _show_operation_error(self, error_msg):
        """Display operation error in the UI."""
        self.set_ui_state(False)
        self.status_label.configure(text=f"❌ Operation failed: {error_msg}")
        print(f"\n❌ Operation failed: {error_msg}")

    def browse_source(self):
        current_path = self.source_path.get()
        try:
            is_file = os.path.isfile(current_path)
        except Exception:
            is_file = False

        if is_file or any(
            current_path.lower().endswith(ext) for ext in [".zip", ".rar", ".7z"]
        ):
            path = filedialog.askopenfilename(
                title="Select a source file",
                filetypes=[
                    ("All Files", "*.*"),
                    ("ZIP Archive", "*.zip"),
                    ("7-Zip Archive", "*.7z"),
                    ("RAR Archive", "*.rar"),
                ]
            )
        else:
            path = filedialog.askdirectory(title="Select a source folder")

        if path:
            self.source_path.set(path)

    def browse_destination(self):
        path = filedialog.askdirectory(title="Select destination folder")
        if path:
            self.dest_path.set(path)


def main_gui():
    """Launches the graphical user interface."""
    app = SuperCopyApp()
    app.mainloop()


def main_cli():
    """Function to run the tool in command-line mode."""
    current_version = get_version_from_package_json()  # Get version here
    parser = argparse.ArgumentParser(
        description="A high-performance file copy and unpack tool.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    # Add version argument
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {current_version}",
        help="Show program's version number and exit.",
    )
    parser.add_argument("source", help="The source file or directory.")
    parser.add_argument("destination", help="The destination file or directory.")
    parser.add_argument(
        "--unpack",
        action="store_true",
        help="Unpack mode: treats the source as an archive to be extracted to the destination.",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=os.cpu_count() or 4,
        help="Number of concurrent threads for copying.\n(Not used for unpacking).",
    )
    parser.add_argument(
        "-b",
        "--buffer",
        type=int,
        default=1048576,  # 1MB
        help="Buffer size for reading/writing files in bytes.\n(Only for copy mode).",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify file integrity after copy using SHA-256 checksum.\n(Only for copy mode).",
    )

    args = parser.parse_args()

    # The dispatcher logic is now in __main__. This function is only called for CLI.
    # So we can assume args.source and args.destination should exist.
    # The original check `if not args.source or not args.destination:` is problematic
    # because `-h` will trigger it. `argparse` handles the exit on `-h` itself.

    # --- Progress Bar Handling for CLI ---
    pbar_files = None
    pbar_bytes = None

    def cli_progress_callback(event_type, data):
        nonlocal pbar_files, pbar_bytes
        if event_type == "start":
            pbar_files = tqdm(total=data["files"], unit="file", desc="Files")
            pbar_bytes = tqdm(
                total=data["bytes"],
                unit="B",
                desc="Size ",
                unit_scale=True,
                unit_divisor=1024,
            )
        elif event_type == "file":
            if pbar_files:
                pbar_files.update(1)
            if pbar_bytes and data > 0:
                pbar_bytes.update(data)
        elif event_type == "finish":
            if pbar_files:
                pbar_files.close()
            if pbar_bytes:
                pbar_bytes.close()

    try:
        if args.unpack:
            print(f"Unpacking {args.source} to {args.destination}...")
            engine = UnpackEngine()
            engine.run_unpack(args.source, args.destination, cli_progress_callback)
            print("\n✅ Unpacking completed successfully!")
        else:
            print(f"Copying {args.source} to {args.destination}...")
            engine = CopyEngine()
            errors = engine.run_copy(
                args.source,
                args.destination,
                args.workers,
                args.buffer,
                args.verify,
                cli_progress_callback,
            )

            print("\n----- Copy Operation Summary -----")
            if not errors:
                print("✅ All files copied successfully!")
            else:
                print(f"❌ Completed with {len(errors)} errors.")
                for path, msg in errors:
                    print(f"  - {path}: {msg}")
            print("------------------------------------")

    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    is_cli_mode = len(sys.argv) > 1

    if is_cli_mode:
        main_cli()
    else:
        # We are in GUI mode. Hide the console window.
        try:
            console_window = ctypes.windll.kernel32.GetConsoleWindow()
            if console_window != 0:
                ctypes.windll.user32.ShowWindow(console_window, 0)  # 0 = SW_HIDE
        except Exception:
            pass
        main_gui()
