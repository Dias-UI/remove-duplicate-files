import os
import hashlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, UnidentifiedImageError
import pandas as pd
from datetime import datetime
from pathlib import Path
import threading
from tqdm import tqdm

class FileComparisonUI:
    def __init__(self, root):
        self.root = root
        self.root.title("File Comparison Tool")
        self.root.geometry("1000x820")
        self.root.resizable(True, True)
        self.root.minsize(800, 600)
        
        # Variables
        self.dir1 = tk.StringVar()
        self.dir2 = tk.StringVar()
        self.matches = []
        self.current_index = 0
        self.checkboxes = []
        self.delete_from = tk.StringVar(value="dir2")
        self.total_matches = tk.StringVar(value="No comparison performed yet")
        self.single_dir_mode = tk.BooleanVar(value=False)
        self.include_subfolders = tk.BooleanVar(value=True)
        self.display_full_path = tk.BooleanVar(value=False)
        
        # Add supported file types
        self.supported_types = {
            'images': ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.heic', '.tiff'),
            'documents': ('.pdf', '.txt', '.doc', '.docx', '.xls', '.xlsx'),
            'all': None  # None means accept all files
        }
        
        # Configure root to expand with content
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Create main scrollable canvas
        self.canvas = tk.Canvas(root)
        self.scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configure scrollable frame to expand horizontally
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Create window in canvas that expands to canvas width
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=self.canvas.winfo_width())
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        
        # Configure canvas to expand with window
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.setup_ui()
        
    def on_canvas_configure(self, event):
        # Update the canvas window to match canvas width
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def setup_ui(self):
        # Directory Selection Frame
        dir_frame = ttk.LabelFrame(self.scrollable_frame, text="Directory Selection", padding="5")
        dir_frame.pack(fill='x', padx=5, pady=5)
        
        # Mode selection
        mode_frame = ttk.Frame(dir_frame)
        mode_frame.grid(row=0, column=0, columnspan=3, pady=5)
        ttk.Checkbutton(mode_frame, text="Single Directory Mode", 
                       variable=self.single_dir_mode, 
                       command=self.toggle_mode).pack(side='left', padx=5)
        ttk.Checkbutton(mode_frame, text="Include Subfolders", 
                       variable=self.include_subfolders).pack(side='left', padx=5)
        ttk.Checkbutton(mode_frame, text="Show Full Paths", 
                       variable=self.display_full_path).pack(side='left', padx=5)
        
        # Directory 1
        ttk.Label(dir_frame, text="Directory 1:").grid(row=1, column=0, padx=5, pady=5)
        ttk.Entry(dir_frame, textvariable=self.dir1, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(dir_frame, text="Browse", command=lambda: self.browse_directory(self.dir1)).grid(row=1, column=2, padx=5)
        
        # Directory 2 (will be hidden in single directory mode)
        self.dir2_widgets = []
        label2 = ttk.Label(dir_frame, text="Directory 2:")
        label2.grid(row=2, column=0, padx=5, pady=5)
        entry2 = ttk.Entry(dir_frame, textvariable=self.dir2, width=50)
        entry2.grid(row=2, column=1, padx=5)
        browse2 = ttk.Button(dir_frame, text="Browse", command=lambda: self.browse_directory(self.dir2))
        browse2.grid(row=2, column=2, padx=5)
        self.dir2_widgets.extend([label2, entry2, browse2])
        
        ttk.Button(dir_frame, text="Compare", command=self.start_comparison).grid(row=3, column=1, pady=10)
        
        # Progress Frame
        progress_frame = ttk.Frame(self.scrollable_frame)
        progress_frame.pack(fill='x', padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill='x', side='top')
        
        self.processing_label = ttk.Label(progress_frame, text="")
        self.processing_label.pack(side='top', pady=2)
        
        # Add index label
        self.index_label = ttk.Label(progress_frame, text="")
        self.index_label.pack(side='top', pady=2)

        # Image Comparison Frame (remove fixed height)
        self.comparison_frame = ttk.Frame(self.scrollable_frame)
        self.comparison_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Left Image Frame
        left_frame = ttk.LabelFrame(self.comparison_frame, text="Directory 1 File")
        left_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        self.img_label1 = ttk.Label(left_frame, cursor="hand2")
        self.img_label1.pack(padx=5, pady=5)
        self.img_label1.bind('<Button-1>', lambda e: self.open_file("dir1"))
        ttk.Button(left_frame, text="Delete This File", 
                  command=lambda: self.delete_single_image("dir1")).pack(pady=5)
        ttk.Button(left_frame, text="Delete All Duplicates from Dir 1",
                  command=lambda: self.delete_all_duplicates("dir1")).pack(pady=5)
        
        # Right Image Frame
        right_frame = ttk.LabelFrame(self.comparison_frame, text="Directory 2 File")
        right_frame.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
        self.img_label2 = ttk.Label(right_frame, cursor="hand2")
        self.img_label2.pack(padx=5, pady=5)
        self.img_label2.bind('<Button-1>', lambda e: self.open_file("dir2"))
        ttk.Button(right_frame, text="Delete This File", 
                  command=lambda: self.delete_single_image("dir2")).pack(pady=5)
        ttk.Button(right_frame, text="Delete All Duplicates from Dir 2",
                  command=lambda: self.delete_all_duplicates("dir2")).pack(pady=5)

        # Configure comparison frame columns to expand equally
        self.comparison_frame.grid_columnconfigure(0, weight=1)
        self.comparison_frame.grid_columnconfigure(1, weight=1)
        
        # Navigation Frame
        nav_frame = ttk.Frame(self.scrollable_frame)
        nav_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(nav_frame, text="Previous", command=self.show_previous).pack(side='left', padx=5)
        ttk.Button(nav_frame, text="Next", command=self.show_next).pack(side='left', padx=5)
        
        # Results Label
        results_frame = ttk.LabelFrame(self.scrollable_frame, text="Results")
        results_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(results_frame, textvariable=self.total_matches).pack(padx=5, pady=5)

    def browse_directory(self, dir_var):
        directory = filedialog.askdirectory()
        if directory:
            dir_var.set(directory)
    
    def get_file_hash(self, filepath):
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def start_comparison(self):
        if not self.dir1.get() or (not self.dir2.get() and not self.single_dir_mode.get()):
            messagebox.showerror("Error", "Please select both directories or enable Single Directory Mode")
            return
            
        # Reset variables
        self.matches = []
        self.current_index = 0
        self.checkboxes = []
        
        # Make sure progress bar and label are visible before starting
        self.progress_bar.pack(fill='x', side='top')
        self.processing_label.pack(side='top', pady=2)
        self.progress_var.set(0)
        self.processing_label.config(text="Starting comparison...")
        self.root.update_idletasks()
        
        # Start comparison in a separate thread
        thread = threading.Thread(target=self.compare_directories)
        thread.start()
    
    def toggle_mode(self):
        # Show/hide directory 2 widgets based on mode
        if self.single_dir_mode.get():
            self.dir2.set("")
            for widget in self.dir2_widgets:
                widget.grid_remove()
        else:
            for widget in self.dir2_widgets:
                widget.grid()

    def compare_directories(self):
        if self.single_dir_mode.get():
            self.compare_single_directory()
        else:
            self.compare_two_directories()

    def update_progress(self, current, total, status_text):
        progress = (current / total * 100) if total > 0 else 0
        self.progress_var.set(progress)
        self.processing_label.config(text=status_text)
        self.root.update_idletasks()

    def compare_single_directory(self):
        dir1 = self.dir1.get()
        files = []
        hash_map = {}
        
        # Count total files first
        total_files = sum(len(files) for _, _, files in os.walk(dir1))
        processed_files = 0
        
        # Scan directory and calculate hashes
        for root, _, filenames in os.walk(dir1):
            if not self.include_subfolders.get() and root != dir1:
                continue
                
            for filename in filenames:
                filepath = os.path.join(root, filename)
                processed_files += 1
                self.update_progress(processed_files, total_files, 
                                   f"Processing file {processed_files} of {total_files}: {filename}")
                try:
                    file_hash = self.get_file_hash(filepath)
                    file_info = {
                        'path': filepath,
                        'name': filename,
                        'size': os.path.getsize(filepath)
                    }
                    files.append(file_info)
                    
                    # Group files by hash instead of name
                    if file_hash in hash_map:
                        hash_map[file_hash].append(file_info)
                    else:
                        hash_map[file_hash] = [file_info]
                except Exception as e:
                    print(f"Error processing {filepath}: {str(e)}")
        
        # Find duplicates by checking hash groups
        self.matches = []
        for file_group in hash_map.values():
            if len(file_group) > 1:  # If multiple files have the same hash
                first_file = file_group[0]
                for other_file in file_group[1:]:
                    if os.path.getsize(first_file['path']) == os.path.getsize(other_file['path']):
                        self.matches.append({
                            'file1': first_file['path'],
                            'file2': other_file['path'],
                            'is_image': first_file['path'].lower().endswith(self.supported_types['images']),
                            'name1': first_file['name'],
                            'name2': other_file['name']
                        })

        # Update UI
        self.root.after(0, self.show_comparison)

    def compare_two_directories(self):
        dir1, dir2 = self.dir1.get(), self.dir2.get()
        files1 = []
        files2_map = {}
        
        # Count total files
        total_files = sum(len(files) for _, _, files in os.walk(dir1))
        total_files += sum(len(files) for _, _, files in os.walk(dir2))
        processed_files = 0
        
        # First directory scan
        self.update_progress(0, total_files, "Scanning first directory...")
        for root, _, files in os.walk(dir1):
            for filename in files:
                filepath = os.path.join(root, filename)
                processed_files += 1
                self.update_progress(processed_files, total_files, 
                                   f"Processing file {processed_files} of {total_files}: {filename}")
                try:
                    file_hash = self.get_file_hash(filepath)
                    files1.append({
                        'path': filepath,
                        'hash': file_hash,
                        'name': filename,
                        'size': os.path.getsize(filepath)
                    })
                except Exception as e:
                    print(f"Error processing {filepath}: {str(e)}")
        
        total_files = len(files1)
        self.progress_var.set(0)
        
        # Build hash map for files2 for faster lookup
        files2_map = {}
        self.update_progress(0, total_files, "Building hash map for second directory...")
        for root, _, files in os.walk(dir2):
            for filename in files:
                filepath = os.path.join(root, filename)
                processed_files += 1
                self.update_progress(processed_files, total_files, 
                                   f"Processing file {processed_files} of {total_files}: {filename}")
                try:
                    file_hash = self.get_file_hash(filepath)
                    if file_hash in files2_map:
                        files2_map[file_hash].append(filepath)
                    else:
                        files2_map[file_hash] = [filepath]
                except Exception as e:
                    print(f"Error processing {filepath}: {str(e)}")
        
        # Compare files by hash
        for i, file1 in enumerate(files1):
            self.progress_var.set((i + 1) / total_files * 100)
            try:
                if file1['hash'] in files2_map:
                    for filepath2 in files2_map[file1['hash']]:
                        if os.path.getsize(filepath2) == file1['size']:  # Double check size
                            self.matches.append({
                                'file1': file1['path'],
                                'file2': filepath2,
                                'is_image': file1['path'].lower().endswith(self.supported_types['images']),
                                'name1': file1['name'],
                                'name2': os.path.basename(filepath2)
                            })
                            break  # Found a match, no need to check other files with same hash
            except Exception as e:
                print(f"Error comparing {file1['path']}: {str(e)}")

        # Update UI
        self.root.after(0, self.show_comparison)
    
    def show_comparison(self):
        # Clear progress bar and processing message
        self.progress_bar.pack_forget()
        self.processing_label.pack_forget()
        
        if not self.matches:
            self.total_matches.set("No matching files found!")
            self.index_label.config(text="")
            messagebox.showinfo("Results", "No matching files found!")
            return
        
        self.total_matches.set(f"Found {len(self.matches)} matching files")
        self.show_current_pair()

    def show_current_pair(self):
        if not self.matches:
            self.index_label.config(text="")
            return
            
        match = self.matches[self.current_index]
        self.index_label.config(text=f"Viewing file {self.current_index + 1} of {len(self.matches)}")
        
        try:
            if match['is_image']:
                self.display_images(match)
            else:
                self.display_file_info(match)
        except Exception as e:
            print(f"Error displaying files: {str(e)}")

    def display_images(self, match):
        # Handle HEIC files
        img1 = self.load_image(match['file1'])
        img2 = self.load_image(match['file2'])
        
        # Calculate size based on frame width
        frame_width = self.comparison_frame.winfo_width()
        target_size = (min(400, frame_width // 2 - 20), min(400, frame_width // 2 - 20))
        
        # Set fixed size for images
        img1.thumbnail(target_size)
        img2.thumbnail(target_size)
        
        # Create white background
        bg1 = Image.new('RGB', target_size, 'white')
        bg2 = Image.new('RGB', target_size, 'white')
        
        # Paste images centered on white background
        offset1 = ((target_size[0] - img1.size[0]) // 2, (target_size[1] - img1.size[1]) // 2)
        offset2 = ((target_size[0] - img2.size[0]) // 2, (target_size[1] - img2.size[1]) // 2)
        bg1.paste(img1, offset1)
        bg2.paste(img2, offset2)
        
        photo1 = ImageTk.PhotoImage(bg1)
        photo2 = ImageTk.PhotoImage(bg2)
        
        # Add filename labels above images
        file1_text = f"File: {self.get_display_path(match['file1'])}"
        file2_text = f"File: {self.get_display_path(match['file2'])}"
        
        self.img_label1.configure(image=photo1, compound='top', text=file1_text)
        self.img_label2.configure(image=photo2, compound='top', text=file2_text)
        
        # Keep references
        self.img_label1.image = photo1
        self.img_label2.image = photo2
    
    def get_display_path(self, filepath):
        if self.display_full_path.get():
            return filepath
        
        # Get last two parts of the path
        parts = Path(filepath).parts
        if len(parts) <= 2:
            return filepath
        return str(Path(*parts[-2:]))  # Join last folder and filename

    def display_file_info(self, match):
        # Update file info display to show both filenames
        file1_path = self.get_display_path(match['file1'])
        file2_path = self.get_display_path(match['file2'])
        
        file1_info = (f"Name: {match['name1']}\n"
                     f"Location: {file1_path}\n"
                     f"Size: {self.get_file_size(match['file1'])}\n"
                     f"Type: {self.get_file_type(match['file1'])}")
        
        file2_info = (f"Name: {match['name2']}\n"
                     f"Location: {file2_path}\n"
                     f"Size: {self.get_file_size(match['file2'])}\n"
                     f"Type: {self.get_file_type(match['file2'])}")
        
        self.img_label1.configure(image='', text=file1_info)
        self.img_label2.configure(image='', text=file2_info)

    def load_image(self, filepath):
        try:
            if filepath.lower().endswith('.heic'):
                import pillow_heif
                heif_file = pillow_heif.read_heif(filepath)
                return Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                )
            return Image.open(filepath)
        except (UnidentifiedImageError, ImportError, Exception) as e:
            print(f"Error loading image {filepath}: {str(e)}")
            # Return a blank image if loading fails
            return Image.new('RGB', (400, 400), 'lightgray')

    def get_file_size(self, filepath):
        size = os.path.getsize(filepath)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def get_file_type(self, filepath):
        return os.path.splitext(filepath)[1].upper()[1:]

    def open_file(self, directory):
        if not self.matches or len(self.matches) <= self.current_index:
            return
        
        match = self.matches[self.current_index]
        file_path = match['file1'] if directory == "dir1" else match['file2']
        
        try:
            import subprocess
            import platform
            
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")

    def delete_single_image(self, directory):
        if not self.matches or len(self.matches) <= self.current_index:
            return
            
        match = self.matches[self.current_index]
        file_path = match['file1'] if directory == "dir1" else match['file2']
        dir_name = "Directory 1" if directory == "dir1" else "Directory 2"
        
        if messagebox.askyesno("Confirm Deletion", 
                             f"Are you sure you want to delete this file?\n\n"
                             f"Location: {self.get_display_path(file_path)}\n"
                             f"Full path: {file_path}"):
            try:
                os.remove(file_path)
                # Remove success popup
                self.matches.pop(self.current_index)
                if self.matches:
                    if self.current_index >= len(self.matches):
                        self.current_index = len(self.matches) - 1
                    self.show_current_pair()
                else:
                    self.total_matches.set("No matching files remaining")
                    self.img_label1.configure(image='')
                    self.img_label2.configure(image='')
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file: {str(e)}")

    def delete_all_duplicates(self, directory):
        if not self.matches:
            return
            
        dir_name = "Directory 1" if directory == "dir1" else "Directory 2"
        if messagebox.askyesno("Confirm Deletion", 
                             f"Are you sure you want to delete ALL duplicate files from {dir_name}?\n"
                             f"This will keep files in {('Directory 2' if directory == 'dir1' else 'Directory 1')} "
                             f"and cannot be undone!"):
            deleted = 0
            errors = []
            
            for match in self.matches[:]:
                file_path = match['file1'] if directory == "dir1" else match['file2']
                try:
                    os.remove(file_path)
                    deleted += 1
                    self.matches.remove(match)
                except Exception as e:
                    errors.append(f"Error deleting {file_path}: {str(e)}")
            
            if self.matches:
                if self.current_index >= len(self.matches):
                    self.current_index = len(self.matches) - 1
                self.show_current_pair()
            else:
                self.total_matches.set("No matching files remaining")
                self.img_label1.configure(image='', text='')
                self.img_label2.configure(image='', text='')
            
            # Only show error message if there were errors
            if errors:
                message = f"Successfully deleted {deleted} files."
                message += f"\n\nErrors occurred while deleting {len(errors)} files:"
                for error in errors[:5]:
                    message += f"\n- {error}"
                if len(errors) > 5:
                    message += "\n..."
                messagebox.showerror("Deletion Errors", message)
            
            self.total_matches.set(f"Remaining matches: {len(self.matches)}")

    def show_previous(self):
        if self.matches and self.current_index > 0:
            self.current_index -= 1
            self.show_current_pair()

    def show_next(self):
        if self.matches and self.current_index < len(self.matches) - 1:
            self.current_index += 1
            self.show_current_pair()

def main():
    root = tk.Tk()
    app = FileComparisonUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
