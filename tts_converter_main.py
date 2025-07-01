#!/usr/bin/env python3
"""
Modern Text-to-Speech Converter
A clean, modular implementation with checkpoint/resume functionality.

REQUIREMENTS: Python 3.6 or higher is required to run this script.
Run with: python3 tts_converter_main.py [options]

IMPORTANT: This script preserves all generated .mp3 files as they are the 
final TTS conversion results. Individual chunk files (temp_chunk_*.mp3) 
are NOT cleaned up automatically - they represent the converted audio output.
"""
import sys

# Check Python version before importing anything else
if sys.version_info < (3, 6):
    print("❌ ERROR: Python 3.6 or higher is required!")
    print(f"   Current version: {sys.version}")
    print("💡 Please run with: python3 tts_converter_main.py")
    sys.exit(1)

import os
import glob
import argparse
import time

# Import from the tts_converter package
from tts_converter.config import Config
from tts_converter.progress import ProgressTracker
from tts_converter.checkpoint import CheckpointManager
from tts_converter.text_processor import TextProcessor
from tts_converter.shutdown import ShutdownHandler
from tts_converter.tts_processor import TTSProcessor
from tts_converter.utils import TTSUtils
from tts_converter.file_manager import FileManager


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert text files to speech with checkpoints and resume capability. Requires Python 3.6+",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="USAGE: python3 tts_converter_main.py [file] [options]"
    )
    
    parser.add_argument(
        "file", 
        help="Path to text file to convert",
        nargs='?'  # Make it optional
    )
    
    parser.add_argument(
        "-o", "--output", 
        help="Base name for output files (default: input filename)"
    )
    
    parser.add_argument(
        "-d", "--output-dir", 
        help=f"Output directory (default: {Config.DEFAULT_OUTPUT_DIR} in package location)",
        default=Config.DEFAULT_OUTPUT_DIR
    )
    
    parser.add_argument(
        "-l", "--language", 
        help="Language for TTS (default: en)",
        default=Config.DEFAULT_LANGUAGE
    )
    
    parser.add_argument(
        "-s", "--slow", 
        help="Use slower TTS speed",
        action="store_true"
    )
    
    parser.add_argument(
        "-p", "--prefix", 
        help="Custom prefix for output chunk files"
    )
    
    parser.add_argument(
        "-i", "--interactive", 
        help="Force interactive file selection mode",
        action="store_true"
    )
    
    parser.add_argument(
        "--delete-progress", 
        help="Delete all previous progress and start fresh",
        action="store_true"
    )
    
    parser.add_argument(
        "--clean", 
        help="Clean up previous progress files without conversion",
        action="store_true"
    )
    
    parser.add_argument(
        "--cleanup", 
        help="Clean up all old progress files and exit",
        action="store_true"
    )
    
    parser.add_argument(
        "--info", 
        help="Show file information without conversion",
        action="store_true"
    )
    
    parser.add_argument(
        "--no-parallel", 
        help="Disable parallel processing and use sequential processing",
        action="store_true"
    )
    
    return parser.parse_args()


def print_header():
    """Print program header."""
    print("\n" + "=" * 80)
    print("🎙️  MODERN TEXT-TO-SPEECH CONVERTER  🎙️")
    print("=" * 80)
    print("📋 Requires Python 3.6+ | Run with: python3 tts_converter_main.py")
    print("=" * 80 + "\n")


def show_help():
    """Show processing help."""
    print("\n" + "="*60)
    print("🎮 PROCESSING CONTROLS")
    print("="*60)
    print("While processing, you can type these commands and press Enter:")
    print("  p/pause     - Pause after current chunk")
    print("  r/resume    - Resume from pause")
    print("  s/stop      - Stop and save progress")
    print("  f/force     - Force stop immediately (will redo current chunk when resumed)")
    print("  sd/delete   - Stop and DELETE all progress")
    print("  h/help      - Show this help")
    print("="*60)
    print("💾 Progress is automatically saved after each chunk!")
    print("🔄 You can always resume later by running the script again.")
    print("⚠️  'sd' or 'delete' will remove ALL progress and temp files!")
    print("⚠️  'f' or 'force' will stop immediately and current chunk will be redone!")
    print("📝 Status messages will keep you informed of progress.")
    print("👉 You'll see 'You may input a command here: ' when commands can be entered.")
    print("="*60)


def cleanup_old_progress_files():
    """Clean up old progress files manually."""
    project_dir = Config.get_project_path()
    
    print("🧹 Global cleanup of old progress files")
    print("=" * 60)
    print("⚠️  This will remove ALL progress databases and boundaries files.")
    print("⚠️  Any ongoing TTS processes will need to restart from the beginning.")
    print("📁 TTS .mp3 files will be preserved as they are the conversion results.")
    print("=" * 60)
    
    print("")  # Add an empty line
    # Move the cursor up one line
    sys.stdout.write("\033[F")
    print("Continue with global cleanup? (y/n): ", end='')
    sys.stdout.flush()
    confirm = input().lower().strip()
    if confirm != 'y':
        print("❌ Global cleanup cancelled.")
        return
        
    print("\n🗑️ Starting global cleanup process...")
    
    # Create a temporary checkpoint manager for cleanup
    checkpoint_mgr = CheckpointManager()
    
    # Clean up all checkpoint databases and progress
    try:
        checkpoint_mgr.cleanup_progress_files()
        print("✅ Cleaned up checkpoint databases")
    except Exception as e:
        print(f"⚠️ Error cleaning checkpoint databases: {e}")
    
    # Find and remove boundary files
    try:
        boundary_files = glob.glob(os.path.join(project_dir, "*_chunk_boundaries.json"))
        if boundary_files:
            for boundary_file in boundary_files:
                try:
                    os.remove(boundary_file)
                    print(f"🧹 Removed boundaries file: {os.path.basename(boundary_file)}")
                except Exception as e:
                    print(f"⚠️ Could not remove {os.path.basename(boundary_file)}: {e}")
        else:
            print("ℹ️ No boundary files found")
    except Exception as e:
        print(f"⚠️ Error during boundary file cleanup: {e}")
    
    # Find and report temp files (but preserve .mp3 files)
    try:
        temp_files = glob.glob(os.path.join(project_dir, "temp_chunk_*.mp3"))
        if temp_files:
            print(f"📁 Found {len(temp_files)} TTS chunk files - preserving them as they are conversion results")
            print("💾 TTS .mp3 files will be preserved (they are the conversion results)")
        else:
            print("ℹ️ No temporary chunk files found")
    except Exception as e:
        print(f"⚠️ Error checking for temporary files: {e}")
    
    print("✅ Global cleanup complete!")
    print("🔄 All progress has been reset. Future conversions will start fresh.")


def main(recursive_call=False):
    """Main entry point."""
    # Parse arguments
    args = parse_arguments()
    
    # Print header (only if not a recursive call)
    if not recursive_call:
        print_header()
    
    # Handle cleanup option
    if args.cleanup:
        cleanup_old_progress_files()
        return
    
    # Ensure dependencies
    print("🔧 Checking TTS dependencies...")
    try:
        TTSUtils.ensure_dependencies()
        print("✅ All TTS dependencies are available!")
    except Exception as e:
        print(f"❌ Dependency check failed: {e}")
        print("💡 Please install required dependencies and try again.")
        sys.exit(1)
    
    # Handle multiprocessing configuration
    if args.no_parallel:
        Config.set_multiprocessing_enabled(False)
        print("⚙️ Multiprocessing configuration updated:")
        print("⚠️ Parallel processing disabled - using sequential processing")
        print("ℹ️ This may increase processing time but reduces system load")
    
    # Create components
    checkpoint_mgr = CheckpointManager()
    progress_tracker = ProgressTracker()
    shutdown_handler = ShutdownHandler(progress_tracker)
    tts_processor = TTSProcessor(checkpoint_mgr, progress_tracker, shutdown_handler)
    
    # Handle command-specific functions
    if args.clean:
        if args.file:
            print(f"🧹 Cleaning up previous progress files for: {os.path.basename(args.file)}")
            print("⚠️  This will remove progress databases and boundaries files for this specific file.")
            print("⚠️  Audio .mp3 files will be preserved as they are the conversion results.")
            
            print("")  # Add an empty line
            # Move the cursor up one line
            sys.stdout.write("\033[F")
            print("Continue with cleanup? (y/n): ", end='')
            sys.stdout.flush()
            confirm = input().lower().strip()
            if confirm != 'y':
                print("❌ Cleanup cancelled.")
                return
            
            print(f"🗑️ Cleaning progress files for: {os.path.basename(args.file)}")
            try:
                checkpoint_mgr.cleanup_progress_files(args.file)
                if TextProcessor.cleanup_chunk_boundaries(args.file):
                    print(f"🧹 Removed boundaries file for: {os.path.basename(args.file)}")
                else:
                    print(f"ℹ️ No boundaries file found for: {os.path.basename(args.file)}")
                print("✅ Cleanup complete!")
            except Exception as e:
                print(f"❌ Error during cleanup: {e}")
        else:
            print("❌ No file specified for cleanup.")
            print("💡 Use: python tts_converter_main.py <file> --clean")
        return
    
    if args.delete_progress:
        if not args.file:
            print("❌ No file specified for progress deletion.")
            print("💡 Use: python tts_converter_main.py <file> --delete-progress")
            return
        
        if not os.path.exists(args.file):
            print(f"❌ File '{args.file}' not found.")
            print("❌ Cannot delete progress for a file that doesn't exist.")
            return
        
        print(f"🗑️ Deleting all progress data for: {os.path.basename(args.file)}")
        print("⚠️  This will remove all checkpoints and boundaries for this file.")
        print("⚠️  You will need to restart conversion from the beginning.")
        print("📁 Audio .mp3 files will be preserved.")
        
        print("")  # Add an empty line
        # Move the cursor up one line
        sys.stdout.write("\033[F")
        print("Continue with progress deletion? (y/n): ", end='')
        sys.stdout.flush()
        confirm = input().lower().strip()
        if confirm != 'y':
            print("❌ Progress deletion cancelled.")
            return
        
        try:
            checkpoint_mgr.delete_all_progress(args.file)
            if TextProcessor.cleanup_chunk_boundaries(args.file):
                print(f"🧹 Removed boundaries file for: {os.path.basename(args.file)}")
            else:
                print(f"ℹ️ No boundaries file found for: {os.path.basename(args.file)}")
            print("✅ Progress deleted successfully!")
        except Exception as e:
            print(f"❌ Error during progress deletion: {e}")
        
        if args.info:
            # Only wanted to delete progress and show info
            print(f"\n📊 Showing file information for: {os.path.basename(args.file)}")
            try:
                TTSUtils.show_file_info(args.file)
            except Exception as e:
                print(f"❌ Error showing file info: {e}")
        return
    
    # Determine file to process
    file_path = args.file
    
    if args.interactive or not file_path:
        print("📁 Starting interactive file selection...")
        file_path = FileManager.interactive_file_selection()
        if file_path == "QUIT":
            print("\n❌ File selection cancelled by user.")
            print("👋 Exiting TTS converter.")
            return
        elif not file_path:
            print("❌ No file selected during interactive selection.")
            print("💡 Please run the script again and select a valid text file.")
            return
    elif file_path and not os.path.exists(file_path):
        print(f"❌ File '{file_path}' not found at specified location.")
        print("💡 The file could not be found at the specified path.")
        print("🔄 Switching to interactive file selection mode...")
        file_path = FileManager.interactive_file_selection()
        if file_path == "QUIT":
            print("\n❌ File selection cancelled by user.")
            print("👋 Exiting TTS converter.")
            return
        elif not file_path:
            print("❌ No file selected during interactive selection.")
            print("💡 Please run the script again and specify a valid file path.")
            return
    
    if args.info:
        if not file_path:
            print("❌ No file specified for information display.")
            print("💡 Use: python tts_converter_main.py <file> --info")
            return
        
        if not os.path.exists(file_path):
            print(f"❌ File '{file_path}' not found.")
            print("💡 Cannot show information for a file that doesn't exist.")
            return
        
        # Show file info and exit
        print(f"📊 Showing file information for: {os.path.basename(file_path)}")
        try:
            TTSUtils.show_file_info(file_path)
            print("✅ File information displayed successfully!")
        except Exception as e:
            print(f"❌ Error showing file info: {e}")
        return
    
    # Validate input file
    print(f"🔍 Validating file: {os.path.basename(file_path)}")
    try:
        TTSUtils.check_file_readability(file_path)
        print("✅ File validation successful!")
    except Exception as e:
        print(f"❌ File validation failed: {e}")
        print("💡 Please ensure the file exists and is readable.")
        sys.exit(1)
    
    # Validate language
    print(f"🌍 Validating language setting: {args.language}")
    validated_language = TTSUtils.validate_language(args.language)
    if validated_language != args.language:
        print(f"⚙️ Language adjusted from '{args.language}' to '{validated_language}'")
    else:
        print(f"✅ Language '{validated_language}' validated successfully!")
    args.language = validated_language
    
    # Check for existing progress to determine if we should ask for folder name
    existing_progress = checkpoint_mgr.load_progress(file_path)
    use_previous_settings = False
    
    if existing_progress and not args.info:
        print("\n" + "="*60)
        print("🔄 PREVIOUS PROGRESS DETECTED")
        print("="*60)
        print(f"Found existing progress for this file: {existing_progress['completed_chunks']}/{existing_progress['total_chunks']} chunks completed.")
        print(f"Previous output folder: {os.path.basename(os.path.dirname(existing_progress['output_file']))}")
        if existing_progress['file_prefix']:
            print(f"Previous file prefix: {existing_progress['file_prefix']}")
        print("="*60)
        
        print("")  # Add an empty line
        # Move the cursor up one line
        sys.stdout.write("\033[F")
        print("Continue with previous settings? (y/n): ", end='')
        sys.stdout.flush()
        continue_choice = input().strip().lower()
        
        if continue_choice == '' or continue_choice == 'y':
            use_previous_settings = True
            # Restore settings from previous progress
            args.output_dir = os.path.dirname(existing_progress['output_file'])
            args.prefix = existing_progress['file_prefix']
            args.language = existing_progress['language'] or args.language
            args.slow = existing_progress['slow']
            print(f"✅ Continuing with previous settings")
        else:
            # User doesn't want to continue with previous settings
            print("\n" + "="*60)
            print("🔄 PREVIOUS PROGRESS MANAGEMENT")
            print("="*60)
            print("Would you like to delete all previous progress and start fresh?")
            print("This will remove all checkpoints for this file.")
            print("="*60)
            
            print("")  # Add an empty line
            # Move the cursor up one line
            sys.stdout.write("\033[F")
            print("Delete all progress? (y/n): ", end='')
            sys.stdout.flush()
            delete_choice = input().strip().lower()
            
            if delete_choice == 'y':
                # Delete all progress
                print(f"🗑️ Deleting all progress data for {os.path.basename(file_path)}...")
                
                # Delete checkpoint progress data
                checkpoint_mgr.delete_all_progress(file_path)
                
                # Delete chunk boundaries file using the TextProcessor's method
                if TextProcessor.cleanup_chunk_boundaries(file_path):
                    print(f"🧹 Removed boundaries file for: {os.path.basename(file_path)}")
                else:
                    print(f"ℹ️ No boundaries file found for: {os.path.basename(file_path)}")
                
                # Delete audio output folder if exists and user confirms
                if existing_progress and 'output_file' in existing_progress:
                    output_folder = os.path.dirname(existing_progress['output_file'])
                    if os.path.exists(output_folder):
                        print(f"\nOutput folder found: {output_folder}")
                        print("Do you want to delete the audio output files as well? (y/n): ", end='')
                        sys.stdout.flush()
                        delete_audio = input().strip().lower()
                        
                        if delete_audio == 'y':
                            try:
                                # Delete all mp3 files in the folder
                                audio_files = glob.glob(os.path.join(output_folder, "*.mp3"))
                                for audio_file in audio_files:
                                    os.remove(audio_file)
                                    print(f"🧹 Removed audio file: {os.path.basename(audio_file)}")
                                
                                # Try to remove the folder if empty
                                if os.path.exists(output_folder) and len(os.listdir(output_folder)) == 0:
                                    os.rmdir(output_folder)
                                    print(f"🧹 Removed empty output folder: {os.path.basename(output_folder)}")
                                elif os.path.exists(output_folder):
                                    print(f"⚠️ Output folder not empty, skipping folder removal")
                            except Exception as e:
                                print(f"⚠️ Error removing audio files or folder: {e}")
                
                print("✅ Progress deleted successfully!")
                print(f"ℹ️ Starting with new settings")
                print("🔄 Returning to file selection...")
                # Recursive call to go back to file selection
                return main(recursive_call=True)
            else:
                # User doesn't want to file selection either, just continue
                if not recursive_call:
                    print("🔄 Restarting file selection...")
                    # Recursive call to go back to file selection
                    return main(recursive_call=True)
                else:
                    # Already in a recursive call, just continue
                    file_path = FileManager.interactive_file_selection()
                    if file_path == "QUIT":
                        print("\n❌ Exiting file selection.\n")
                        return
                    elif not file_path:
                        print("❌ No file selected. Exiting.")
                        return
    
    # Ask for custom folder name only if not using previous settings
    if not args.info and not use_previous_settings:
        # Get default folder name from input file (without extension)
        default_folder_name = os.path.splitext(os.path.basename(file_path))[0]
        
        print("\n" + "="*60)
        print("📁 FOLDER AND FILE NAMING")
        print("="*60)
        print("Enter a name for the output folder. This will also be used as")
        print("the prefix for all audio files.")
        print(f"Default: '{default_folder_name}'")
        print("="*60)
        
        print("")  # Add an empty line
        # Move the cursor up one line
        sys.stdout.write("\033[F")
        print(f"Folder name (press Enter for '{default_folder_name}'): ", end='')
        sys.stdout.flush()
        custom_name = input().strip()
        
        if not custom_name:
            # Use the default folder name derived from the file
            custom_name = default_folder_name
            print(f"✅ Using default '{default_folder_name}' for folder and file names")
        else:
            print(f"✅ Using '{custom_name}' for folder and file names")
            
        # Use the custom name for both the output directory and the prefix
        args.output_dir = os.path.join(Config.get_default_output_dir(), custom_name)
        args.prefix = custom_name
    
    # Show process information
    print(f"\n🚀 Starting TTS conversion...")
    print(f"📁 File: {os.path.basename(file_path)}")
    
    # Display custom output info with folder and prefix details
    if not use_previous_settings:
        if args.prefix and args.prefix == os.path.basename(args.output_dir):
            # Using custom folder name as prefix
            print(f"🎯 Output: Folder '{args.prefix}' with audio files '{args.prefix} 1.mp3', '{args.prefix} 2.mp3', etc.")
        else:
            # Using standard output directory or different prefix
            print(f"🎯 Output: {args.output_dir}/{args.output or os.path.basename(file_path).replace('.txt', '')} (multiple audio files)")
            if args.prefix:
                print(f"🏷️ Audio file prefix: '{args.prefix}'")
        
        print(f"🌍 Language: {args.language}")
        print(f"🐌 Slow speech: {args.slow}")
    else:
        # When continuing with existing settings, make sure we're using the existing output folder
        if existing_progress and 'output_file' in existing_progress:
            output_folder = os.path.dirname(existing_progress['output_file'])
            print(f"🔄 Continuing with existing settings from previous session")
            print(f"🎯 Output: Using existing folder '{os.path.basename(output_folder)}'")
            
            # Ensure the output directory exists
            if not os.path.exists(args.output_dir):
                try:
                    os.makedirs(args.output_dir, exist_ok=True)
                    print(f"📁 Created output directory: {args.output_dir}")
                except Exception as e:
                    print(f"⚠️ Could not create output directory: {e}")
                    # Fall back to default output directory
                    args.output_dir = Config.get_default_output_dir()
                    print(f"📁 Using default output directory instead: {args.output_dir}")
        else:
            print(f"🔄 Continuing with existing settings from previous session")
    
    # Validate and create output directory
    print(f"\n📁 Validating output directory: {args.output_dir}")
    try:
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir, exist_ok=True)
            print(f"✅ Created output directory: {os.path.basename(args.output_dir)}")
        else:
            print(f"✅ Output directory exists: {os.path.basename(args.output_dir)}")
        
        # Test write permission
        test_file = os.path.join(args.output_dir, ".write_test")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            print(f"✅ Write permissions confirmed for output directory")
        except Exception as e:
            raise Exception(f"No write permission in output directory: {e}")
            
    except Exception as e:
        print(f"❌ Output directory validation failed: {e}")
        print(f"💡 Falling back to default output directory...")
        try:
            args.output_dir = Config.get_default_output_dir()
            os.makedirs(args.output_dir, exist_ok=True)
            print(f"✅ Using default output directory: {args.output_dir}")
        except Exception as fallback_error:
            print(f"❌ Could not create fallback directory: {fallback_error}")
            print(f"💡 Please check your permissions and try again.")
            sys.exit(1)

    # Show help and start processing
    show_help()
    print(f"\n💡 TIP: Type commands (p/pause, r/resume, s/stop, f/force, h/help) anytime during processing")
    print(f"    You'll see a prompt: 'You may input a command here: ' during processing")
    
    if not args.info:
        print("")  # Add an empty line
        # Move the cursor up one line
        sys.stdout.write("\033[F")
        print("Press Enter to start processing...", end='')
        sys.stdout.flush()
        input()
    
    # Process the file
    start_time = time.time()
    
    # Mark that processing is starting now (for shutdown handler)
    shutdown_handler.processing_started = True
    # Start the input listener thread now that we're about to begin processing
    shutdown_handler._start_input_listener()
    
    result = tts_processor.process_file(
        file_path,
        args.output,
        args.language,
        args.slow,
        args.output_dir,
        args.prefix
    )
    
    # Show final result
    total_time = time.time() - start_time
    if result:
        print(f"\n" + "=" * 80)
        print(f"🎉 TTS CONVERSION COMPLETED SUCCESSFULLY! 🎉")
        print(f"=" * 80)
        print(f"📁 Source file: {os.path.basename(file_path)}")
        print(f"🎵 Output location: {args.output_dir}")
        print(f"⏱️ Total processing time: {progress_tracker.format_time(total_time)}")
        print(f"✅ All audio files have been generated successfully!")
        print(f"=" * 80)
        
        # Final attempt to clean up progress files if they still exist
        cleanup_errors = []
        try:
            project_dir = Config.get_project_path()
            
            # Find and remove any checkpoint databases
            db_files = glob.glob(os.path.join(project_dir, "*.db"))
            for db_file in db_files:
                # Ensure we catch the tts_checkpoints.db file
                if "tts" in db_file.lower() or "checkpoint" in db_file.lower():
                    try:
                        os.remove(db_file)
                        print(f"🧹 Final cleanup - removed checkpoint database: {os.path.basename(db_file)}")
                    except Exception as e:
                        cleanup_errors.append(f"Database {os.path.basename(db_file)}: {e}")
            
            # Explicitly try to remove the main checkpoints database if it still exists
            checkpoints_db = os.path.join(project_dir, "tts_checkpoints.db")
            if os.path.exists(checkpoints_db):
                try:
                    os.remove(checkpoints_db)
                    print(f"🧹 Final cleanup - removed main checkpoints database")
                except Exception as e:
                    cleanup_errors.append(f"Main checkpoints database: {e}")
            
            # Find and remove any chunk boundary files
            boundary_files = glob.glob(os.path.join(project_dir, "*_chunk_boundaries.json"))
            for b_file in boundary_files:
                try:
                    os.remove(b_file)
                    print(f"🧹 Final cleanup - removed boundaries file: {os.path.basename(b_file)}")
                except Exception as e:
                    cleanup_errors.append(f"Boundaries file {os.path.basename(b_file)}: {e}")
            
            if cleanup_errors:
                print(f"⚠️ Some cleanup operations had issues:")
                for error in cleanup_errors:
                    print(f"   • {error}")
            else:
                print(f"✅ Final cleanup completed successfully!")
                
        except Exception as e:
            print(f"⚠️ Error during final cleanup: {e}")
    else:
        print(f"\n" + "=" * 80)
        if shutdown_handler.should_delete_progress():
            print(f"🛑 TTS CONVERSION STOPPED - PROGRESS DELETED")
            print(f"=" * 80)
            print(f"📁 Source file: {os.path.basename(file_path)}")
            print(f"🗑️ All progress data has been removed as requested.")
            print(f"⚠️ You will need to start from the beginning if you convert this file again.")
        else:
            print(f"⏸️ TTS CONVERSION STOPPED - PROGRESS SAVED")
            print(f"=" * 80)
            print(f"📁 Source file: {os.path.basename(file_path)}")
            print(f"💾 Progress has been saved and can be resumed later.")
            print(f"🔄 Run the script again with the same file to continue where you left off.")
        print(f"⏱️ Processing time before stop: {progress_tracker.format_time(total_time)}")
        print(f"=" * 80)
    
    print(f"\n👋 Thank you for using the Modern Text-to-Speech Converter!")
    print(f"🎵 Your audio files are ready to enjoy.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
