# Oracle - AUR Helper Wrapper

Oracle is a modern graphical user interface wrapper for AUR helpers and Pacman, designed to make package management on Arch Linux more accessible and user-friendly.


## Features

- 🔍 Search packages in both official repositories and AUR
- 📦 Install packages with a simple click
- 🔄 Check for system updates
- 🚀 Perform system-wide updates
- 🗑️ Remove packages with dependency handling
- 📝 Real-time terminal output viewing
- 🔐 Secure sudo authentication handling
- 🎨 Modern dark theme interface

## Prerequisites

- Arch Linux
- Python
- PyQt6
- One of the following AUR helpers:
  - yay (recommended)
  - paru
  - pamac
  - aurman
  - pikaur

## Installation

### Option 1: Using the Pre-built Binary

1. Download the latest release from the [releases page](https://github.com/0xgingi/oracle/releases)
2. Make the file executable:
```bash
chmod +x oracle
```
3. Run the application:
```bash
./oracle
```

Optional: Move to your path for system-wide access:
```bash
sudo mv oracle /usr/local/bin/
```

### Option 2: Building from Source

1. Clone the repository:
```bash
git clone https://github.com/0xgingi/oracle.git
cd oracle
```

2. Install build dependencies inside a venv:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Build the executable:
```bash
python build.py
```

The executable will be created in the `dist` directory.

4. Run the application:
```bash
./dist/oracle
```

### Option 3: Running from Source

1. Clone the repository:
```bash
git clone https://github.com/0xgingi/oracle.git
cd oracle
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python aur_manager.py
```