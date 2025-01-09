import sys
import os
import subprocess
import time
from threading import Thread, Event
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTreeWidget, QTreeWidgetItem, QLabel,
    QTabWidget, QCheckBox, QTextEdit, QDialog, QScrollArea,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread, QTimer
from PyQt6.QtGui import QFont, QIcon

class OutputSignals(QObject):
    output = pyqtSignal(str)

class PasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.password = None
        self.setup_ui()
        
        self.password_input.returnPressed.connect(self.accept)

    def setup_ui(self):
        self.setWindowTitle("Authentication Required")
        self.setFixedSize(400, 180)
        self.setStyleSheet("""
            QDialog {
                background-color: #2e2e2e;
            }
            QLabel {
                color: white;
            }
            QLineEdit {
                padding: 8px;
                background-color: #3e3e3e;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                min-height: 20px;
            }
            QPushButton {
                padding: 8px 16px;
                min-width: 80px;
                background-color: #0066cc;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0077dd;
            }
            QPushButton[secondary="true"] {
                background-color: #464646;
            }
            QPushButton[secondary="true"]:hover {
                background-color: #565656;
            }
            QCheckBox {
                color: white;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()
        icon_label = QLabel("🔑")
        icon_label.setFont(QFont("", 16))
        icon_label.setStyleSheet("color: white; margin-right: 10px;")
        header_layout.addWidget(icon_label)

        title_label = QLabel("Authentication Required")
        title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        password_label = QLabel("Enter sudo password:")
        layout.addWidget(password_label)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(30)
        layout.addWidget(self.password_input)

        self.remember_checkbox = QCheckBox("Remember password for 5 minutes")
        layout.addWidget(self.remember_checkbox)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("secondary", True)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        self.password_input.setFocus()

    def get_password(self):
        if self.exec() == QDialog.DialogCode.Accepted:
            password = self.password_input.text()
            if self.remember_checkbox.isChecked():
                return password, True
            return password, False
        return None, False

class PackageWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    output = pyqtSignal(str)
    sudo_command = pyqtSignal(list, dict)
    package_found = pyqtSignal(dict)
    sudo_response = None
    sudo_event = None

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function
        self.sudo_event = Event()
        self.sudo_response = None
        self._is_running = False
        self._cleanup_lock = Event()

    def run_sudo_command(self, cmd, **kwargs):
        self.sudo_command.emit(cmd, kwargs)
        self.sudo_event.wait()
        self.sudo_event.clear()
        if isinstance(self.sudo_response, Exception):
            raise self.sudo_response
        return self.sudo_response

    def set_sudo_response(self, response):
        self.sudo_response = response
        self.sudo_event.set()

    def run(self):
        try:
            self._is_running = True
            self._cleanup_lock.clear()
            if self.function:
                self.function(self)
            else:
                self.error.emit("Function is not set.")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._is_running = False
            self.sudo_event.set()
            self._cleanup_lock.set()
            self.finished.emit()

    def stop(self):
        """Safely stop the worker thread"""
        if self._is_running:
            self._is_running = False
            self.sudo_event.set()
            self._cleanup_lock.wait()
            self.wait()

    def __del__(self):
        """Ensure proper cleanup on deletion"""
        self.stop()

class AURManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
        self.installed_packages = self.get_installed_packages()
        
        self.output_signals = OutputSignals()
        self.output_signals.output.connect(self.log_to_terminal)

        self.current_worker = None
        self._worker_lock = Event()

        self.sudo_password = None
        self.sudo_timestamp = None
        self.sudo_timeout = 300

    def setup_ui(self):
        self.setWindowTitle("Oracle - AUR Helper Wrapper")
        self.setMinimumSize(1000, 700)
        
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2e2e2e;
                color: white;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background-color: #3e3e3e;
                color: white;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0066cc;
            }
            QTreeWidget {
                background-color: #1e1e1e;
                alternate-background-color: #262626;
                border: none;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #0066cc;
            }
            QPushButton {
                padding: 8px 16px;
                background-color: #0066cc;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0077dd;
            }
            QLineEdit {
                padding: 8px;
                background-color: #3e3e3e;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QTextEdit {
                background-color: #1e1e1e;
                border: none;
                font-family: 'Consolas', monospace;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.setup_search_tab()
        self.setup_updates_tab()
        self.setup_about_tab()

        self.setup_terminal_output()

    def setup_search_tab(self):
        search_widget = QWidget()
        layout = QVBoxLayout(search_widget)

        title_label = QLabel("Package Search")
        title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search packages...")
        self.search_input.returnPressed.connect(self.search_packages)
        search_layout.addWidget(self.search_input)

        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_packages)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        self.package_tree = QTreeWidget()
        self.package_tree.setHeaderLabels(["Status", "Name", "Version", "Source", "Description"])
        self.package_tree.setAlternatingRowColors(True)
        self.package_tree.setColumnWidth(0, 30)
        self.package_tree.setColumnWidth(1, 200)
        self.package_tree.setColumnWidth(2, 120)
        self.package_tree.setColumnWidth(3, 100)
        layout.addWidget(self.package_tree)

        button_layout = QHBoxLayout()
        install_button = QPushButton("Install")
        install_button.clicked.connect(self.install_package)
        button_layout.addWidget(install_button)

        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self.remove_package)
        button_layout.addWidget(remove_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.tab_widget.addTab(search_widget, "Search")

    def setup_updates_tab(self):
        updates_widget = QWidget()
        layout = QVBoxLayout(updates_widget)

        title_label = QLabel("System Updates")
        title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)

        button_layout = QHBoxLayout()
        check_updates_button = QPushButton("Check for Updates")
        check_updates_button.clicked.connect(self.check_updates)
        button_layout.addWidget(check_updates_button)

        update_all_button = QPushButton("Update All")
        update_all_button.clicked.connect(self.update_all)
        button_layout.addWidget(update_all_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.updates_tree = QTreeWidget()
        self.updates_tree.setHeaderLabels(["Name", "Current Version", "New Version", "Source"])
        self.updates_tree.setAlternatingRowColors(True)
        self.updates_tree.setColumnWidth(0, 200)
        self.updates_tree.setColumnWidth(1, 200)
        self.updates_tree.setColumnWidth(2, 200)
        layout.addWidget(self.updates_tree)

        self.tab_widget.addTab(updates_widget, "Updates")

    def setup_about_tab(self):
        about_widget = QWidget()
        layout = QVBoxLayout(about_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("About Oracle")
        title_label.setFont(QFont("", 16, QFont.Weight.Bold))
        layout.addWidget(title_label)

        author_label = QLabel("Author: 0xGingi")
        author_label.setFont(QFont("", 12))
        layout.addWidget(author_label)

        description = QLabel(
            "Oracle is a wrapper for AUR helpers and Pacman. "
            "It provides an easy way to search, install, and manage packages from both "
            "the official Arch repositories and the Arch User Repository (AUR).\n\n"
        )
        description.setWordWrap(True)
        description.setFont(QFont("", 11))
        layout.addWidget(description)

        layout.addStretch()

        self.tab_widget.addTab(about_widget, "About")

    def setup_terminal_output(self):
        toggle_layout = QHBoxLayout()
        self.terminal_checkbox = QCheckBox("Show Terminal Output")
        self.terminal_checkbox.stateChanged.connect(self.toggle_terminal)
        toggle_layout.addWidget(self.terminal_checkbox)
        toggle_layout.addStretch()
        self.centralWidget().layout().addLayout(toggle_layout)

        self.terminal_frame = QFrame()
        self.terminal_frame.setVisible(False)
        terminal_layout = QVBoxLayout(self.terminal_frame)

        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setMinimumHeight(150)
        terminal_layout.addWidget(self.terminal_output)

        self.centralWidget().layout().addWidget(self.terminal_frame)

    def toggle_terminal(self, state):
        self.terminal_frame.setVisible(state == Qt.CheckState.Checked.value)

    def log_to_terminal(self, text):
        self.terminal_output.append(text)
        self.terminal_output.verticalScrollBar().setValue(
            self.terminal_output.verticalScrollBar().maximum()
        )

    def get_installed_packages(self):
        try:
            result = subprocess.run(
                ["pacman", "-Q"],
                capture_output=True,
                text=True,
                check=True
            )
            packages = {}
            for line in result.stdout.splitlines():
                if line.strip():
                    name, version = line.split()
                    packages[name] = version
            return packages
        except subprocess.CalledProcessError:
            return {}

    def get_cached_sudo_password(self):
        """Check if we have a valid cached sudo password"""
        if self.sudo_password is None:
            return None
            
        if self.sudo_timestamp is None or \
           (time.time() - self.sudo_timestamp) > self.sudo_timeout:
            self.sudo_password = None
            return None
            
        return self.sudo_password

    def cache_sudo_password(self, password):
        """Cache the sudo password temporarily"""
        self.sudo_password = password
        self.sudo_timestamp = time.time()

    def run_sudo_command(self, cmd, **kwargs):
        """Run a command with sudo using GUI password prompt"""
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                password = self.get_cached_sudo_password()
                
                if password is None:
                    dialog = PasswordDialog(self)
                    result = dialog.get_password()
                    
                    if result[0] is None:
                        self.log_to_terminal("Authentication cancelled by user")
                        raise subprocess.CalledProcessError(1, cmd, "Authentication cancelled by user")
                        
                    password = result[0]
                    if result[1]:
                        self.cache_sudo_password(password)
                
                verify_process = subprocess.Popen(
                    ["sudo", "-S", "true"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                verify_stdout, verify_stderr = verify_process.communicate(input=password + "\n")
                
                if verify_process.returncode != 0:
                    if "incorrect password" in verify_stderr.lower():
                        self.sudo_password = None
                        self.sudo_timestamp = None
                        self.log_to_terminal("Incorrect password, please try again")
                        attempt += 1
                        continue
                    else:
                        self.log_to_terminal(f"Sudo verification failed: {verify_stderr}")
                        raise subprocess.CalledProcessError(verify_process.returncode, cmd, verify_stderr)
                
                safe_env = {
                    'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                    'HOME': os.environ.get('HOME', ''),
                    'USER': os.environ.get('USER', ''),
                    'LANG': os.environ.get('LANG', 'C.UTF-8'),
                    'DISPLAY': os.environ.get('DISPLAY', ''),
                    'XAUTHORITY': os.environ.get('XAUTHORITY', '')
                }
                
                if 'env' in kwargs:
                    safe_env.update(kwargs.pop('env'))
                
                process = subprocess.Popen(
                    ["sudo", "-S"] + cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=safe_env,
                    **kwargs
                )
                
                self.log_to_terminal(f"Running: sudo {' '.join(cmd)}")
                stdout, stderr = process.communicate(input=password + "\n")
                
                if stdout:
                    self.log_to_terminal(stdout)
                if stderr:
                    self.log_to_terminal(stderr)
                
                if process.returncode != 0:
                    error_msg = stderr if stderr else stdout if stdout else "Unknown error occurred"
                    self.log_to_terminal(f"Command failed with error: {error_msg}")
                    raise subprocess.CalledProcessError(process.returncode, cmd, error_msg)
                
                return stdout
                
            except subprocess.CalledProcessError as e:
                if "incorrect password" in str(e).lower() and attempt < max_retries - 1:
                    self.sudo_password = None
                    self.sudo_timestamp = None
                    attempt += 1
                    self.log_to_terminal("Incorrect password, please try again")
                    continue
                raise
            except Exception as e:
                self.log_to_terminal(f"Error in sudo command: {str(e)}")
                raise
            
        if attempt >= max_retries:
            self.log_to_terminal("Maximum authentication attempts reached")
            raise subprocess.CalledProcessError(1, cmd, "Maximum authentication attempts reached")

    def run_with_output(self, cmd, **kwargs):
        """Run a command and capture output to terminal"""
        safe_env = {
            'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            'HOME': os.environ.get('HOME', ''),
            'USER': os.environ.get('USER', ''),
            'LANG': os.environ.get('LANG', 'C.UTF-8')
        }
        
        if 'env' in kwargs:
            safe_env.update(kwargs.pop('env'))
            
        kwargs['env'] = safe_env
        
        try:
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
                    self.output_signals.output.emit(output.strip())
            
            return process.poll()
            
        except Exception as e:
            self.log_to_terminal(f"Error in command execution: {str(e)}")
            raise

    def search_packages(self):
        query = self.search_input.text()
        if not query:
            return

        def search_task(worker):
            worker.output.emit(f"\nSearching for: {query}")
            
            # Search official repositories
            try:
                worker.output.emit("Searching official repositories...")
                repo_results = subprocess.run(
                    ["pacman", "-Ss", query],
                    capture_output=True,
                    text=True
                )
                
                if repo_results.returncode == 0:
                    lines = repo_results.stdout.strip().split('\n')
                    for i in range(0, len(lines), 2):
                        if i + 1 >= len(lines):
                            break
                            
                        pkg_line = lines[i]
                        desc_line = lines[i + 1]
                        
                        try:
                            parts = pkg_line.split()
                            repo_name = parts[0]
                            repo, name = repo_name.split('/')
                            version = parts[1]
                            description = desc_line.strip()
                            
                            worker.package_found.emit({
                                'status': "✓" if name in self.installed_packages else "",
                                'name': name,
                                'version': version,
                                'source': repo,
                                'description': description
                            })
                        except Exception as e:
                            worker.output.emit(f"Warning: Could not parse package line: {pkg_line}")

            except subprocess.CalledProcessError as e:
                worker.output.emit(f"Error searching repositories: {str(e)}")

            # Search AUR
            try:
                aur_helper = self.detect_aur_helper()
                if aur_helper:
                    worker.output.emit("Searching AUR...")
                    result = subprocess.run(
                        [*aur_helper, '-Ss', query],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        lines = result.stdout.strip().split('\n')
                        i = 0
                        while i < len(lines):
                            line = lines[i].strip()
                            if not line:
                                i += 1
                                continue
                                
                            try:
                                # Handle different AUR helper output formats
                                if aur_helper[0] == 'yay':
                                    if line.startswith('aur/'):
                                        parts = line.split()
                                        name = parts[0].split('/')[1]
                                        version = parts[1]
                                        description = lines[i + 1].strip() if i + 1 < len(lines) else ""
                                        i += 2
                                    else:
                                        i += 1
                                        continue
                                else:  # Generic format for other helpers
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        name = parts[0].split('/')[-1]
                                        version = parts[1]
                                        description = lines[i + 1].strip() if i + 1 < len(lines) else ""
                                        i += 2
                                    else:
                                        i += 1
                                        continue
                                
                                worker.package_found.emit({
                                    'status': "✓" if name in self.installed_packages else "",
                                    'name': name,
                                    'version': version,
                                    'source': "AUR",
                                    'description': description
                                })
                            except Exception as e:
                                worker.output.emit(f"Warning: Could not parse AUR package line: {line}")
                                i += 1

            except Exception as e:
                worker.output.emit(f"Error searching AUR: {str(e)}")

        self.package_tree.clear()
        worker = PackageWorker(search_task, self)
        worker.output.connect(self.log_to_terminal)
        worker.package_found.connect(self.add_package_to_tree)
        worker.error.connect(lambda e: QMessageBox.critical(self, "Error", f"Search failed: {e}"))
        
        self.start_worker(worker)

    def add_package_to_tree(self, package_info):
        """Add a package to the appropriate tree view"""
        item = QTreeWidgetItem()
        
        if 'new_version' in package_info:
            item.setText(0, package_info['name'])
            item.setText(1, package_info['current_version'])
            item.setText(2, package_info['new_version'])
            item.setText(3, package_info['source'])
            self.updates_tree.addTopLevelItem(item)
        else:
            item.setText(0, package_info['status'])
            item.setText(1, package_info['name'])
            item.setText(2, package_info['version'])
            item.setText(3, package_info['source'])
            item.setText(4, package_info['description'])
            self.package_tree.addTopLevelItem(item)

    def handle_sudo_command(self, cmd, kwargs):
        """Handle sudo commands from worker threads"""
        try:
            if cmd[0] == 'show_dialog':
                reply = QMessageBox.question(
                    self,
                    kwargs.get('title', 'Confirmation'),
                    kwargs.get('message', 'Continue?'),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No if kwargs.get('default_no') else QMessageBox.StandardButton.Yes
                )
                if self.current_worker:
                    self.current_worker.set_sudo_response(reply == QMessageBox.StandardButton.Yes)
            else:
                self.log_to_terminal(f"\nExecuting sudo command: {' '.join(cmd)}")
                result = self.run_sudo_command(cmd, **kwargs)
                if self.current_worker:
                    self.current_worker.set_sudo_response(result)
        except subprocess.CalledProcessError as e:
            self.log_to_terminal(f"Sudo command failed: {str(e)}")
            if self.current_worker:
                self.current_worker.set_sudo_response(e)
        except Exception as e:
            self.log_to_terminal(f"Unexpected error in sudo command: {str(e)}")
            if self.current_worker:
                self.current_worker.set_sudo_response(e)

    def install_package(self):
        selected_items = self.package_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a package to install")
            return

        item = selected_items[0]
        package_name = item.text(1)
        source = item.text(3)

        def install_task(worker):
            try:
                worker.output.emit("\nUpdating package database...")
                try:
                    worker.run_sudo_command(['pacman', '-Sy'])
                except subprocess.CalledProcessError as e:
                    if "Authentication cancelled" in str(e):
                        worker.output.emit("\nInstallation cancelled: Authentication required for database update")
                        return
                    worker.output.emit(f"\nWarning: Failed to update package database: {str(e)}")
                    worker.sudo_command.emit(
                        ['show_dialog'],
                        {
                            'title': "Database Update Failed",
                            'message': "Failed to update package database. Do you want to continue with installation anyway?",
                            'default_no': True
                        }
                    )
                    worker.sudo_event.wait()
                    worker.sudo_event.clear()
                    if not worker.sudo_response:
                        worker.output.emit("\nInstallation cancelled by user")
                        return

                check_official = subprocess.run(
                    ['pacman', '-Si', package_name],
                    capture_output=True,
                    text=True
                )
                
                is_official = check_official.returncode == 0
                
                if is_official:
                    worker.output.emit(f"\nInstalling {package_name} from official repositories...")
                    try:
                        result = worker.run_sudo_command(['pacman', '-S', '--noconfirm', package_name])
                        if result:
                            worker.output.emit(result)
                    except subprocess.CalledProcessError as e:
                        if "Authentication cancelled" in str(e):
                            worker.output.emit("\nInstallation cancelled: Authentication required")
                            return
                        error_msg = e.stderr if e.stderr else e.stdout if e.stdout else str(e)
                        worker.output.emit(f"\nPacman error output:\n{error_msg}")
                        raise Exception(f"Pacman installation failed: {error_msg}")
                    except Exception as e:
                        worker.output.emit(f"\nError installing package: {str(e)}")
                        raise
                else:
                    aur_helper = self.detect_aur_helper()
                    if not aur_helper:
                        raise Exception("No AUR helper found. Please install yay, paru, or another AUR helper.")
                        
                    worker.output.emit(f"\nInstalling {package_name} using {aur_helper[0]}...")
                    try:
                        if aur_helper[0] == 'pamac':
                            worker.run_sudo_command(['pamac', 'install', '--no-confirm', package_name])
                        else:
                            worker.run_sudo_command([*aur_helper, '-S', '--noconfirm', package_name])
                    except subprocess.CalledProcessError as e:
                        if "Authentication cancelled" in str(e):
                            worker.output.emit("\nInstallation cancelled: Authentication required")
                            return
                        worker.output.emit(f"\nError installing package: {str(e)}")
                        raise
                    except Exception as e:
                        worker.output.emit(f"\nError installing package: {str(e)}")
                        raise

                worker.output.emit(f"\n{package_name} installed successfully!")

            except Exception as e:
                worker.output.emit(f"\nError during installation: {str(e)}")
                raise

        worker = PackageWorker(install_task, self)
        worker.output.connect(self.log_to_terminal)
        worker.error.connect(lambda e: QMessageBox.critical(self, "Error", f"Installation failed: {e}"))
        worker.sudo_command.connect(self.handle_sudo_command)
        worker.finished.connect(lambda: self.installation_finished(package_name))
        
        self.start_worker(worker)

    def installation_finished(self, package_name):
        """Handle post-installation tasks"""
        self.installed_packages = self.get_installed_packages()
        self.log_to_terminal(f"\n{package_name} installed successfully")
        
        QMessageBox.information(
            self,
            "Installation Complete",
            f"{package_name} has been installed successfully.\n\n"
            "You can check for updates manually using the Updates tab."
        )

    def safe_check_updates(self):
        """Safely check for updates after ensuring previous workers are cleaned up"""
        if self.current_worker and self.current_worker._is_running:
            QTimer.singleShot(1000, self.safe_check_updates)
            return
        
        self.current_worker = None
        
        self.check_updates()

    def installation_error(self, package_name, error):
        self.log_to_terminal(f"\nError: {error}")
        QMessageBox.critical(self, "Error", f"Failed to install package: {error}")

    def remove_package(self):
        selected_items = self.package_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a package to remove")
            return

        item = selected_items[0]
        package_name = item.text(1)

        try:
            result = subprocess.run(
                ["sudo", "pacman", "-Qi", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            
            required_by = []
            for line in result.stdout.splitlines():
                if line.startswith("Required By"):
                    deps = line.split(":")[1].strip()
                    if deps and deps != "None":
                        required_by = deps.split()
                    break

            if required_by:
                reply = QMessageBox.question(
                    self,
                    "Dependencies Found",
                    f"{package_name} is required by other packages:\n\n{', '.join(required_by)}\n\n"
                    "Do you want to remove it and its dependents?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        self.log_to_terminal(f"\nRemoving {package_name} and its dependents...")
                        self.run_sudo_command(["pacman", "-Rc", "--noconfirm", package_name])
                        self.log_to_terminal(f"\n{package_name} and dependents removed successfully")
                        self.installed_packages = self.get_installed_packages()
                        self.search_packages()
                    except Exception as e:
                        self.log_to_terminal(f"\nError: {str(e)}")
                        QMessageBox.critical(self, "Error", f"Failed to remove package: {str(e)}")
            else:
                reply = QMessageBox.question(
                    self,
                    "Confirm Removal",
                    f"Are you sure you want to remove {package_name}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        self.log_to_terminal(f"\nRemoving {package_name}...")
                        self.run_sudo_command(["pacman", "-R", "--noconfirm", package_name])
                        self.log_to_terminal(f"\n{package_name} removed successfully")
                        self.installed_packages = self.get_installed_packages()
                        self.search_packages()
                    except Exception as e:
                        self.log_to_terminal(f"\nError: {str(e)}")
                        QMessageBox.critical(self, "Error", f"Failed to remove package: {str(e)}")

        except subprocess.CalledProcessError as e:
            reply = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Are you sure you want to remove {package_name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self.log_to_terminal(f"\nRemoving {package_name}...")
                    self.run_sudo_command(["pacman", "-R", "--noconfirm", package_name])
                    self.log_to_terminal(f"\n{package_name} removed successfully")
                    self.installed_packages = self.get_installed_packages()
                    self.search_packages()
                except Exception as e:
                    self.log_to_terminal(f"\nError: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to remove package: {str(e)}")

    def detect_aur_helper(self):
        """Detect installed AUR helpers and return the preferred one"""
        aur_helpers = [
            ('yay', ['yay']),
            ('paru', ['paru']),
            ('pamac', ['pamac']),
            ('aurman', ['aurman']),
            ('pikaur', ['pikaur'])
        ]
        
        for helper_name, helper_cmd in aur_helpers:
            try:
                result = subprocess.run(
                    ['which', helper_name],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.log_to_terminal(f"Found AUR helper: {helper_name}")
                    return helper_cmd
            except Exception:
                continue
        
        return None

    def check_updates(self):
        if not hasattr(self, 'updates_tree'):
            return
        
        self.updates_tree.clear()
        self.log_to_terminal("\nChecking for updates...")

        def check_updates_task(worker):
            if not worker._is_running:
                return
            
            try:
                aur_helper = self.detect_aur_helper()
                if not aur_helper:
                    worker.output.emit("No AUR helper found. Cannot check for updates.")
                    return
                
                worker.output.emit(f"Using {aur_helper[0]} to check updates...")
                
                safe_env = {
                    'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                    'HOME': os.environ.get('HOME', ''),
                    'USER': os.environ.get('USER', ''),
                    'LANG': os.environ.get('LANG', 'C.UTF-8'),
                    'DISPLAY': os.environ.get('DISPLAY', ''),
                    'XAUTHORITY': os.environ.get('XAUTHORITY', '')
                }
                
                if aur_helper[0] == 'pamac':
                    cmd = ['pamac', 'checkupdates', '-a']
                elif aur_helper[0] == 'yay':
                    worker.output.emit("Syncing package databases...")
                    try:
                        worker.run_sudo_command(['pacman', '-Sy'])
                    except subprocess.CalledProcessError as e:
                        if "Authentication cancelled" in str(e):
                            worker.output.emit("\nUpdate check cancelled: Authentication required")
                            return
                        worker.output.emit(f"\nWarning: Database sync failed: {str(e)}")
                    
                    cmd = ['yay', '-Qu', '--devel', '--needed']
                else:
                    cmd = [*aur_helper, '-Qu']
                
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        env=safe_env
                    )
                    
                    if (result.returncode == 0 or 
                        (aur_helper[0] == 'yay' and result.returncode == 1 and not result.stderr.strip())):
                        
                        if result.stdout.strip():
                            for line in result.stdout.strip().split('\n'):
                                if not worker._is_running:
                                    return
                                if line.strip():
                                    try:
                                        parts = line.split()
                                        name = parts[0]
                                        current_version = parts[1]
                                        new_version = parts[3] if len(parts) > 3 else parts[-1]
                                        
                                        source = "AUR" if name in self.get_foreign_packages() else "System"
                                        
                                        if worker._is_running:
                                            worker.package_found.emit({
                                                'name': name,
                                                'current_version': current_version,
                                                'new_version': new_version,
                                                'source': source
                                            })
                                            worker.output.emit(f"Found update: {name} ({current_version} → {new_version})")
                                    except (ValueError, IndexError) as e:
                                        worker.output.emit(f"Warning: Could not parse update line: {line} ({str(e)})")
                                        continue
                        else:
                            worker.output.emit("No updates found")
                    elif result.returncode != 0:
                        if result.stderr.strip():
                            worker.output.emit(f"Error output: {result.stderr}")
                        else:
                            worker.output.emit("No updates found")
                        
                except subprocess.CalledProcessError as e:
                    worker.output.emit(f"Error checking updates: {str(e)}")
                    if e.stderr:
                        worker.output.emit(f"Error output: {e.stderr}")
                    raise
                
                if worker._is_running:
                    worker.output.emit("\nUpdate check complete!")
                    worker._cleanup_lock.set()
                    
            except Exception as e:
                if worker._is_running:
                    worker.output.emit(f"Error during update check: {str(e)}")
                    worker._cleanup_lock.set()
                    raise

            worker.sudo_command.connect(self.handle_sudo_command)  

        try:
            worker = PackageWorker(check_updates_task, self)
            worker.output.connect(self.log_to_terminal)
            worker.package_found.connect(self.add_package_to_tree)
            worker.error.connect(lambda e: QMessageBox.critical(self, "Error", f"Update check failed: {e}"))
            worker.sudo_command.connect(self.handle_sudo_command)
            
            self.start_worker(worker)
        except Exception as e:
            self.log_to_terminal(f"Failed to start update check: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to start update check: {str(e)}")

    def update_all(self):
        if self.updates_tree.topLevelItemCount() == 0:
            QMessageBox.information(self, "Info", "No updates available")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Update",
            "Do you want to install all updates?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            def update_task(worker):
                try:
                    aur_helper = self.detect_aur_helper()
                    if not aur_helper:
                        worker.output.emit("No AUR helper found. Cannot proceed with updates.")
                        return

                    worker.output.emit("\nUpdating official packages...")
                    try:
                        worker.run_sudo_command(['pacman', '-Syu', '--noconfirm'])
                    except subprocess.CalledProcessError as e:
                        if "Authentication cancelled" in str(e):
                            worker.output.emit("\nUpdate cancelled: Authentication required")
                            return
                        worker.output.emit(f"\nWarning: Error updating official packages: {str(e)}")
                    
                    worker.output.emit(f"\nUpdating AUR packages using {aur_helper[0]}...")
                    try:
                        if aur_helper[0] == 'pamac':
                            worker.run_sudo_command(['pamac', 'upgrade', '-a', '--no-confirm'])
                        else:
                            if aur_helper[0] in ['yay', 'paru']:
                                worker.run_sudo_command([*aur_helper, '-Sua', '--noconfirm'])
                            else:
                                worker.run_sudo_command([*aur_helper, '-Su', '--noconfirm'])
                    except subprocess.CalledProcessError as e:
                        if "Authentication cancelled" in str(e):
                            worker.output.emit("\nUpdate cancelled: Authentication required")
                            return
                        worker.output.emit(f"\nError updating AUR packages: {str(e)}")
                        raise

                    worker.output.emit("\nUpdate process completed successfully!")
                    
                except Exception as e:
                    worker.output.emit(f"\nError during updates: {str(e)}")
                    raise

            worker = PackageWorker(update_task, self)
            worker.output.connect(self.log_to_terminal)
            worker.error.connect(lambda e: QMessageBox.critical(self, "Error", f"Update failed: {e}"))
            worker.sudo_command.connect(self.handle_sudo_command)
            worker.finished.connect(self.check_updates)
            
            self.start_worker(worker)

    def get_foreign_packages(self):
        """Get list of foreign (AUR) packages"""
        try:
            result = subprocess.run(
                ['pacman', '-Qm'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return [line.split()[0] for line in result.stdout.splitlines()]
        except Exception:
            pass
        return []

    def closeEvent(self, event):
        """Handle cleanup when closing the application"""
        if self.current_worker and self.current_worker._is_running:
            self.current_worker.stop()
            self._worker_lock.wait()
        event.accept()

    def start_worker(self, worker):
        """Safely start a new worker thread"""
        if self.current_worker and self.current_worker._is_running:
            self.current_worker.stop()
            self._worker_lock.wait()
        
        self._worker_lock.clear()
        self.current_worker = worker
        worker.finished.connect(self._worker_lock.set)
        worker.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AURManager()
    window.show()
    sys.exit(app.exec()) 