#!/usr/bin/env python3
"""
File management functionality for the TTS converter.
"""
import os
import glob
import sys
from .config import Config

class FileManager:
    """Handles file discovery and selection."""
    
    @staticmethod
    def find_text_files():
        """Find all .txt files in the TTS project folder and its subdirectories."""
        # Get the directory where the tts_converter package is located
        tts_converter_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to get the project root directory
        project_root = os.path.dirname(tts_converter_dir)
        
        # Find all .txt files in the project root and subdirectories
        files = []
        for root, dirs, filenames in os.walk(project_root):
            # Only search within the project folder
            if not root.startswith(project_root):
                continue
                
            for filename in filenames:
                if filename.endswith('.txt'):
                    files.append(os.path.join(root, filename))
        
        return sorted(files)
    
    @staticmethod
    def interactive_file_selection():
        """Interactive file selection interface."""
        print("\n======================================================================")
        print("🎵 TTS CONVERTER - FILE SELECTION")
        print("======================================================================")
        
        files = FileManager.find_text_files()
        
        if not files:
            print("❌ No .txt files found in TTS project folder or its subdirectories!")
            print("\n💡 Tips:")
            print("   • Add .txt files to the TTS project folder or its subdirectories")
            print("   • Use -f option to specify a file directly")
            print("\nWould you like to enter a custom file path? (y/n): ", end='')
            sys.stdout.flush()
            choice = input().strip().lower()
            if choice in ['y', 'yes']:
                return FileManager._get_custom_file_path()
            else:
                return None
        
        # Get the project root directory for relative path display
        tts_converter_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(tts_converter_dir)
        
        print(f"\n📁 Found {len(files)} .txt file(s) in TTS project folder and subdirectories:")
        print("----------------------------------------------------------------------")
        
        for i, file_path in enumerate(files, 1):
            try:
                file_size = os.path.getsize(file_path) / 1024
                
                # Show path relative to project root for better readability
                try:
                    rel_path = os.path.relpath(file_path, project_root)
                    display_name = rel_path
                except:
                    display_name = file_path
                
                # Match the exact format from the v3 file with proper spacing
                print(f"{i:2d}. {display_name:<45} ({file_size:6.1f}KB)")
            except OSError:
                print(f"{i:2d}. {file_path:<45} (Error reading)")
        
        print(f"{len(files) + 1:2d}. 📂 Enter custom file path")
        print(f"{len(files) + 2:2d}. ❌ Exit")
        print("----------------------------------------------------------------------")
        print("")  # Add an empty line for better spacing
        
        # Add another empty line here (this is the extra line you requested)
        print("")
        
        # Now move the cursor up one line to be ready for input
        sys.stdout.write("\033[F")  # ANSI escape code to move cursor up one line
        
        # Prompt text - displayed separately for visibility
        prompt_text = f"Select file (1-{len(files) + 2}) or 'q' to quit: "
        print(prompt_text, end='')  # Print without newline
        sys.stdout.flush()  # Force flush to ensure prompt is visible
        
        while True:
            try:
                # Add the prompt immediately after displaying file options
                choice = input().strip().lower()  # Just get input, prompt already displayed
                
                if choice in ['q', 'quit', 'exit']:
                    # No need to print any message here, main script will handle it
                    return "QUIT"  # Special return value to indicate user explicitly quit
                
                try:
                    choice_num = int(choice)
                    
                    if 1 <= choice_num <= len(files):
                        selected = files[choice_num - 1]
                        # Return the selection immediately without confirmation
                        return selected
                    
                    elif choice_num == len(files) + 1:
                        return FileManager._get_custom_file_path()
                    
                    elif choice_num == len(files) + 2:
                        # Exit option selected
                        return "QUIT"
                    
                    else:
                        print(f"❌ Invalid choice! Please enter 1-{len(files) + 2}")
                        # Continue the loop instead of recursive call
                        continue
                
                except ValueError:
                    print("❌ Please enter a valid number or 'q' to quit")
                    # Continue the loop instead of recursive call
                    continue
                    
            except KeyboardInterrupt:
                # No need to print message here, main script will handle it
                return "QUIT"  # Special return value to indicate user explicitly quit
    
    @staticmethod
    def _show_file_preview(file_path):
        """Show preview of selected file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                preview = f.read(200)
            print(f"\n📖 Preview: {preview}...")
            print("----------------------------------------------------------------------")
        except Exception as e:
            print(f"⚠️  Could not preview file: {e}")
            print("----------------------------------------------------------------------")
    
    @staticmethod
    def _get_custom_file_path():
        """Get custom file path from user."""
        print("----------------------------------------------------------------------")
        # Add an empty line for better spacing
        print("")
        # Add another empty line
        print("")
        # Move the cursor up one line to be ready for input
        sys.stdout.write("\033[F")
        
        print("💡 Tips for entering file paths:")
        print("  • Enter the full path to a .txt file anywhere on your system")
        print("  • On macOS/Linux, use forward slashes: /")
        print("  • You can drag and drop a file into the terminal")
        print("  • Example: /Users/username/Documents/my_text.txt")
        print("")
        
        while True:
            print("📁 Enter full path to your text file (or 'q' to cancel): ", end='')
            sys.stdout.flush()
            custom_path = input().strip().strip('"').strip("'")
            
            if not custom_path:
                continue
                
            if custom_path.lower() in ['q', 'quit', 'exit', 'cancel']:
                # No need to print message here, main script will handle it
                return "QUIT"  # Special return value to indicate user explicitly quit
            
            # Try to expand user directory (e.g., ~/Documents)
            if custom_path.startswith('~'):
                custom_path = os.path.expanduser(custom_path)
            
            # Check if file exists
            if os.path.exists(custom_path):
                if os.path.isfile(custom_path):
                    # Check if it's a text file
                    if not custom_path.lower().endswith('.txt'):
                        print(f"⚠️ '{custom_path}' is not a .txt file. Are you sure you want to use it? (y/n): ", end='')
                        sys.stdout.flush()
                        use_anyway = input().strip().lower()
                        if use_anyway in ['y', 'yes']:
                            return custom_path
                        else:
                            continue
                    return custom_path
                else:
                    print(f"❌ '{custom_path}' is a directory, not a file. Please enter a file path.")
            else:
                print(f"❌ File '{custom_path}' not found!")
                # Check if the directory exists at least
                dir_path = os.path.dirname(custom_path)
                if dir_path and not os.path.exists(dir_path):
                    print(f"⚠️ Directory '{dir_path}' does not exist either.")
                
                print("")  # Add an empty line
                # Move the cursor up one line
                sys.stdout.write("\033[F")
                print("Try again? (y/n): ", end='')
                sys.stdout.flush()
                retry = input().strip().lower()
                if retry not in ['y', 'yes']:
                    return "QUIT"  # Special return value to indicate user explicitly quit
