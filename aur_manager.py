import tkinter as tk
from tkinter import ttk, messagebox
import requests
import subprocess
import json
from threading import Thread
import os
import sys
from ttkthemes import ThemedTk

class PasswordDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.password = None
        
        # Window settings
        self.title("Authentication Required")
        self.geometry("400x200")
        self.resizable(False, False)
        
        # Configure dark theme colors
        self.configure(bg='#2e2e2e')
        
        # Make it modal
        self.transient(parent)
        self.grab_set()
        
        # Main container with padding
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # Icon and header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(0, 20))
        
        # Lock icon (unicode character)
        lock_label = ttk.Label(
            header_frame,
            text="🔒",
            font=('Helvetica', 24),
            foreground='white'
        )
        lock_label.pack(side='left', padx=(0, 10))
        
        # Header text
        header_label = ttk.Label(
            header_frame,
            text="Authentication Required",
            font=('Helvetica', 12, 'bold'),
            foreground='white'
        )
        header_label.pack(side='left', fill='x')
        
        # Password entry frame
        entry_frame = ttk.Frame(main_frame)
        entry_frame.pack(fill='x', pady=10)
        
        password_label = ttk.Label(
            entry_frame,
            text="Enter sudo password:",
            foreground='white'
        )
        password_label.pack(anchor='w', pady=(0, 5))
        
        self.password_entry = ttk.Entry(
            entry_frame,
            show="•",  # Use bullet character instead of asterisk
            font=('Helvetica', 10)
        )
        self.password_entry.pack(fill='x')
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(20, 0))
        
        cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel,
            style='Secondary.TButton'
        )
        cancel_button.pack(side='right', padx=(5, 0))
        
        ok_button = ttk.Button(
            button_frame,
            text="OK",
            command=self.ok,
            style='Accent.TButton'
        )
        ok_button.pack(side='right')
        
        # Focus the password entry
        self.password_entry.focus_set()
        
        # Bind Enter key to OK button and Escape to Cancel
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())
        
        # Center the dialog on parent
        self.center_on_parent()
        
    def center_on_parent(self):
        parent = self.master
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
    def ok(self):
        self.password = self.password_entry.get()
        self.destroy()
        
    def cancel(self):
        self.password = None
        self.destroy()

class AURManager:
    def __init__(self, root):
        self.root = root
        self.root.title("AUR Package Manager")
        self.root.geometry("1000x700")  # Larger default size
        
        # Apply dark theme
        style = ttk.Style()
        style.theme_use('equilux')  # Dark theme
        
        # Configure colors and styles
        self.root.configure(bg='#464646')  # Dark background
        style.configure('Treeview', 
                       rowheight=25,
                       background="#2e2e2e",
                       fieldbackground="#2e2e2e",
                       foreground="white")
        style.configure('TButton', padding=6)
        style.configure('Header.TLabel', 
                       font=('Helvetica', 12, 'bold'),
                       foreground='white')
        style.configure('TNotebook', 
                       background='#464646',
                       tabmargins=[2, 5, 2, 0])
        style.configure('TNotebook.Tab', 
                       padding=[10, 2],
                       background='#2e2e2e',
                       foreground='white')
        style.map('TNotebook.Tab',
                 background=[('selected', '#464646')],
                 foreground=[('selected', 'white')])
        style.configure('Treeview.Heading',
                       background="#2e2e2e",
                       foreground="white")
        
        # Configure selection colors
        style.map('Treeview',
                 background=[('selected', '#0066cc')],
                 foreground=[('selected', 'white')])

        # Create cache directory if it doesn't exist
        self.cache_dir = os.path.expanduser("~/.cache/aur-manager")
        os.makedirs(self.cache_dir, exist_ok=True)

        # Get initially installed packages
        self.installed_packages = self.get_installed_packages()
        
        # Initialize cache
        self.aur_cache = {}
        self.load_cache()

        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill='both', expand=True)

        # Create notebook in main container instead of root
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Add terminal output frame
        self.terminal_visible = tk.BooleanVar(value=False)
        self.setup_terminal_output()

        # Search tab
        self.search_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.search_tab, text='Search')

        # Updates tab
        self.updates_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.updates_tab, text='Updates')

        # Setup search tab
        self.setup_search_tab()
        # Setup updates tab
        self.setup_updates_tab()

        # Add styles for the password dialog
        style.configure('Secondary.TButton', padding=6)
        style.configure('Dialog.TLabel', foreground='white')

    def setup_updates_tab(self):
        # Updates frame with padding
        self.updates_frame = ttk.Frame(self.updates_tab, padding="20")
        self.updates_frame.pack(fill='both', expand=True)

        # Title
        title_label = ttk.Label(
            self.updates_frame,
            text="System Updates",
            style='Header.TLabel'
        )
        title_label.pack(fill='x', pady=(0, 20))

        # Buttons frame
        buttons_frame = ttk.Frame(self.updates_frame)
        buttons_frame.pack(fill='x', pady=(0, 10))

        self.check_updates_button = ttk.Button(
            buttons_frame,
            text="Check for Updates",
            command=self.check_updates,
            style='Accent.TButton'
        )
        self.check_updates_button.pack(side='left', padx=5)

        self.update_all_button = ttk.Button(
            buttons_frame,
            text="Update All",
            command=self.update_all
        )
        self.update_all_button.pack(side='left', padx=5)

        # Updates treeview with modern styling
        self.updates_tree = ttk.Treeview(
            self.updates_frame,
            columns=("Name", "Current Version", "New Version", "Source"),
            show="headings",
            style='Treeview'
        )
        
        # Configure modern headers
        for col in ("Name", "Current Version", "New Version", "Source"):
            self.updates_tree.heading(col, text=col, anchor='w')

        self.updates_tree.column("Name", width=200)
        self.updates_tree.column("Current Version", width=200)
        self.updates_tree.column("New Version", width=200)
        self.updates_tree.column("Source", width=150)

        self.updates_tree.pack(fill='both', expand=True)

        # Modern scrollbar for updates
        updates_scrollbar = ttk.Scrollbar(
            self.updates_frame,
            orient="vertical",
            command=self.updates_tree.yview
        )
        updates_scrollbar.pack(side='right', fill='y')
        self.updates_tree.configure(yscrollcommand=updates_scrollbar.set)

    def is_git_package(self, package_name):
        return package_name.endswith('-git')

    def check_git_package_update(self, package_name, current_version):
        cache_dir = os.path.join(self.cache_dir, package_name)
        
        try:
            # Check if we have a cached clone
            if os.path.exists(cache_dir):
                # Update existing clone
                subprocess.run(["git", "fetch"], cwd=cache_dir, check=True)
            else:
                # Clone the repository
                subprocess.run(["git", "clone", f"https://aur.archlinux.org/{package_name}.git", cache_dir], 
                             check=True)
            
            # Run makepkg --printsrcinfo to get the new version
            result = subprocess.run(
                ["makepkg", "--printsrcinfo"],
                capture_output=True,
                text=True,
                check=True,
                cwd=cache_dir
            )
            
            # Parse the output to get the new version
            for line in result.stdout.splitlines():
                if line.startswith('pkgver ='):
                    new_version = line.split('=')[1].strip()
                    return new_version != current_version
                    
            return False
        except Exception as e:
            print(f"Error checking git package {package_name}: {str(e)}")
            return False

    def check_updates(self):
        # Clear existing items
        for item in self.updates_tree.get_children():
            self.updates_tree.delete(item)

        self.log_to_terminal("Checking for updates...")
        
        # Check system updates
        try:
            # Sync databases first
            self.log_to_terminal("\nSyncing package databases...")
            self.run_sudo_command(["pacman", "-Sy"])
            
            # Check for updates
            self.log_to_terminal("Checking system packages...")
            result = subprocess.run(
                ["pacman", "-Qu"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        name, current_version, _, new_version = line.split()
                        self.updates_tree.insert("", tk.END, values=(
                            name,
                            current_version,
                            new_version,
                            "System"
                        ))
                        self.log_to_terminal(f"Found update: {name} ({current_version} → {new_version})")
        except subprocess.CalledProcessError:
            self.log_to_terminal("No system updates found")

        # Check AUR updates
        try:
            # Get installed AUR packages
            self.log_to_terminal("\nChecking AUR packages...")
            aur_packages = {}
            result = subprocess.run(
                ["pacman", "-Qm"],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.splitlines():
                if line.strip():
                    name, version = line.split()
                    aur_packages[name] = version

            if not aur_packages:
                self.log_to_terminal("No AUR packages installed")
                return

            # Batch request for AUR package info
            package_names = list(aur_packages.keys())
            if package_names:
                try:
                    self.log_to_terminal(f"Checking {len(package_names)} AUR packages...")
                    response = requests.get(
                        "https://aur.archlinux.org/rpc/",
                        params={
                            "v": "5",
                            "type": "info",
                            "arg[]": package_names
                        }
                    )
                    data = response.json()
                    
                    # Update cache with new information
                    for pkg in data.get("results", []):
                        self.aur_cache[pkg["Name"]] = pkg
                    self.save_cache()
                    
                except Exception as e:
                    self.log_to_terminal(f"Error updating AUR cache: {e}")

            # Check each AUR package
            for name, current_version in aur_packages.items():
                try:
                    if self.is_git_package(name):
                        self.log_to_terminal(f"Checking git package: {name}")
                        if self.check_git_package_update(name, current_version):
                            self.updates_tree.insert("", tk.END, values=(
                                name,
                                current_version,
                                "git-latest",
                                "AUR-git"
                            ))
                            self.log_to_terminal(f"Update available for {name}")
                    else:
                        pkg_info = self.aur_cache.get(name)
                        if pkg_info:
                            aur_version = pkg_info["Version"]
                            
                            try:
                                vercmp_result = subprocess.run(
                                    ["vercmp", aur_version, current_version],
                                    capture_output=True,
                                    text=True,
                                    check=True
                                )
                                
                                if int(vercmp_result.stdout.strip()) > 0:
                                    self.updates_tree.insert("", tk.END, values=(
                                        name,
                                        current_version,
                                        aur_version,
                                        "AUR"
                                    ))
                                    self.log_to_terminal(f"Found update: {name} ({current_version} → {aur_version})")
                            except subprocess.CalledProcessError:
                                continue

                except Exception as e:
                    self.log_to_terminal(f"Error checking {name}: {str(e)}")
                    continue

        except subprocess.CalledProcessError as e:
            self.log_to_terminal("Error: Failed to check AUR updates")
            messagebox.showerror("Error", "Failed to check AUR updates")

        self.log_to_terminal("\nUpdate check complete!")

    def update_all(self):
        updates = []
        aur_updates = []
        
        for item in self.updates_tree.get_children():
            values = self.updates_tree.item(item)["values"]
            if values[3] == "System":
                updates.append(values[0])
            else:
                aur_updates.append(values[0])

        if not updates and not aur_updates:
            messagebox.showinfo("Info", "No updates available")
            return

        if messagebox.askyesno("Confirm", "Do you want to install all updates?"):
            def update_thread():
                try:
                    # System updates
                    if updates:
                        self.log_to_terminal("\nInstalling system updates...")
                        self.run_sudo_command(["pacman", "-Su", "--noconfirm"])
                        self.log_to_terminal("System updates completed")

                    # AUR updates
                    if aur_updates:
                        self.log_to_terminal("\nInstalling AUR updates...")
                        for package in aur_updates:
                            try:
                                self.log_to_terminal(f"\nUpdating {package}...")
                                self.log_to_terminal("Cloning repository...")
                                self.run_with_output(
                                    ["git", "clone", f"https://aur.archlinux.org/{package}.git"],
                                    check=True
                                )
                                
                                self.log_to_terminal("Building package...")
                                self.run_with_output(
                                    ["makepkg", "--noconfirm"],
                                    cwd=package,
                                    check=True
                                )
                                
                                pkg_files = [f for f in os.listdir(package) 
                                           if f.endswith('.pkg.tar.zst')]
                                
                                if pkg_files:
                                    self.log_to_terminal("Installing package...")
                                    self.run_sudo_command(
                                        ["pacman", "-U", "--noconfirm", pkg_files[0]],
                                        cwd=package
                                    )
                                    self.log_to_terminal(f"{package} updated successfully")
                            except Exception as e:
                                self.log_to_terminal(f"Error updating {package}: {str(e)}")
                            finally:
                                subprocess.run(["rm", "-rf", package])

                    self.log_to_terminal("\nAll updates completed!")
                    messagebox.showinfo("Success", "All updates installed successfully")
                    self.root.after(0, self.check_updates)
                except Exception as e:
                    self.log_to_terminal(f"\nError during update: {str(e)}")
                    messagebox.showerror("Error", f"Failed to install updates: {str(e)}")

            Thread(target=update_thread).start()

    def setup_search_tab(self):
        # Search frame
        self.main_frame = ttk.Frame(self.search_tab, padding="20")
        self.main_frame.pack(fill='both', expand=True)

        # Title
        title_label = ttk.Label(self.main_frame, text="Package Search", style='Header.TLabel')
        title_label.pack(fill='x', pady=(0, 20))

        # Search controls frame with modern styling
        self.search_frame = ttk.Frame(self.main_frame)
        self.search_frame.pack(fill='x', pady=5)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            self.search_frame, 
            textvariable=self.search_var,
            font=('Helvetica', 10),
            width=50
        )
        self.search_entry.pack(side='left', fill='x', expand=True, padx=5)

        self.search_button = ttk.Button(
            self.search_frame,
            text="Search",
            command=self.search_packages,
            style='Accent.TButton'
        )
        self.search_button.pack(side='left', padx=5)

        # Results frame
        self.results_frame = ttk.Frame(self.main_frame)
        self.results_frame.pack(fill='both', expand=True, pady=10)

        # Treeview with modern styling
        self.tree = ttk.Treeview(
            self.results_frame,
            columns=("Status", "Name", "Version", "Source", "Description"),
            show="headings",
            style='Treeview'
        )
        
        # Configure modern headers
        for col in ("Status", "Name", "Version", "Source", "Description"):
            self.tree.heading(col, text=col, anchor='w')
        
        # Set column widths
        self.tree.column("Status", width=30, stretch=False)
        self.tree.column("Name", width=200)
        self.tree.column("Version", width=120)
        self.tree.column("Source", width=100)
        self.tree.column("Description", width=500)
        
        self.tree.pack(side='left', fill='both', expand=True)

        # Modern scrollbar
        self.scrollbar = ttk.Scrollbar(
            self.results_frame,
            orient=tk.VERTICAL,
            command=self.tree.yview
        )
        self.scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        # Action buttons frame
        self.buttons_frame = ttk.Frame(self.main_frame)
        self.buttons_frame.pack(fill='x', pady=10)

        self.install_button = ttk.Button(
            self.buttons_frame,
            text="Install",
            command=self.install_package,
            style='Accent.TButton'
        )
        self.install_button.pack(side='left', padx=5)

        self.remove_button = ttk.Button(
            self.buttons_frame,
            text="Remove",
            command=self.remove_package
        )
        self.remove_button.pack(side='left', padx=5)

        # Bind Enter key to search
        self.search_entry.bind('<Return>', lambda e: self.search_packages())

    def get_installed_packages(self):
        try:
            result = subprocess.run(["pacman", "-Q"], capture_output=True, text=True, check=True)
            packages = {}
            for line in result.stdout.splitlines():
                if line.strip():
                    name, version = line.split()
                    packages[name] = version
            return packages
        except subprocess.CalledProcessError:
            return {}

    def search_packages(self):
        query = self.search_var.get()
        if not query:
            return

        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Refresh installed packages list
        self.installed_packages = self.get_installed_packages()

        # Search official repositories
        try:
            repo_results = subprocess.run(
                ["pacman", "-Ss", query],
                capture_output=True,
                text=True
            )
            
            if repo_results.returncode == 0:
                # Parse pacman search results
                lines = repo_results.stdout.strip().split('\n')
                i = 0
                while i < len(lines):
                    if lines[i].startswith(' '):  # This is a description line
                        i += 1
                        continue
                        
                    pkg_line = lines[i]
                    desc_line = lines[i + 1] if i + 1 < len(lines) else ""
                    
                    # Parse package line
                    # Format: repo/name version [installed]
                    parts = pkg_line.split()
                    repo_name = parts[0]
                    repo, name = repo_name.split('/')
                    version = parts[1]
                    description = desc_line.strip()
                    
                    status = "✓" if name in self.installed_packages else ""
                    
                    self.tree.insert("", tk.END, values=(
                        status,
                        name,
                        version,
                        repo,
                        description
                    ))
                    
                    i += 2

        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to search repositories: {str(e)}")

        # Search AUR
        url = f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={query}"
        try:
            response = requests.get(url)
            data = response.json()
            
            if data["resultcount"] > 0:
                for package in data["results"]:
                    name = package["Name"]
                    status = "✓" if name in self.installed_packages else ""
                    self.tree.insert("", tk.END, values=(
                        status,
                        name,
                        package["Version"],
                        "AUR",
                        package["Description"]
                    ))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to search AUR: {str(e)}")

    def run_sudo_command(self, cmd, **kwargs):
        """Run a command with sudo using GUI password prompt"""
        password_dialog = PasswordDialog(self.root)
        self.root.wait_window(password_dialog)
        
        if password_dialog.password is None:
            raise subprocess.CalledProcessError(1, cmd, "Authentication cancelled")
            
        process = subprocess.Popen(
            ["sudo", "-S"] + cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **kwargs
        )
        
        self.log_to_terminal(f"Running: sudo {' '.join(cmd)}")
        stdout, stderr = process.communicate(input=password_dialog.password + "\n")
        
        if stdout:
            self.log_to_terminal(stdout)
        if stderr:
            self.log_to_terminal(stderr)
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, stderr)
        
        return stdout

    def remove_package(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a package to remove")
            return

        package_name = self.tree.item(selected[0])["values"][1]
        
        if messagebox.askyesno("Confirm", f"Are you sure you want to remove {package_name}?"):
            try:
                self.run_sudo_command(["pacman", "-R", "--noconfirm", package_name])
                messagebox.showinfo("Success", f"Package {package_name} removed successfully")
                # Refresh the display
                self.search_packages()
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Failed to remove package: {str(e)}")

    def install_package(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a package to install")
            return

        values = self.tree.item(selected[0])["values"]
        package_name = values[1]
        source = values[3]
        
        def install_thread():
            try:
                if source == "AUR":
                    # AUR installation process
                    self.log_to_terminal(f"\nCloning {package_name} from AUR...")
                    self.run_with_output(
                        ["git", "clone", f"https://aur.archlinux.org/{package_name}.git"],
                        check=True
                    )
                    
                    self.log_to_terminal("\nBuilding package...")
                    self.run_with_output(
                        ["makepkg", "--noconfirm"],
                        cwd=package_name,
                        check=True
                    )
                    
                    pkg_files = [f for f in os.listdir(package_name) 
                               if f.endswith('.pkg.tar.zst')]
                    
                    if not pkg_files:
                        raise subprocess.CalledProcessError(1, "makepkg", "No package file found")
                    
                    self.log_to_terminal("\nInstalling package...")
                    self.run_sudo_command(["pacman", "-U", "--noconfirm", pkg_files[0]], 
                                        cwd=package_name)
                else:
                    # Official repo installation
                    self.run_sudo_command(["pacman", "-S", "--noconfirm", package_name])
                
                messagebox.showinfo("Success", f"Package {package_name} installed successfully")
                self.root.after(0, self.search_packages)
            except subprocess.CalledProcessError as e:
                self.log_to_terminal(f"\nError: {str(e)}")
                messagebox.showerror("Error", f"Failed to install package: {str(e)}")
            finally:
                if source == "AUR":
                    # Cleanup AUR files
                    subprocess.run(["rm", "-rf", package_name])

        Thread(target=install_thread).start()

    def load_cache(self):
        """Load cached AUR package information"""
        cache_file = os.path.join(self.cache_dir, "aur_cache.json")
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    self.aur_cache = json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
            self.aur_cache = {}

    def save_cache(self):
        """Save AUR package information to cache"""
        cache_file = os.path.join(self.cache_dir, "aur_cache.json")
        try:
            with open(cache_file, 'w') as f:
                json.dump(self.aur_cache, f)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def setup_terminal_output(self):
        # Terminal toggle frame
        self.terminal_toggle_frame = ttk.Frame(self.main_container)
        self.terminal_toggle_frame.pack(fill='x', padx=10)

        self.terminal_toggle = ttk.Checkbutton(
            self.terminal_toggle_frame,
            text="Show Terminal Output",
            command=self.toggle_terminal,
            variable=self.terminal_visible
        )
        self.terminal_toggle.pack(side='left')

        # Terminal output frame
        self.terminal_frame = ttk.Frame(self.main_container)
        
        # Terminal output text widget
        self.terminal_output = tk.Text(
            self.terminal_frame,
            height=10,
            bg='#1e1e1e',
            fg='#ffffff',
            font=('Consolas', 10),
            wrap=tk.WORD
        )
        self.terminal_output.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Terminal scrollbar
        terminal_scrollbar = ttk.Scrollbar(
            self.terminal_frame,
            orient="vertical",
            command=self.terminal_output.yview
        )
        terminal_scrollbar.pack(side='right', fill='y')
        self.terminal_output.configure(yscrollcommand=terminal_scrollbar.set)

    def toggle_terminal(self):
        if self.terminal_visible.get():
            self.terminal_frame.pack(fill='both', expand=False, padx=10, pady=5)
        else:
            self.terminal_frame.pack_forget()

    def log_to_terminal(self, text):
        self.terminal_output.insert(tk.END, f"{text}\n")
        self.terminal_output.see(tk.END)

    def run_with_output(self, cmd, **kwargs):
        """Run a command and capture output to terminal"""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            **kwargs
        )

        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                self.root.after(0, self.log_to_terminal, output.strip())
        
        return process.poll()

if __name__ == "__main__":
    root = ThemedTk(theme="equilux")
    app = AURManager(root)
    root.mainloop() 