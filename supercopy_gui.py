
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
from supercopy import CopyEngine, UnpackEngine

class SuperCopyApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SuperCopy")
        self.geometry("600x450")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(1, weight=1)

        # --- State Variables ---
        self.source_path = tk.StringVar()
        self.dest_path = tk.StringVar()
        self.verify_files = tk.BooleanVar()
        self.is_unpack_mode = False
        self.is_running = False

        # --- UI Widgets ---

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

        # Bind source path changes
        self.source_path.trace_add("write", self.update_ui_mode)

    def browse_source(self):
        # Allow selecting either a file or a directory
        path = filedialog.askopenfilename()
        if not path:
            path = filedialog.askdirectory()
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
        self.is_running = is_running
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
            self.update_ui_mode() # Reset button text

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

        if self.is_unpack_mode:
            engine = UnpackEngine()
            thread = threading.Thread(target=engine.run_unpack, args=(source, dest, self.gui_progress_callback))
        else:
            engine = CopyEngine()
            thread = threading.Thread(
                target=engine.run_copy,
                args=(source, dest, None, 1048576, self.verify_files.get(), self.gui_progress_callback)
            )
        
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    app = SuperCopyApp()
    app.mainloop()
