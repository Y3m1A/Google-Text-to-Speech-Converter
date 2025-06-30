#!/usr/bin/env python3
"""
Utility functions for the TTS converter.
"""
import os
import sys
import subprocess

class TTSUtils:
    """Utility functions for the TTS converter."""
    
    @staticmethod
    def ensure_dependencies():
        """Check and install required dependencies."""
        # List of required packages
        required_packages = [
            {"import_name": "gtts", "display_name": "gTTS", "description": "Google Text-to-Speech library"},
            # Add any other dependencies your project needs
        ]
        
        missing_packages = []
        
        print("🔍 Checking dependencies...")
        
        # Check each required package
        for package in required_packages:
            try:
                __import__(package["import_name"])
                print(f"✅ {package['display_name']} is installed")
            except ImportError:
                missing_packages.append(package)
                print(f"❌ {package['display_name']} is missing")
        
        # If there are missing packages, try to install them or exit
        if missing_packages:
            print("\n⚠️ Missing dependencies detected!")
            
            # Ask if user wants to auto-install
            try:
                choice = input("Would you like to attempt automatic installation? (y/n): ").strip().lower()
                if choice in ['y', 'yes']:
                    for package in missing_packages:
                        print(f"\nInstalling {package['display_name']}...")
                        try:
                            subprocess.run([sys.executable, "-m", "pip", "install", package["import_name"]], check=True)
                            # Verify installation
                            try:
                                __import__(package["import_name"])
                                print(f"✅ {package['display_name']} installed successfully")
                                missing_packages.remove(package)  # Remove from missing list if successful
                            except ImportError:
                                print(f"❌ Failed to import {package['display_name']} after installation")
                        except Exception as e:
                            print(f"❌ Failed to install {package['display_name']}: {e}")
                else:
                    print("Automatic installation skipped.")
            except KeyboardInterrupt:
                print("\nInstallation cancelled.")
        
        # If there are still missing packages, show installation instructions and exit
        if missing_packages:
            print("\n⚠️ Please install the following dependencies before running the script:")
            for package in missing_packages:
                print(f"  - {package['display_name']} ({package['description']})")
            
            print("\nYou can install them using pip:")
            pip_command = f"{sys.executable} -m pip install " + " ".join(p["import_name"] for p in missing_packages)
            print(f"  {pip_command}")
            
            sys.exit(1)
        
        print("✅ All dependencies are installed and ready to use")
    
    @staticmethod
    def check_file_readability(file_path):
        """Check if a file exists and is readable."""
        if not os.path.exists(file_path):
            raise Exception(f"File not found: {file_path}")
        if not os.path.isfile(file_path):
            raise Exception(f"Not a file: {file_path}")
        if not os.access(file_path, os.R_OK):
            raise Exception(f"File not readable: {file_path}")
        return True
    
    @staticmethod
    def validate_language(language_code):
        """Validate language code."""
        # Basic validation for common language codes
        valid_langs = ['en', 'fr', 'es', 'de', 'it', 'pt', 'nl', 'ja', 'zh-CN', 'zh-TW', 'ru']
        if language_code not in valid_langs:
            print(f"⚠️ '{language_code}' may not be a supported language code. Continuing anyway...")
        return language_code
    
    @staticmethod
    def format_file_size(size_bytes):
        """Format file size in a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    @staticmethod
    def show_file_info(file_path):
        """Show information about a file."""
        try:
            file_size = os.path.getsize(file_path)
            formatted_size = TTSUtils.format_file_size(file_size)
            
            # Count lines and characters
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                line_count = content.count('\n') + 1
                char_count = len(content)
                word_count = len(content.split())
            
            print(f"📄 File: {os.path.basename(file_path)}")
            print(f"   • Size: {formatted_size}")
            print(f"   • Characters: {char_count:,}")
            print(f"   • Words: {word_count:,}")
            print(f"   • Lines: {line_count:,}")
            
            # Estimate chunks (approximately)
            from .config import Config
            est_chunks = max(1, char_count // Config.DEFAULT_CHUNK_SIZE)
            print(f"   • Estimated chunks: ~{est_chunks}")
            
            return {
                'size': file_size,
                'characters': char_count,
                'words': word_count,
                'lines': line_count,
                'estimated_chunks': est_chunks
            }
        except Exception as e:
            print(f"⚠️ Error getting file info: {e}")
            return None
