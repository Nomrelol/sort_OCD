# sorter.py
import os
import sys
import datetime
import argparse
import time
import itertools
import threading

# --- CONSTANTS ---
LOG_FILE = 'sorter.log'

# --- ANSI escape codes for terminal color formatting ---
class Colors:
    """Provides a set of ANSI color codes for rich terminal output."""
    RESET = '\033[0m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'

# --- Helper Functions ---
def get_safe_new_path(path):
    """
    Generates a unique file path to prevent overwriting existing files.
    Appends a counter (e.g., 'file (1).txt') if the path already exists.
    """
    if not os.path.exists(path):
        return path
    directory, filename = os.path.split(path)
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_name = f"{name} ({counter}){ext}"
        new_path = os.path.join(directory, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def format_bytes(byte_count):
    """Formats an integer byte count into a human-readable string (KB, MB, GB)."""
    if byte_count is None: return "0 B"
    power = 1024; n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while byte_count >= power and n < len(power_labels):
        byte_count /= power; n += 1
    return f"{byte_count:.2f} {power_labels[n]}B"

# --- Animation Utilities ---
class Spinner:
    """Spinner animation for long-running operations."""
    def __init__(self, message="Processing..."):
        self.message = message
        self.stop_flag = False
        self.thread = threading.Thread(target=self._spin)

    def _spin(self):
        for c in itertools.cycle("|/-\\"):
            if self.stop_flag:
                break
            sys.stdout.write(f"\r{self.message} {c}")
            sys.stdout.flush()
            time.sleep(0.1)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_flag = True
        self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message)+4) + "\r")

def typing_effect(text, delay=0.02):
    """Prints text with a typewriter-style effect."""
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def print_progress_bar(iteration, total, prefix='', suffix='', length=50, fill='█'):
    """
    Creates and prints a terminal progress bar.
    Should be called repeatedly inside loops for updates.
    """
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')

def exit_banner():
    """Displays a small animated goodbye banner."""
    msg = "Organization complete! Goodbye 👋"
    for i in range(3):
        sys.stdout.write("\r" + " " * i + msg)
        sys.stdout.flush()
        time.sleep(0.2)
    print()

# --- Logging Functions ---
def log_action(message):
    """Appends a timestamped message to the global log file."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

def setup_logging():
    """Writes a session start header to the log file."""
    with open(LOG_FILE, 'a') as f:
        f.write("\n" + "="*50 + "\n")
        f.write(f"Sorter session started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*50 + "\n")

# --- UI and Interactive Functions ---
def display_action_plan(move_plan):
    """
    Displays a summary of planned moves and requests user confirmation.
    Returns True if confirmed, False otherwise.
    """
    print()
    print(f"{Colors.BLUE}--- ACTION PLAN ---{Colors.RESET}")
    total_files = sum(len(f) for f in move_plan.values())
    total_bytes = sum(os.path.getsize(f) for files in move_plan.values() for f in files)
    print(f"The script will organize {Colors.YELLOW}{total_files}{Colors.RESET} file(s) into {Colors.YELLOW}{len(move_plan)}{Colors.RESET} folder(s).")
    print(f"Total size of files to be moved: {Colors.YELLOW}{format_bytes(total_bytes)}{Colors.RESET}")
    print()
    log_action("Action plan presented to user for confirmation.")
    try:
        confirm = input("Proceed with this plan? (y/n): ")
        if confirm.lower() != 'y':
            print(f"{Colors.RED}Operation cancelled.{Colors.RESET}")
            log_action("User cancelled the operation.")
            return False
        return True
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Operation cancelled.{Colors.RESET}")
        log_action("User cancelled via KeyboardInterrupt.")
        return False

def run_interactive_mode():
    """
    Runs the script's interactive user-friendly mode.
    Returns (target_folder, mode) or (None, None) if cancelled.
    """
    print()
    typing_effect(f"{Colors.CYAN}--- Welcome to the Interactive File Sorter ---{Colors.RESET}")
    try:
        target_folder = input("Enter the path to the folder you want to sort: ")
        if not os.path.isdir(target_folder):
            print(f"{Colors.RED}Error: Invalid directory.{Colors.RESET}"); return None, None
        print("\nHow would you like to sort the files?")
        print("  1: By File Type (e.g., Images, Documents)")
        print("  2: By Year (e.g., 2025)")
        print("  3: By Month (e.g., 2025-09-September)")
        print("  4: By Day (e.g., 2025-09-29-Monday)")
        print()
        choice = input("Enter your choice [default is 1]: ") or "1"
        mode_map = {'1': 'ext', '2': 'year', '3': 'month', '4': 'day'}
        mode = mode_map.get(choice)
        if not mode:
            print(f"{Colors.RED}Error: Invalid choice.{Colors.RESET}"); return None, None
        return target_folder, mode
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Operation cancelled.{Colors.RESET}"); return None, None

# --- Main Workflow ---
def main():
    """Main function to parse arguments and execute the file sorter."""
    parser = argparse.ArgumentParser(
        description='A smart file sorter. Runs interactively if no path is provided.',
        epilog='Example: python sorter.py ./my_downloads --by month'
    )
    parser.add_argument('path', nargs='?', default=None, help='(Optional) The directory to sort.')
    parser.add_argument('-b', '--by', choices=['ext', 'year', 'month', 'day'], default='ext', help='Sorting strategy.')
    args = parser.parse_args()

    setup_logging()
    log_action("Script initialized.")

    if args.path:
        target_folder, mode = args.path, args.by
        log_action(f"CLI mode. Path: {target_folder}, Mode: {mode}")
    else:
        log_action("Interactive mode activated.")
        target_folder, mode = run_interactive_mode()
        if not target_folder:
            log_action("User cancelled interactive session.")
            sys.exit()
        log_action(f"Interactive mode. Path: {target_folder}, Mode: {mode}")

    EXT_DIRS = {
        'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'],
        'Videos': ['.mp4', '.mkv', '.mov', '.avi', '.webm'],
        'Audio': ['.mp3', '.wav', '.flac', '.aac'],
        'Documents': ['.pdf', '.docx', '.doc', '.txt', '.md'],
        'Archives': ['.zip', '.rar', '.tar', '.gz'],
        'Code': ['.py', '.js', '.java', '.html', '.css'],
    }

    if not os.path.isdir(target_folder):
        error_msg = f"Error: Directory '{target_folder}' not found."
        print(f"{Colors.RED}{error_msg}{Colors.RESET}")
        log_action(error_msg)
        sys.exit(1)

    print()
    move_plan = {}
    files_in_dir = [f for f in os.listdir(target_folder) if os.path.isfile(os.path.join(target_folder, f))]
    total_files = len(files_in_dir)
    log_action(f"Starting scan of {total_files} files.")

    # <<< --- CRITICAL FIX IS HERE --- >>>
    # If there are no files, we exit early to prevent a division by zero error.
    if total_files == 0:
        print(f"{Colors.GREEN}Directory is empty. Nothing to sort.{Colors.RESET}")
        log_action("Scan complete. Directory was empty.")
        sys.exit(0)
    
    print_progress_bar(0, total_files, prefix='Scanning Files:', suffix='Complete', length=50)

    for i, filename in enumerate(files_in_dir):
        time.sleep(0.01)  # Small delay to make the progress bar visible
        file_path = os.path.join(target_folder, filename)

        dest_dir_name = None
        if mode == 'ext':
            for dir_name, extensions in EXT_DIRS.items():
                if any(filename.lower().endswith(ext) for ext in extensions):
                    dest_dir_name = dir_name
                    break
        else:  # Date-based modes
            try:
                mod_time = os.path.getmtime(file_path)
                date_obj = datetime.datetime.fromtimestamp(mod_time)
                if mode == 'year': dest_dir_name = date_obj.strftime('%Y')
                elif mode == 'month': dest_dir_name = date_obj.strftime('%Y-%m-%B')
                elif mode == 'day': dest_dir_name = date_obj.strftime('%Y-%m-%d-%A')
            except OSError:
                continue

        if dest_dir_name:
            move_plan.setdefault(dest_dir_name, []).append(file_path)

        print_progress_bar(i + 1, total_files, prefix='Scanning Files:', suffix='Complete', length=50)

    log_action(f"Scan complete. Plan created with {len(move_plan)} destination folders.")

    if not move_plan:
        print(f"\n{Colors.GREEN}No files to organize.{Colors.RESET}")
        log_action("No files needed sorting. Exiting.")
        sys.exit(0)

    if not display_action_plan(move_plan):
        sys.exit()

    print(f"\n{Colors.GREEN}Starting organization...{Colors.RESET}")
    log_action("User confirmed. Starting file move operation.")
    moved_count = 0

    spinner = Spinner("Organizing files")
    spinner.start()

    for dest_dir, files in move_plan.items():
        dest_dir_path = os.path.join(target_folder, dest_dir)
        if not os.path.exists(dest_dir_path):
            os.mkdir(dest_dir_path)
            log_action(f"Created directory: {dest_dir_path}")
        for file_path in files:
            safe_path = get_safe_new_path(os.path.join(dest_dir_path, os.path.basename(file_path)))
            os.rename(file_path, safe_path)
            log_action(f"Moved '{file_path}' to '{safe_path}'")
            moved_count += 1
    
    spinner.stop()

    log_action(f"Operation complete. Moved {moved_count} files.")
    exit_banner()

# Script entry point
if __name__ == "__main__":
    main()