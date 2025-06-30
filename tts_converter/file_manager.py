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
        # Add another empty line (this is the extra line you requested)
        print("")
        # Move the cursor up one line to be ready for input
        sys.stdout.write("\033[F")
        
        while True:
            print("📁 Enter full path to your text file (or 'q' to cancel): ", end='')
            sys.stdout.flush()
            custom_path = input().strip().strip('"')
            
            if not custom_path:
                continue
                
            if custom_path.lower() in ['q', 'quit', 'exit', 'cancel']:
                # No need to print message here, main script will handle it
                return "QUIT"  # Special return value to indicate user explicitly quit
            
            if os.path.exists(custom_path):
                return custom_path
            else:
                print(f"❌ File '{custom_path}' not found!")
                print("")  # Add an empty line
                # Move the cursor up one line
                sys.stdout.write("\033[F")
                print("Try again? (y/n): ", end='')
                sys.stdout.flush()
                retry = input().strip().lower()
                if retry not in ['y', 'yes']:
                    return "QUIT"  # Special return value to indicate user explicitly quit
