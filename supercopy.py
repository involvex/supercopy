import os
import shutil
import argparse
import sys
import hashlib
import zipfile
import py7zr
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import ctypes

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

    def _copy_file_task(self, source_path, dest_path, buffer_size, verify, progress_callback):
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
            progress_callback('file', file_size)
            return (source_path, None)
        except Exception as e:
            progress_callback('file', 0)
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

    def run_copy(self, source, destination, workers, buffer_size, verify, progress_callback):
        """Executes the copy operation for a source file or directory."""
        errors = []
        source = os.path.abspath(source)
        destination = os.path.abspath(destination)

        if not os.path.exists(source):
            raise FileNotFoundError(f"Source path '{source}' does not exist.")

        if os.path.isdir(source):
            if os.path.exists(destination) and not os.path.isdir(destination):
                raise ValueError(f"Cannot copy a directory to a file '{destination}'.")

            dest_dir = os.path.join(destination, os.path.basename(source)) if os.path.isdir(destination) and os.path.basename(source) != '' else destination
            
            file_list, total_size = self.get_file_list(source)
            
            if not file_list:
                progress_callback('finish', 0)
                return []

            progress_callback('start', {'files': len(file_list), 'bytes': total_size})
            
            required_dirs = {os.path.join(dest_dir, rel_path) for _, rel_path, _, _ in file_list}
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
                        progress_callback
                    )
                    for src_path, rel_path, file_name, _ in file_list
                }
                
                for future in as_completed(futures):
                    path, error = future.result()
                    if error:
                        errors.append((path, error))
        else: # It's a single file
            if os.path.isdir(destination):
                dest_file = os.path.join(destination, os.path.basename(source))
            else:
                dest_file = destination
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)

            file_size = os.path.getsize(source)
            progress_callback('start', {'files': 1, 'bytes': file_size})

            _, error = self._copy_file_task(source, dest_file, buffer_size, verify, progress_callback)
            if error:
                errors = [(source, error)]

        progress_callback('finish', 0)
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

        if ext == '.zip':
            self._unpack_zip(archive_path, destination_path, progress_callback)
        elif ext == '.7z':
            self._unpack_7z(archive_path, destination_path, progress_callback)
        elif ext == '.rar':
            self._unpack_rar(archive_path, destination_path, progress_callback)
        else:
            raise ValueError(f"Unsupported archive format: {ext}")
        
        progress_callback('finish', 0)

    def _unpack_zip(self, archive_path, dest_path, callback):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            members = zip_ref.infolist()
            total_size = sum(f.file_size for f in members)
            callback('start', {'files': len(members), 'bytes': total_size})
            
            for member in members:
                zip_ref.extract(member, dest_path)
                callback('file', member.file_size)

    def _unpack_7z(self, archive_path, dest_path, callback):
        with py7zr.SevenZipFile(archive_path, mode='r') as z:
            members = z.list()
            total_size = sum(f.uncompressed for f in members if not f.is_directory)
            callback('start', {'files': len(members), 'bytes': total_size})
            
            z.extractall(path=dest_path)
            for f in members:
                callback('file', f.uncompressed if not f.is_directory else 0)

    def _unpack_rar(self, archive_path, dest_path, callback):
        total_size = 1
        total_files = 1
        callback('start', {'files': total_files, 'bytes': total_size})
        
        try:
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
            else:
                exe_dir = os.path.dirname(os.path.abspath(__file__))
            
            tool_path = "7z"
            if os.path.exists(os.path.join(exe_dir, "7z.exe")):
                 tool_path = os.path.join(exe_dir, "7z.exe")

            command = [tool_path, 'x', archive_path, f'-o{dest_path}', '-y']
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(command, capture_output=True, text=True, startupinfo=startupinfo, check=False)

            if result.returncode != 0:
                raise Exception(f"7-Zip failed to unpack {archive_path}. Error: {result.stderr}")

            callback('file', total_size)

        except FileNotFoundError:
            raise Exception("7z.exe not found. Ensure it is in the application directory or in your system's PATH.")
        except Exception as e:
            raise Exception(f"Unpacking .rar files failed. Error: {e}")

class SuperCopyApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SuperCopy")
        self.geometry("600x450")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(1, weight=1)

        self.source_path = tk.StringVar()
        self.dest_path = tk.StringVar()
        self.verify_files = tk.BooleanVar()
        self.is_unpack_mode = False
        self.is_running = False

        # Source Path
        self.source_label = ctk.CTkLabel(self, text="Source:")
        self.source_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        self.source_entry = ctk.CTkEntry(self, textvariable=self.source_path)
        self.source_entry.grid(row=0, column=1, padx=10, pady=(10, 5), sticky="ew")
        self.source_button = ctk.CTkButton(self, text="Browse...", command=self.browse_source)
        self.source_button.grid(row=0, column=2, padx=10, pady=(10, 5))

        # Destination Path
        self.dest_label = ctk.CTkLabel(self, text="Destination:")
        self.dest_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.dest_entry = ctk.CTkEntry(self, textvariable=self.dest_path)
        self.dest_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        self.dest_button = ctk.CTkButton(self, text="Browse...", command=self.browse_destination)
        self.dest_button.grid(row=1, column=2, padx=10, pady=5)
        
        # Options
        self.options_frame = ctk.CTkFrame(self)
        self.options_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        self.verify_checkbox = ctk.CTkCheckBox(self.options_frame, text="Verify files after copy (slower)", variable=self.verify_files)
        self.verify_checkbox.pack(side="left", padx=10, pady=10)

        # Action Button
        self.action_button = ctk.CTkButton(self, text="Copy", command=self.start_operation)
        self.action_button.grid(row=3, column=0, columnspan=3, padx=10, pady=10, ipady=10, sticky="ew")

        # Progress & Status
        self.status_label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_label.grid(row=4, column=0, columnspan=3, padx=10, pady=(10, 0), sticky="ew")

        self.pbar_files_label = ctk.CTkLabel(self, text="Files:", anchor="w")
        self.pbar_files_label.grid(row=5, column=0, padx=10, pady=0, sticky="w")
        self.pbar_files = ctk.CTkProgressBar(self)
        self.pbar_files.set(0)
        self.pbar_files.grid(row=5, column=1, columnspan=2, padx=10, pady=0, sticky="ew")

        self.pbar_bytes_label = ctk.CTkLabel(self, text="Total Size:", anchor="w")
        self.pbar_bytes_label.grid(row=6, column=0, padx=10, pady=5, sticky="w")
        self.pbar_bytes = ctk.CTkProgressBar(self)
        self.pbar_bytes.set(0)
        self.pbar_bytes.grid(row=6, column=1, columnspan=2, padx=10, pady=5, sticky="ew")

        self.source_path.trace_add("write", self.update_ui_mode)

    def browse_source(self):
        current_path = self.source_path.get()
        try:
            is_file = os.path.isfile(current_path)
        except Exception:
            is_file = False

        if is_file or any(current_path.lower().endswith(ext) for ext in ['.zip', '.rar', '.7z']):
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
        is_archive = any(source.lower().endswith(ext) for ext in ['.zip', '.rar', '.7z'])
        
        if is_archive:
            self.is_unpack_mode = True
            self.action_button.configure(text="Unpack")
            self.verify_checkbox.configure(state="disabled")
        else:
            self.is_unpack_mode = False
            self.action_button.configure(text="Copy")
            self.verify_checkbox.configure(state="normal")

    def set_ui_state(self, is_running):
        state = "disabled" if is_running else "normal"
        self.source_entry.configure(state=state)
        self.dest_entry.configure(state=state)
        self.source_button.configure(state=state)
        self.dest_button.configure(state=state)
        self.verify_checkbox.configure(state=state if not self.is_unpack_mode else "disabled")
        self.action_button.configure(state=state)
        if is_running:
            self.action_button.configure(text="Working...")
        else:
            self.update_ui_mode()

    def gui_progress_callback(self, event_type, data):
        if event_type == 'start':
            self.total_files = data['files']
            self.total_bytes = data['bytes']
            self.copied_files = 0
            self.copied_bytes = 0
            self.pbar_files.set(0)
            self.pbar_bytes.set(0)
            self.status_label.configure(text=f"Starting... Found {self.total_files} files.")
        
        elif event_type == 'file':
            self.copied_files += 1
            self.copied_bytes += data
            
            file_progress = self.copied_files / self.total_files if self.total_files > 0 else 0
            byte_progress = self.copied_bytes / self.total_bytes if self.total_bytes > 0 else 0
            
            self.pbar_files.set(file_progress)
            self.pbar_bytes.set(byte_progress)
            
            self.status_label.configure(text=f"Processed: {self.copied_files}/{self.total_files} files")

        elif event_type == 'finish':
            self.status_label.configure(text="Operation finished.")
            self.set_ui_state(False)

    def start_operation(self):
        source = self.source_path.get()
        dest = self.dest_path.get()

        if not source or not dest:
            self.status_label.configure(text="Error: Source and Destination paths are required.")
            return

        self.set_ui_state(True)
        
        thread_args = (source, dest, self.gui_progress_callback)
        if self.is_unpack_mode:
            engine = UnpackEngine()
            thread = threading.Thread(target=engine.run_unpack, args=thread_args)
        else:
            engine = CopyEngine()
            # Note: GUI doesn't have a workers setting, defaults to os.cpu_count()
            full_args = (source, dest, os.cpu_count() or 4, 1048576, self.verify_files.get(), self.gui_progress_callback)
            thread = threading.Thread(target=engine.run_copy, args=full_args)
        
        thread.daemon = True
        thread.start()

def main_gui():
    """Launches the graphical user interface."""
    app = SuperCopyApp()
    app.mainloop()

def main_cli():
    """Function to run the tool in command-line mode."""
    parser = argparse.ArgumentParser(
        description="A high-performance file copy and unpack tool.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("source", help="The source file or directory.")
    parser.add_argument("destination", help="The destination file or directory.")
    parser.add_argument(
        "--unpack", action="store_true",
        help="Unpack mode: treats the source as an archive to be extracted to the destination."
    )
    parser.add_argument(
        "-w", "--workers", type=int, default=os.cpu_count() or 4,
        help="Number of concurrent threads for copying.\n(Not used for unpacking)."
    )
    parser.add_argument(
        "-b", "--buffer", type=int, default=1048576,  # 1MB
        help="Buffer size for reading/writing files in bytes.\n(Only for copy mode)."
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify file integrity after copy using SHA-256 checksum.\n(Only for copy mode)."
    )
    
    args = parser.parse_args()

    # --- Progress Bar Handling for CLI ---
    pbar_files = None
    pbar_bytes = None

    def cli_progress_callback(event_type, data):
        nonlocal pbar_files, pbar_bytes
        if event_type == 'start':
            pbar_files = tqdm(total=data['files'], unit='file', desc="Files")
            pbar_bytes = tqdm(total=data['bytes'], unit='B', desc="Size ", unit_scale=True, unit_divisor=1024)
        elif event_type == 'file':
            if pbar_files: pbar_files.update(1)
            if pbar_bytes and data > 0: pbar_bytes.update(data)
        elif event_type == 'finish':
            if pbar_files: pbar_files.close()
            if pbar_bytes: pbar_bytes.close()

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
                args.source, args.destination,
                args.workers, args.buffer, args.verify,
                cli_progress_callback
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
        # App is built as a console app, so CLI mode works by default.
        main_cli()
    else:
        # We are in GUI mode. Hide the console window that is created by default.
        try:
            # Get a handle to the console window
            console_window = ctypes.windll.kernel32.GetConsoleWindow()
            if console_window != 0:
                # Hide the console window (0 = SW_HIDE)
                ctypes.windll.user32.ShowWindow(console_window, 0)
        except Exception:
            # This might fail if not running in a console, which is fine.
            pass
        main_gui()