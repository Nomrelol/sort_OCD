# ✨ sort_OCD ✨

A professional, feature-rich CLI tool for intelligently organizing files. Built for the 72-hour Virtual CLI Development Challenge.

Smart Sorter is designed to be both powerful for experts and easy for beginners. It can be run instantly with a single command or through a user-friendly interactive menu.

---

## 🚀 Features

* **Hybrid Interface**: Use it as a fast command-line tool or through a guided interactive menu.
* **Multiple Sorting Strategies**: Organize your files by:
    * File Type (e.g., Images, Documents, Code)
    * Year (e.g., `2025/`)
    * Month (e.g., `2025-09-September/`)
    * Day (e.g., `2025-09-29-Monday/`)
* **Rich Animations**: Polished animations for a modern CLI experience, including:
    * A typewriter effect for the welcome message.
    * A live progress bar during file scanning.
    * A spinner animation during file organization.
    * An animated exit banner.
* **Built for Safety**:
    * **Action Plan Confirmation**: Always shows a summary of changes and asks for user approval before moving any files.
    * **Safe Renaming**: Automatically prevents overwriting files by renaming duplicates (e.g., `file.txt` becomes `file (1).txt`).
* **Detailed Logging**: All actions are automatically recorded in a `sorter.log` file for a complete audit trail.

---

## ⚙️ Requirements

* Python 3.x

No external libraries are needed! All features are built using Python's standard library.

---

## Usage

There are two ways to use Smart Sorter: Interactive Mode and CLI Mode.

### 1. Interactive Mode (For Beginners)

If you're new or unsure, simply run the script without any arguments. It will guide you through the process with a friendly menu.

**Command:**
```bash
python sorter.py

DEMO:
--- Welcome to the Interactive File Sorter ---
Enter the path to the folder you want to sort: ./test_folder

How would you like to sort the files?
  1: By File Type (e.g., Images, Documents)
  2: By Year (e.g., 2025)
  3: By Month (e.g., 2025-09-September)
  4: By Day (e.g., 2025-09-29-Monday)

Enter your choice [default is 1]: 1

Scanning Files: |██████████████████████████████████████████████████| 100.0% Complete

--- ACTION PLAN ---
The script will organize 6 file(s) into 5 folder(s).
Total size of files to be moved: 0.00 B

Proceed with this plan? (y/n): y

Starting organization...
Organizing files /
  - Moved 'archive.zip'
  - Moved 'document.pdf'
  - Moved 'image.jpg'
  - Moved 'notes.txt'
  - Moved 'song.mp3'
  - Moved 'video.mp4'

Organization complete! Moved 6 file(s).
Organization complete! Goodbye 👋

Comands:
python sorter.py ./my_downloads --by ext
python sorter.py ./my_photos --by year
python sorter.py C:\Users\YourUser\Desktop --by month
python sorter.py /path/to/your/folder --by day


📝 Logging
Every time you run the script, it will create or append to a file named sorter.log in the same directory. This file contains a timestamped record of all actions performed, including the mode used, directories created, and files moved. This is useful for keeping track of your organization history.

==================================================
Sorter session started at 2025-09-29 23:15:00
==================================================
[2025-09-29 23:15:00] CLI mode. Path: ./test_folder, Mode: ext
[2025-09-29 23:15:00] Starting scan of 6 files.
[2025-09-29 23:15:01] Scan complete. Plan created with 5 destination folders.
[2025-09-29 23:15:05] User confirmed. Starting file move operation.
[2025-09-29 23:15:05] Created directory: ./test_folder/Archives
[2025-09-29 23:15:05] Moved './test_folder/archive.zip' to './test_folder/Archives/archive.zip'
...
[2025-09-29 23:15:06] Operation complete. Moved 6 files.
