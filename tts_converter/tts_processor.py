#!/usr/bin/env python3
"""
Core TTS conversion functionality.
"""
import os
import time
import json
import glob
from functools import wraps
from .config import Config
from .text_processor import TextProcessor

class TTSProcessor:
    """Handles text-to-speech conversion."""
    
    def __init__(self, checkpoint_mgr, progress_tracker, shutdown_handler):
        self.checkpoint_mgr = checkpoint_mgr
        self.progress_tracker = progress_tracker
        self.shutdown_handler = shutdown_handler
    
    def _setup_progress_tracking(self, file_path):
        """Setup progress tracking with cumulative time support for specific file."""
        self.progress_tracker._checkpoint_mgr = self.checkpoint_mgr
        self.progress_tracker._file_path = file_path
    
    @staticmethod
    def retry_with_backoff(max_retries=Config.MAX_RETRIES, base_delay=Config.RETRY_DELAY):
        """Decorator for retrying operations with exponential backoff."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                return None
            return wrapper
        return decorator
    
    @retry_with_backoff()
    def _convert_chunk_to_speech(self, text, filename, language='en', slow=False):
        """Convert single text chunk to speech."""
        from gtts import gTTS
        tts = gTTS(text=text, lang=language, slow=slow)
        tts.save(filename)
        return True
    
    def process_file(self, file_path, output_file=None, language='en', slow=False, output_dir=None, prefix=None):
        """Process entire file with checkpoint support."""
        try:
            # Setup progress tracking with cumulative time support
            self._setup_progress_tracking(file_path)
            
            # If no custom prefix provided, try to use output directory name as prefix
            if not prefix and output_dir:
                dir_name = os.path.basename(output_dir)
                if dir_name and dir_name != Config.DEFAULT_OUTPUT_DIR:
                    prefix = dir_name
            
            # Ensure output directory exists
            output_dir = Config.ensure_output_dir(output_dir)
            print(f"📁 Output directory: {output_dir}")
            if prefix:
                print(f"🏷️ Using prefix for audio files: {prefix}")
            
            # Set default output filename for folder path reference
            if not output_file:
                base_name = os.path.splitext(os.path.basename(file_path))[0] + ".mp3"
                output_file = os.path.join(output_dir, base_name)
            elif not os.path.isabs(output_file):
                # If output_file is not an absolute path, place it in the output directory
                output_file = os.path.join(output_dir, output_file)
            
            # Check for existing progress
            progress = self.checkpoint_mgr.load_progress(file_path)
            
            if progress:
                print("🔄 Resuming previous session...")
                chunks = TextProcessor.split_into_chunks(
                    TextProcessor.extract_from_file(file_path), 
                    file_path=file_path
                )
                temp_files, completed_chunks, failed_chunks = self._restore_progress(progress)
                last_chunk = self._find_last_completed_chunk(temp_files)
                
                # Restore output file and directory from progress to ensure consistency
                if progress.get('output_file'):
                    original_output_file = output_file
                    original_output_dir = output_dir
                    output_file = progress['output_file']
                    # Update output_dir to match the stored output file's directory
                    output_dir = os.path.dirname(output_file)
                    
                    # Log directory consistency
                    if original_output_dir != output_dir:
                        print(f"📁 Switched to previous output directory: {output_dir}")
                        print(f"   (was going to use: {original_output_dir})")
                    else:
                        print(f"📁 Confirmed output directory: {output_dir}")
                    
                    # Ensure the output directory exists
                    os.makedirs(output_dir, exist_ok=True)
                
                # If last session was force stopped (Ctrl+C), mark it in the progress
                if self.shutdown_handler.is_force_stop_requested():
                    self.checkpoint_mgr.save_progress(
                        file_path,
                        len(chunks),
                        completed_chunks,
                        list(failed_chunks),
                        temp_files,
                        output_file,
                        language,
                        slow,
                        'force_stopped',
                        prefix=prefix
                    )
                
                # Restore prefix from progress if available
                if not prefix and 'file_prefix' in progress and progress['file_prefix']:
                    prefix = progress['file_prefix']
                    print(f"🏷️ Restored prefix from previous session: {prefix}")
            else:
                print("🆕 Starting new conversion...")
                text = TextProcessor.extract_from_file(file_path)
                if not text.strip():
                    raise Exception("No text found in file")
                
                chunks = TextProcessor.split_into_chunks(text, file_path=file_path)
                temp_files = []
                completed_chunks = 0
                failed_chunks = set()
            
            # Initialize progress tracking
            self.progress_tracker.start(len(chunks))
            
            # Process remaining chunks
            for i in range(completed_chunks, len(chunks)):
                if self.shutdown_handler.should_continue():
                    # Mark start of chunk processing
                    self.progress_tracker.start_chunk()
                    
                    # Update progress info before processing
                    self.progress_tracker.update(
                        completed_chunks,
                        f"Processing chunk {i+1}/{len(chunks)}"
                    )
                    
                    # Get chunk output filename
                    if prefix:
                        # Use format "prefix N.mp3" for more user-friendly files
                        chunk_filename = f"{prefix} {i+1}.mp3"
                    else:
                        # Use technical format for non-prefixed files
                        chunk_filename = f"{Config.TEMP_FILE_PREFIX}{i+1}.mp3"
                    
                    temp_file = os.path.join(output_dir, chunk_filename)
                    
                    # Process the chunk with retry logic
                    max_attempts = Config.MAX_RETRIES
                    for attempt in range(max_attempts):
                        try:
                            # Convert chunk to speech
                            if self._convert_chunk_to_speech(
                                chunks[i],
                                temp_file,
                                language=language,
                                slow=slow
                            ):
                                # Record successful completion
                                temp_files.append(temp_file)
                                completed_chunks = i + 1
                                
                                # Update checkpoint progress
                                self.checkpoint_mgr.save_progress(
                                    file_path,
                                    len(chunks),
                                    completed_chunks,
                                    list(failed_chunks),
                                    temp_files,
                                    output_file,
                                    language,
                                    slow,
                                    'in_progress',
                                    prefix=prefix
                                )
                                
                                # Track chunk completion time
                                chunk_time = self.progress_tracker.complete_chunk()
                                
                                break  # Success - exit retry loop
                            
                        except Exception as e:
                            if attempt == max_attempts - 1:
                                # Final attempt failed
                                failed_chunks.add(i)
                                self.checkpoint_mgr.save_progress(
                                    file_path,
                                    len(chunks),
                                    completed_chunks,
                                    list(failed_chunks),
                                    temp_files,
                                    output_file,
                                    language,
                                    slow,
                                    'processing',
                                    prefix=prefix
                                )
                                raise Exception(
                                    f"Failed to convert chunk {i+1} after {max_attempts} attempts: {e}"
                                )
                            else:
                                # Retry
                                delay = Config.RETRY_DELAY * (2 ** attempt)
                                print(f"\n⚠️ Error processing chunk {i+1}, retrying in {delay}s: {e}")
                                time.sleep(delay)
                
                if not self.shutdown_handler.should_continue():
                    # Update progress one last time before stopping
                    self.checkpoint_mgr.save_progress(
                        file_path,
                        len(chunks),
                        completed_chunks,
                        list(failed_chunks),
                        temp_files,
                        output_file,
                        language,
                        slow,
                        'force_stopped' if self.shutdown_handler.is_force_stop_requested() else 'stopped',
                        prefix=prefix
                    )
                    break
            
            self.progress_tracker.stop("Processing complete")
            
            # Check if all chunks were completed
            all_chunks_completed = (completed_chunks == len(chunks) and len(failed_chunks) == 0)
            
            # Clean up progress files if all chunks were completed
            if all_chunks_completed and self.shutdown_handler.should_continue():
                self._cleanup_after_processing(file_path)
                print(f"\n✅ All audio files saved to directory: {output_dir}")
                print(f"📁 Created {len(temp_files)} individual audio files")
            
            return len(temp_files) > 0 and all_chunks_completed
        
        except Exception as e:
            self.progress_tracker.stop("Error")
            raise e
    
    def _process_single_chunk(self, chunk, output_file, language, slow, file_path):
        """Process single chunk."""
        try:
            self.progress_tracker.start(1, "Processing single chunk...")
            success = self._convert_chunk_to_speech(chunk, output_file, language, slow)
            
            # Check for force stop after conversion
            if self.shutdown_handler.should_force_stop():
                # Delete the incomplete audio file if force stop requested
                if os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                        print(f"\n⚡ Force stop requested - removed incomplete file: {os.path.basename(output_file)}")
                    except Exception as e:
                        print(f"\n⚠️ Force stop: Could not remove incomplete file: {e}")
                
                # Save progress with force_stopped status
                self.checkpoint_mgr.save_progress(
                    file_path, 1, 0, [], 
                    [], output_file, language, slow, 'force_stopped'
                )
                
                print(f"\n⚡ Force stopped during chunk processing. This will be redone when processing resumes.")
                self.progress_tracker.stop("Force stopped")
                return False
            
            if success:
                self.progress_tracker.update(1, "Completed!")
                self.progress_tracker.stop("Complete")
                # Single chunk completed successfully - clean up all progress files
                print("🎉 Single chunk completed successfully!")
                self.checkpoint_mgr.cleanup_progress_files(file_path)
                TextProcessor.cleanup_chunk_boundaries(file_path)
                return True
        except Exception as e:
            self.progress_tracker.stop("Failed")
            raise e
    
    def _process_multiple_chunks(self, chunks, temp_files, completed_chunks, 
                               failed_chunks, last_chunk, output_file, language, slow, file_path, prefix=None, output_dir=None):
        """Process multiple chunks with checkpointing."""
        try:
            self.progress_tracker.start(len(chunks), "Initializing...")
            self.progress_tracker.update(completed_chunks, "Starting chunk processing...")
            
            # Extract output directory from output file path
            output_dir = output_dir or os.path.dirname(output_file)
            if not output_dir:
                output_dir = Config.DEFAULT_OUTPUT_DIR
                output_file = os.path.join(output_dir, os.path.basename(output_file))
            
            # If no custom prefix provided, try to use output directory name as prefix
            if not prefix:
                dir_name = os.path.basename(output_dir)
                if dir_name and dir_name != Config.DEFAULT_OUTPUT_DIR:
                    prefix = dir_name
                    print(f"🏷️ Using directory name as prefix: {prefix}")
            
            # Make sure the output directory exists
            Config.ensure_output_dir(output_dir)
            
            # Process remaining chunks
            for i in range(last_chunk + 1, len(chunks)):
                if not self.shutdown_handler.should_continue():
                    break
                
                self.shutdown_handler.handle_pause()
                if not self.shutdown_handler.should_continue():
                    break
                
                # Process chunk
                temp_file = Config.get_temp_filename(i, output_dir, prefix)
                self.progress_tracker.update(completed_chunks, f"Processing chunk {i+1}/{len(chunks)}")
                self.progress_tracker.start_chunk()  # Start timing this chunk
                
                # Retry logic
                for attempt in range(Config.MAX_RETRIES):
                    try:
                        success = self._convert_chunk_to_speech(chunks[i], temp_file, language, slow)
                        
                        # Check for force stop request after conversion
                        if self.shutdown_handler.should_force_stop():
                            # Delete the incomplete audio file if force stop requested
                            if os.path.exists(temp_file):
                                try:
                                    os.remove(temp_file)
                                    print(f"\n⚡ Force stop requested - removed incomplete file: {os.path.basename(temp_file)}")
                                except Exception as e:
                                    print(f"\n⚠️ Force stop: Could not remove incomplete file: {e}")
                            
                            # Save progress with force_stopped status
                            self.checkpoint_mgr.save_progress(
                                file_path, len(chunks), completed_chunks, list(failed_chunks),
                                temp_files, output_file, language, slow, 'force_stopped',
                                prefix=prefix
                            )
                            
                            print(f"\n⚡ Force stopped during chunk {i+1}. This chunk will be redone when processing resumes.")
                            # Don't update progress for this chunk
                            self.progress_tracker.stop("Force stopped")
                            return False
                            
                        if success:
                            # Update progress
                            temp_files.append(temp_file)
                            completed_chunks += 1
                            chunk_time = self.progress_tracker.complete_chunk()
                            
                            # Save progress
                            self.checkpoint_mgr.save_progress(
                                file_path, len(chunks), completed_chunks, list(failed_chunks),
                                temp_files, output_file, language, slow, 'processing',
                                prefix=prefix
                            )
                            
                            # Show progress
                            file_stats = os.stat(temp_file)
                            file_size = file_stats.st_size / (1024 * 1024)  # Convert to MB
                            time_str = self.progress_tracker.format_time(chunk_time) if chunk_time else 'N/A'
                            self.progress_tracker.update(
                                completed_chunks, 
                                f"Completed chunk {i+1}/{len(chunks)} in {time_str} | Size: {file_size:.2f} MB"
                            )
                            break
                    except Exception as e:
                        if attempt == Config.MAX_RETRIES - 1:
                            # Max retries reached, mark as failed
                            failed_chunks.add(i)
                            print(f"\n{Config.ERROR_EMOJI} Failed to process chunk {i+1} after {Config.MAX_RETRIES} attempts: {e}")
                            
                            # Save progress with failed chunk
                            self.checkpoint_mgr.save_progress(
                                file_path, len(chunks), completed_chunks, list(failed_chunks),
                                temp_files, output_file, language, slow, 'processing',
                                prefix=prefix
                            )
                        else:
                            # Retry
                            delay = Config.RETRY_DELAY * (2 ** attempt)
                            print(f"\n⚠️ Error processing chunk {i+1}, retrying in {delay}s: {e}")
                            time.sleep(delay)
                
                if not self.shutdown_handler.should_continue():
                    break
            
            self.progress_tracker.stop("Processing complete")
            
            # Check if all chunks were completed
            all_chunks_completed = (completed_chunks == len(chunks) and len(failed_chunks) == 0)
            
            # Clean up progress files if all chunks were completed
            if all_chunks_completed and self.shutdown_handler.should_continue():
                self._cleanup_after_processing(file_path)
                print(f"\n✅ All audio files saved to directory: {output_dir}")
                print(f"📁 Created {len(temp_files)} individual audio files")
            
            return len(temp_files) > 0 and all_chunks_completed
        
        except Exception as e:
            self.progress_tracker.stop("Error")
            raise e
    
    def _cleanup_after_processing(self, file_path):
        """Clean up progress files after successful processing."""
        try:
            # Clean up progress database and boundaries
            self.checkpoint_mgr.cleanup_progress_files(file_path)
            self.checkpoint_mgr.mark_completed(file_path)
            TextProcessor.cleanup_chunk_boundaries(file_path)
            print("✅ Marked conversion as completed in database")
        except Exception as e:
            print(f"⚠️ Could not clean up all progress files: {e}")
    
    def _restore_progress(self, progress):
        """Restore progress from checkpoint."""
        temp_files = progress.get('temp_files', [])
        completed_chunks = progress.get('completed_chunks', 0)
        failed_chunks = set(progress.get('failed_chunks', []))
        
        # Check if last session was force stopped (Ctrl+C or force stop command)
        was_force_stopped = progress.get('status') == 'force_stopped'
        
        # If force stopped, we need to decrement the completed chunks to redo the last one
        if was_force_stopped and completed_chunks > 0:
            print(f"\n" + "="*60)
            print("⚡ RESUMING FROM FORCE STOP")
            print("="*60)
            print(f"Last session was interrupted during chunk {completed_chunks}")
            completed_chunks -= 1
            
            # If we have temp files, remove the last one as it may be incomplete
            if temp_files and len(temp_files) > 0:
                last_temp_file = temp_files[-1]
                temp_files = temp_files[:-1]
                
                # Delete the potentially incomplete file if it exists
                if os.path.exists(last_temp_file):
                    try:
                        os.remove(last_temp_file)
                        print(f"🧹 Removed incomplete chunk file: {os.path.basename(last_temp_file)}")
                    except Exception as e:
                        print(f"⚠️ Could not remove incomplete chunk file: {e}")
                        
            print(f"💡 Will restart from chunk {completed_chunks + 1}")
            print("="*60 + "\n")
        
        # Verify temp files exist
        existing_files = [f for f in temp_files if os.path.exists(f)]
        if len(existing_files) != len(temp_files):
            print(f"⚠️ Some temporary files are missing: found {len(existing_files)} of {len(temp_files)}")
            completed_chunks = len(existing_files)
        
        print(f"📊 Restored progress: {completed_chunks} chunks completed, {len(failed_chunks)} chunks failed")
        print(f"📁 Found {len(existing_files)} existing audio chunks")
        
        # Display previously completed chunks
        if existing_files:
            print("\n" + "="*60)
            print("🔄 PREVIOUSLY COMPLETED CHUNKS")
            print("="*60)
            
            # Sort files by chunk number to display in order
            sorted_files = sorted(existing_files, key=lambda f: self._extract_chunk_number(f) or float('inf'))
            
            for temp_file in sorted_files:
                chunk_num = self._extract_chunk_number(temp_file)
                if chunk_num is not None:
                    # Get file stats
                    try:
                        file_stats = os.stat(temp_file)
                        file_size = file_stats.st_size / (1024 * 1024)  # Convert to MB
                        print(f"✅ Chunk {chunk_num} completed | Size: {file_size:.2f} MB")
                    except Exception:
                        print(f"✅ Chunk {chunk_num} completed")
            
            print("="*60)
            print(f"Next chunk to process: #{completed_chunks + 1}")
            print("="*60 + "\n")
        
        return existing_files, completed_chunks, failed_chunks
    
    def _extract_chunk_number(self, temp_file):
        """Extract chunk number from temp file name."""
        try:
            filename = os.path.basename(temp_file)
            # Handle different naming patterns
            if filename.startswith(Config.TEMP_FILE_PREFIX):
                # Legacy pattern: temp_chunk_X.mp3
                parts = filename.replace(Config.TEMP_FILE_PREFIX, '').replace('.mp3', '').split('_')
                if parts and parts[0].isdigit():
                    return int(parts[0])
            
            # Custom prefix patterns like "MyPrefix 5.mp3"
            parts = os.path.splitext(filename)[0].split()
            if parts and parts[-1].isdigit():
                return int(parts[-1])
                
        except Exception:
            pass
        
        return None
    
    def _find_last_completed_chunk(self, temp_files):
        """Find the last completed chunk index from temp file names."""
        last_chunk = -1
        
        for temp_file in temp_files:
            chunk_num = self._extract_chunk_number(temp_file)
            if chunk_num is not None:
                # Adjust to 0-based index for internal use
                chunk_idx = chunk_num - 1
                last_chunk = max(last_chunk, chunk_idx)
        
        return last_chunk
