
import os
import shutil
import argparse
import sys
import hashlib
import zipfile
import rarfile
import py7zr
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

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
                    # File might be a symlink or inaccessible, skip it
                    continue
        return file_list, total_size

    def _copy_file_task(self, source_path, dest_path, buffer_size, verify, progress_callback):
        """The actual file copy operation performed by a worker thread."""
        try:
            original_checksum = None
            if verify:
                sha256 = hashlib.sha256()
                with open(source_path, 'rb') as f:
                    while chunk := f.read(buffer_size):
                        sha256.update(chunk)
                original_checksum = sha256.hexdigest()

            with open(source_path, 'rb') as fsrc, open(dest_path, 'wb') as fdest:
                while chunk := fsrc.read(buffer_size):
                    fdest.write(chunk)
            
            if verify and original_checksum:
                if not self._verify_checksum(dest_path, original_checksum):
                    raise Exception("Checksum mismatch")

            file_size = os.path.getsize(dest_path)
            progress_callback('file', file_size)
            return (source_path, None)
        except Exception as e:
            progress_callback('file', 0) # Still need to advance the file progress bar
            return (source_path, str(e))

    def _verify_checksum(self, file_path, original_checksum):
        """Verifies the SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(4096):
                    sha256.update(chunk)
            return sha256.hexdigest() == original_checksum
        except Exception:
            return False

    def run_copy(self, source, destination, workers, buffer_size, verify, progress_callback):
        """
        Executes the copy operation for a source file or directory.
        Calls the progress_callback with progress updates.
        """
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
            
            # Create destination directories sequentially first
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
        """
        Extracts an archive to a destination.
        Calls the progress_callback with progress updates.
        """
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
            
            # py7zr does not have per-file callbacks, so we extract all
            # and then simulate the progress.
            z.extractall(path=dest_path)
            for f in members:
                callback('file', f.uncompressed if not f.is_directory else 0)

    def _unpack_rar(self, archive_path, dest_path, callback):
        try:
            rarfile.UNRAR_TOOL = "unrar" # Or provide full path
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                members = rar_ref.infolist()
                total_size = sum(f.file_size for f in members)
                callback('start', {'files': len(members), 'bytes': total_size})

                for member in members:
                    rar_ref.extract(member, dest_path)
                    callback('file', member.file_size)
        except rarfile.UNRARError as e:
             raise Exception("Unpacking .rar files failed. Ensure 'unrar.exe' is in your system's PATH. Error: " + str(e))


# --- COMMAND-LINE INTERFACE ---

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

    # --- Progress Bar Handling ---
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
    main_cli()

