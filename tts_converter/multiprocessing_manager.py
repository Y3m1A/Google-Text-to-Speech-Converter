#!/usr/bin/env python3
"""
Multiprocessing manager for parallel TTS conversion.
"""
import os
import time
import threading
import queue
from .config import Config


class MultiprocessingManager:
    """Manages parallel TTS conversion with progress tracking."""
    
    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self.active_chunks = {}  # Track currently processing chunks
        self.completed_chunks = set()  # Track completed chunks
        self.failed_chunks = set()  # Track failed chunks
        self.display_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.stop_new_chunks = threading.Event()  # Flag to stop starting new chunks but let current ones finish
        self.display_lines_count = 0  # Track how many lines we've displayed
        self.last_display_update = 0  # Track last update time to avoid spam
        self._current_session_str = "0s"  # Current timing strings
        self._current_total_str = "0s"
        self._current_eta_str = "0s"
        
        # For resume functionality
        self.initial_completed_count = 0
        self.initial_temp_files = []
        
        # For static display tracking
        self.completed_lines_shown = set()  # Track which completed chunks we've already shown
        self.processing_lines_shown = set()  # Track which processing chunks we've already shown
        self.last_completed_chunks = set()  # Track completed chunks from last display update
        
    def process_chunks_parallel(self, chunks, start_index, output_dir, language, slow, prefix, 
                              progress_tracker, checkpoint_mgr, shutdown_handler, file_path, 
                              initial_temp_files=None):
        """Process chunks in parallel with live progress display."""
        
        # Store initial state for proper progress tracking
        self.initial_completed_count = start_index
        self.initial_temp_files = initial_temp_files or []
        
        # Setup chunk processing queue
        chunk_queue = queue.Queue()
        results_queue = queue.Queue()
        
        # Populate queue with remaining chunks
        for i in range(start_index, len(chunks)):
            chunk_info = {
                'index': i,
                'text': chunks[i],
                'output_dir': output_dir,
                'language': language,
                'slow': slow,
                'prefix': prefix,
                'total_chunks': len(chunks)
            }
            chunk_queue.put(chunk_info)
        
        # Start worker threads (using threads instead of processes for better control)
        workers = []
        for _ in range(min(self.max_workers, chunk_queue.qsize())):
            worker = threading.Thread(
                target=self._worker_thread,
                args=(chunk_queue, results_queue, shutdown_handler)
            )
            worker.daemon = True
            worker.start()
            workers.append(worker)
        
        # Start display updater thread
        display_thread = threading.Thread(
            target=self._display_updater,
            args=(results_queue, progress_tracker, checkpoint_mgr, file_path, chunks, output_dir, language, slow, prefix)
        )
        display_thread.daemon = True
        display_thread.start()
        
        # Initial display setup - show first 4 chunks as "processing"
        self._show_initial_display(progress_tracker, len(chunks), start_index)
        
        # Monitor completion
        total_to_process = len(chunks) - start_index
        stop_message_shown = False
        
        while not self.shutdown_event.is_set():
            if not shutdown_handler.should_continue():
                # Stop requested - set flag to prevent new chunks but let current ones finish
                if not self.stop_new_chunks.is_set():
                    self.stop_new_chunks.set()
                    if not stop_message_shown:
                        active_count = len(self.active_chunks)
                        if active_count > 0:
                            print(f"\n{Config.STOP_EMOJI} Stop requested. Allowing {active_count} active chunks to finish...")
                        stop_message_shown = True
                
                # Check if all active chunks have completed
                if len(self.active_chunks) == 0:
                    # All active chunks completed, now we can exit
                    self.shutdown_event.set()
                    break
                
            try:
                # Check completion status
                total_completed_this_session = len(self.completed_chunks)
                total_completed_overall = self.initial_completed_count + total_completed_this_session
                total_processed = total_completed_this_session + len(self.failed_chunks)
                remaining_chunks = len(chunks) - total_completed_overall
                
                # Check if we're done
                if remaining_chunks <= 0 or total_processed >= total_to_process:
                    break
                
                # Check if all workers are done and no more work
                if all(not worker.is_alive() for worker in workers) and chunk_queue.empty():
                    break
                    
                time.sleep(0.1)
            except KeyboardInterrupt:
                # Treat Ctrl+C like a normal stop, not force stop
                print(f"\n{Config.STOP_EMOJI} Stop requested via Ctrl+C")
                self.stop_new_chunks.set()
                break
        
        # Wait for all workers to finish
        for worker in workers:
            worker.join(timeout=5.0)
        
        # Wait for display thread to finish
        display_thread.join(timeout=2.0)
        
        return len(self.completed_chunks), self.failed_chunks
    
    def _worker_thread(self, chunk_queue, results_queue, shutdown_handler):
        """Worker thread to process individual chunks."""
        while not self.shutdown_event.is_set() and shutdown_handler.should_continue():
            # If stop was requested, don't start new chunks but let current ones finish
            if self.stop_new_chunks.is_set():
                break
                
            try:
                chunk_info = chunk_queue.get_nowait()
            except queue.Empty:
                break
            
            chunk_index = chunk_info['index']
            
            # Mark chunk as active
            with self.display_lock:
                self.active_chunks[chunk_index] = {
                    'start_time': time.time(),
                    'info': chunk_info
                }
            
            try:
                # Process the chunk
                success = self._process_single_chunk(chunk_info)
                
                # Report result
                result = {
                    'index': chunk_index,
                    'success': success,
                    'info': chunk_info,
                    'processing_time': time.time() - self.active_chunks[chunk_index]['start_time']
                }
                results_queue.put(result)
                
            except Exception as e:
                # Report failure
                result = {
                    'index': chunk_index,
                    'success': False,
                    'error': str(e),
                    'info': chunk_info,
                    'processing_time': time.time() - self.active_chunks[chunk_index]['start_time']
                }
                results_queue.put(result)
            
            finally:
                # Remove from active chunks
                with self.display_lock:
                    if chunk_index in self.active_chunks:
                        del self.active_chunks[chunk_index]
            
            chunk_queue.task_done()
    
    def _process_single_chunk(self, chunk_info):
        """Process a single chunk (extracted for reusability)."""
        from gtts import gTTS  # type: ignore
        
        index = chunk_info['index']
        text = chunk_info['text']
        output_dir = chunk_info['output_dir']
        language = chunk_info['language']
        slow = chunk_info['slow']
        prefix = chunk_info['prefix']
        
        # Generate filename
        if prefix:
            chunk_filename = f"{prefix} {index + 1}.mp3"
        else:
            chunk_filename = f"{Config.TEMP_FILE_PREFIX}{index + 1}.mp3"
        
        temp_file = os.path.join(output_dir, chunk_filename)
        
        # Convert to speech with retry logic
        max_attempts = Config.MAX_RETRIES
        for attempt in range(max_attempts):
            try:
                tts = gTTS(text=text, lang=language, slow=slow)
                tts.save(temp_file)
                return True
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise e
                delay = Config.RETRY_DELAY * (2 ** attempt)
                time.sleep(delay)
        
        return False
    
    def _display_updater(self, results_queue, progress_tracker, checkpoint_mgr, file_path, 
                        chunks, output_dir, language, slow, prefix):
        """Update display with parallel processing progress."""
        temp_files = []
        total_chunks = len(chunks)
        last_display_time = 0
        display_interval = 1.0  # Update timing every 1 second
        
        while not self.shutdown_event.is_set():
            try:
                # Process any completed chunks
                chunk_completed = False
                new_completions = set()
                while True:
                    try:
                        result = results_queue.get_nowait()
                        self._handle_chunk_result(result, temp_files, progress_tracker, 
                                                checkpoint_mgr, file_path, chunks, output_dir, 
                                                language, slow, prefix)
                        if result['success']:
                            new_completions.add(result['index'])
                        chunk_completed = True
                    except queue.Empty:
                        break
                
                # Only rebuild display if there are actual new completions
                if new_completions:
                    # Add new completion messages without overwriting existing ones
                    self._add_completion_messages(new_completions, total_chunks, progress_tracker)
                    # Track that we've shown these completions
                    self.last_completed_chunks.update(new_completions)
                elif chunk_completed:
                    # Just update timing for processing chunks without rebuilding completion messages
                    self._update_processing_timing(progress_tracker, total_chunks)
                else:
                    # Just update timing values periodically without changing display structure
                    current_time = time.time()
                    if (current_time - last_display_time) >= display_interval:
                        self._update_parallel_display(progress_tracker, total_chunks)
                        last_display_time = current_time
                
                # Check if we're done - continue until all chunks are processed or stopped
                total_completed_this_session = len(self.completed_chunks)
                total_completed_overall = self.initial_completed_count + total_completed_this_session
                total_processed = total_completed_this_session + len(self.failed_chunks)
                remaining_chunks = total_chunks - total_completed_overall
                
                # Exit conditions:
                # 1. All chunks completed
                # 2. Stop was requested AND no active chunks remaining
                if (remaining_chunks <= 0 or total_completed_overall >= total_chunks or 
                    (self.stop_new_chunks.is_set() and len(self.active_chunks) == 0)):
                    # Final display update
                    self._rebuild_static_display(progress_tracker, total_chunks)
                    break
                
                time.sleep(0.1)  # Small sleep to prevent excessive CPU usage
                
            except Exception as e:
                print(f"Display updater error: {e}")
                break
    
    def _handle_chunk_result(self, result, temp_files, progress_tracker, checkpoint_mgr, 
                           file_path, chunks, output_dir, language, slow, prefix):
        """Handle the result of a completed chunk."""
        index = result['index']
        success = result['success']
        chunk_info = result['info']
        
        if success:
            self.completed_chunks.add(index)
            
            # Generate filename for temp_files tracking
            if prefix:
                chunk_filename = f"{prefix} {index + 1}.mp3"
            else:
                chunk_filename = f"{Config.TEMP_FILE_PREFIX}{index + 1}.mp3"
            
            temp_file = os.path.join(output_dir, chunk_filename)
            temp_files.append(temp_file)
            
            # Save progress with correct total completed count
            total_completed = self.initial_completed_count + len(self.completed_chunks)
            all_temp_files = self.initial_temp_files + temp_files
            output_file = os.path.join(output_dir, f"{prefix or 'output'}.mp3")
            checkpoint_mgr.save_progress(
                file_path,
                len(chunks),
                total_completed,
                list(self.failed_chunks),
                all_temp_files,
                output_file,
                language,
                slow,
                'in_progress',
                prefix=prefix
            )
        else:
            self.failed_chunks.add(index)
            error = result.get('error', 'Unknown error')
            print(f"❌ Chunk {index + 1} failed: {error}")
    
    def _update_parallel_display(self, progress_tracker, total_chunks):
        """Update only the timing values in the static display without creating new lines."""
        current_time = time.time()
        
        # Limit update frequency to avoid spam
        if current_time - self.last_display_update < 1.0:  # Update every 1 second
            return
            
        with self.display_lock:
            self.last_display_update = current_time
            
            # Calculate timing info
            session_elapsed = time.time() - progress_tracker._start_time if progress_tracker._start_time else 0
            total_elapsed = session_elapsed + progress_tracker._previous_cumulative_time
            
            # Calculate ETA
            completed_count = len(self.completed_chunks)
            remaining_count = total_chunks - completed_count
            
            eta_str = "0s"
            if completed_count > 0 and remaining_count > 0:
                if session_elapsed > 0:
                    avg_time_per_chunk = session_elapsed / completed_count
                    estimated_remaining_time = avg_time_per_chunk * remaining_count
                    eta_str = progress_tracker.format_time(estimated_remaining_time)
            
            session_str = progress_tracker.format_time(session_elapsed)
            total_str = progress_tracker.format_time(total_elapsed)
            
            # Store the current values for when chunks complete and we need to rebuild display
            self._current_session_str = session_str
            self._current_total_str = total_str
            self._current_eta_str = eta_str
    
    def _show_initial_display(self, progress_tracker, total_chunks, start_index):
        """Show the initial static display with completed and processing chunks in order."""
        # Calculate timing info (will be 0s initially for new sessions)
        session_str = "0s"
        total_str = "0s"
        eta_str = "0s"
        
        # Store initial timing values
        self._current_session_str = session_str
        self._current_total_str = total_str
        self._current_eta_str = eta_str
        
        display_lines = []
        
        # First, show completed chunks from previous sessions (0 to start_index-1)
        for i in range(start_index):
            chunk_num = i + 1
            display_lines.append(f"✅ Chunk {chunk_num} completed")
            # Track that we've shown this completion
            self.completed_lines_shown.add(i)
            # Add to completed chunks set (these were completed in previous sessions)
            self.completed_chunks.add(i)
            self.last_completed_chunks.add(i)
        
        # Then show the first few chunks that need processing (up to 4) in numerical order
        chunks_displayed = 0
        max_initial_display = 4
        
        for i in range(start_index, total_chunks):
            if chunks_displayed >= max_initial_display:
                break
            chunk_num = i + 1
            display_lines.append(f"📝 Processing chunk {chunk_num}/{total_chunks} | Session: {session_str} | Total: {total_str} | ETA: {eta_str}")
            # Track that we've shown this processing line
            self.processing_lines_shown.add(i)
            chunks_displayed += 1
        
        # Print initial static display - this will be rebuilt as chunks complete
        print()  # Empty line before status
        for line in display_lines:
            print(line)
        
        print()  # Empty line
        print("Input your command here: ", end="", flush=True)
        
        # Track line count for future operations
        self.display_lines_count = len(display_lines)
    
    def _rebuild_static_display(self, progress_tracker, total_chunks):
        """Rebuild the entire static display when chunks complete."""
        with self.display_lock:
            # Calculate timing info
            session_elapsed = time.time() - progress_tracker._start_time if progress_tracker._start_time else 0
            total_elapsed = session_elapsed + progress_tracker._previous_cumulative_time
            
            # Calculate ETA - account for all completed chunks (including from previous sessions)
            total_completed_count = len(self.completed_chunks)  # This includes previously completed chunks
            remaining_count = total_chunks - total_completed_count
            
            eta_str = "0s"
            # Only calculate ETA based on chunks completed in this session for accuracy
            session_completed = total_completed_count - self.initial_completed_count
            if session_completed > 0 and remaining_count > 0 and session_elapsed > 0:
                avg_time_per_chunk = session_elapsed / session_completed
                estimated_remaining_time = avg_time_per_chunk * remaining_count
                eta_str = progress_tracker.format_time(estimated_remaining_time)
            
            session_str = progress_tracker.format_time(session_elapsed)
            total_str = progress_tracker.format_time(total_elapsed)
            
            # Update stored values
            self._current_session_str = session_str
            self._current_total_str = total_str
            self._current_eta_str = eta_str
            
            # Clear previous display if it exists
            if self.display_lines_count > 0:
                # Move cursor up to clear previous display
                print(f"\033[{self.display_lines_count + 2}A", end="")
                for _ in range(self.display_lines_count + 2):
                    print("\033[2K\033[1B", end="")  # Clear line and move down
                print(f"\033[{self.display_lines_count + 2}A", end="")  # Move back up
            
            # Build new display content with chunks in correct order
            display_lines = []
            max_lines = 8  # Show more lines to include both completed and processing
            
            # Show all completed chunks in order (up to a reasonable limit)
            completed_list = sorted(self.completed_chunks)
            lines_used = 0
            
            # Show completed chunks (but limit to avoid too much output)
            if completed_list:
                # If we have many completed chunks, show only the most recent ones
                if len(completed_list) > 4:
                    # Show first 2 and last 2 with dots in between if needed
                    for i in completed_list[:2]:
                        chunk_num = i + 1
                        display_lines.append(f"✅ Chunk {chunk_num} completed")
                        lines_used += 1
                    
                    if len(completed_list) > 4:
                        display_lines.append("... (other completed chunks)")
                        lines_used += 1
                    
                    for i in completed_list[-2:]:
                        if i not in completed_list[:2]:  # Avoid duplicates
                            chunk_num = i + 1
                            display_lines.append(f"✅ Chunk {chunk_num} completed")
                            lines_used += 1
                else:
                    # Show all completed chunks
                    for i in completed_list:
                        chunk_num = i + 1
                        display_lines.append(f"✅ Chunk {chunk_num} completed")
                        lines_used += 1
            
            # Show currently processing chunks
            active_list = sorted(self.active_chunks.keys())
            for chunk_idx in active_list:
                if lines_used >= max_lines:
                    break
                chunk_num = chunk_idx + 1
                display_lines.append(f"📝 Processing chunk {chunk_num}/{total_chunks} | Session: {session_str} | Total: {total_str} | ETA: {eta_str}")
                lines_used += 1
            
            # Show next few pending chunks (if there's room and they exist)
            next_chunk_to_process = max(max(completed_list) if completed_list else -1, 
                                      max(active_list) if active_list else -1) + 1
            chunks_to_show = min(3, max_lines - lines_used)  # Show up to 3 upcoming chunks
            
            for i in range(next_chunk_to_process, min(next_chunk_to_process + chunks_to_show, total_chunks)):
                if lines_used >= max_lines:
                    break
                chunk_num = i + 1
                display_lines.append(f"📝 Processing chunk {chunk_num}/{total_chunks} | Session: {session_str} | Total: {total_str} | ETA: {eta_str}")
                lines_used += 1
            
            # Print new static display
            for line in display_lines:
                print(line)
            
            print()  # Empty line
            print("Input your command here: ", end="", flush=True)
            
            # Update line count for next operation
            self.display_lines_count = len(display_lines)
    
    def _add_completion_messages(self, new_completions, total_chunks, progress_tracker):
        """Add completion messages for newly completed chunks without overwriting existing ones."""
        with self.display_lock:
            # Clear the input prompt line
            print("\r\033[K", end="")  # Clear current line
            print("\033[F\r\033[K", end="")  # Move up one line and clear it
            
            # Add completion messages for new chunks (in order)
            for chunk_index in sorted(new_completions):
                chunk_num = chunk_index + 1
                print(f"✅ Chunk {chunk_num} completed")
            
            # Calculate current timing for any processing status updates
            session_elapsed = time.time() - progress_tracker._start_time if progress_tracker._start_time else 0
            total_elapsed = session_elapsed + progress_tracker._previous_cumulative_time
            
            session_str = self._format_time(session_elapsed)
            total_str = self._format_time(total_elapsed)
            
            # Calculate ETA
            completed_count = len(self.completed_chunks)
            remaining_count = total_chunks - completed_count
            eta_str = "0s"
            if completed_count > 0 and remaining_count > 0 and session_elapsed > 0:
                avg_time_per_chunk = session_elapsed / completed_count
                estimated_remaining_time = avg_time_per_chunk * remaining_count
                eta_str = self._format_time(estimated_remaining_time)
            
            # Show a few processing chunks that are currently active or next in line
            active_list = sorted(self.active_chunks.keys())
            all_processed_or_active = self.completed_chunks | set(self.active_chunks.keys()) | self.failed_chunks
            
            # Find next chunks to show as processing
            next_chunks = []
            for i in range(total_chunks):
                if i not in all_processed_or_active:
                    next_chunks.append(i)
                    if len(next_chunks) >= 3:  # Show up to 3 next chunks
                        break
            
            # Combine active and next chunks
            chunks_to_show = active_list[:3]  # Show up to 3 active
            remaining_slots = 3 - len(chunks_to_show)
            chunks_to_show.extend(next_chunks[:remaining_slots])
            chunks_to_show.sort()
            
            # Display processing status for these chunks
            for chunk_index in chunks_to_show:
                if chunk_index < total_chunks:
                    chunk_num = chunk_index + 1
                    print(f"📝 Processing chunk {chunk_num}/{total_chunks} | Session: {session_str} | Total: {total_str} | ETA: {eta_str}")
            
            # Restore input prompt
            print()  # Empty line
            print("Input your command here: ", end="", flush=True)
    
    def _format_time(self, seconds):
        """Format time in a human-readable way."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def _update_processing_timing(self, progress_tracker, total_chunks):
        """Update timing information for processing chunks without rebuilding completion messages."""
        # For now, just do a minimal update - we could enhance this to update only timing
        # without touching completion messages, but this prevents unnecessary rebuilds
        pass
        
    def reset(self):
        """Reset the manager state for a new processing session."""
        self.shutdown_event.clear()
        self.stop_new_chunks.clear()
        self.completed_chunks.clear()
        self.failed_chunks.clear()
        self.active_chunks.clear()
        self.display_lines_count = 0
        self.last_display_update = 0
        self._current_session_str = "0s"
        self._current_total_str = "0s"
        self._current_eta_str = "0s"
        self.completed_lines_shown.clear()
        self.processing_lines_shown.clear()
        self.last_completed_chunks.clear()
