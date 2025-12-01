
import os
import shutil
import argparse
import sys
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

def get_file_list(source_dir):
    """Generates a list of all files to be copied."""
    file_list = []
    for root, _, files in os.walk(source_dir):
        for file in files:
            source_path = os.path.join(root, file)
            # Correctly map the relative path to the destination
            relative_path = os.path.relpath(root, source_dir)
            file_list.append((source_path, relative_path, file))
    return file_list

def create_dest_dirs(file_list, dest_dir):
    """Creates all necessary destination directories before copying."""
    # Using a set to avoid redundant mkdir calls
    required_dirs = set()
    for _, relative_path, _ in file_list:
        required_dirs.add(os.path.join(dest_dir, relative_path))
    
    for d in required_dirs:
        os.makedirs(d, exist_ok=True)

def verify_checksum(file_path, original_checksum):
    """Verifies the SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(4096):
                sha256.update(chunk)
        return sha256.hexdigest() == original_checksum
    except Exception:
        return False

def copy_file(source_path, dest_path, buffer_size, pbar, verify=False):
    """Copies a single file with a progress bar and optional verification."""
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
            if not verify_checksum(dest_path, original_checksum):
                return (source_path, "Checksum mismatch")

        return (source_path, None)
    except Exception as e:
        return (source_path, str(e))
    finally:
        pbar.update(1)


def main():
    """Main function to parse arguments and initiate copying."""
    parser = argparse.ArgumentParser(
        description="A high-performance file and folder copy tool.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("source", help="The source file or directory.")
    parser.add_argument("destination", help="The destination file or directory.")
    parser.add_argument(
        "-w", "--workers", type=int, default=os.cpu_count() or 4,
        help="Number of concurrent threads to use for copying.\nDefault: Number of CPU cores."
    )
    parser.add_argument(
        "-b", "--buffer", type=int, default=1048576, # 1MB
        help="Buffer size for reading/writing files in bytes.\nDefault: 1048576 (1MB)."
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify file integrity after copy using SHA-256 checksum.\nThis will slow down the copy process."
    )
    
    args = parser.parse_args()
    
    source = os.path.abspath(args.source)
    destination = os.path.abspath(args.destination)
    
    if not os.path.exists(source):
        print(f"Error: Source path '{source}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Source:      {source}")
    print(f"Destination: {destination}")
    print(f"Workers:     {args.workers}")
    print(f"Buffer Size: {args.buffer} bytes")
    print(f"Verify:      {'Enabled' if args.verify else 'Disabled'}\n")

    if os.path.isdir(source):
        # If destination exists and is a file, it's an error.
        if os.path.exists(destination) and not os.path.isdir(destination):
             print(f"Error: Cannot copy a directory to a file '{destination}'.", file=sys.stderr)
             sys.exit(1)
        
        # Smart destination handling: if dest is an existing dir, copy source *into* it.
        # Otherwise, create dest as the new directory.
        dest_dir = os.path.join(destination, os.path.basename(source)) if os.path.isdir(destination) else destination
        
        print("Gathering file list...")
        file_list = get_file_list(source)
        
        if not file_list:
            print("Source directory is empty. Nothing to copy.")
            sys.exit(0)
            
        print(f"Found {len(file_list)} files to copy.")
        print("Creating destination directories...")
        create_dest_dirs(file_list, dest_dir)
        
        errors = []
        with tqdm(total=len(file_list), unit='file', desc="Copying") as pbar:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(
                        copy_file, 
                        src_path, 
                        os.path.join(dest_dir, rel_path, file_name),
                        args.buffer,
                        pbar,
                        args.verify
                    )
                    for src_path, rel_path, file_name in file_list
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
            
        with tqdm(total=1, unit='file', desc="Copying") as pbar:
            _, error = copy_file(source, dest_file, args.buffer, pbar, args.verify)
            if error:
                errors = [(source, error)]

    print("\n----- Copy Operation Summary -----")
    if not errors:
        print("✅ All files copied successfully!")
    else:
        print(f"❌ Completed with {len(errors)} errors.")
        for path, msg in errors:
            print(f"  - {path}: {msg}")
    print("------------------------------------")


if __name__ == "__main__":
    main()

