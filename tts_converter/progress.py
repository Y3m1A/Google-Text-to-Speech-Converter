#!/usr/bin/env python3
"""
Progress tracking functionality for the TTS converter.
"""
import time
import threading
from .config import Config

class ProgressTracker:
    """Enhanced progress tracker with improved time estimation and cumulative time tracking."""
    
    def __init__(self, checkpoint_mgr=None, file_path=None):
        self.total_items = 0
        self.completed_items = 0
        self.current_status = ""
        self._lock = threading.Lock()
        self._last_status_length = 0
        self._start_time = None
        self._chunk_times = []  # Track individual chunk completion times
        self._current_chunk_start = None  # Track current chunk start time
        self._checkpoint_mgr = checkpoint_mgr  # For updating cumulative time
        self._file_path = file_path  # File being processed
        self._previous_cumulative_time = 0.0  # Time from previous sessions
        
    def start(self, total_items, status="Starting..."):
        """Start progress tracking with cumulative time support."""
        with self._lock:
            self.total_items = total_items
            self.completed_items = 0
            self.current_status = status
            self._last_status_length = 0
            self._start_time = time.time()
            
            # Load previous cumulative time if available
            if self._checkpoint_mgr and self._file_path:
                self._previous_cumulative_time = self._checkpoint_mgr.get_cumulative_time(self._file_path)
        
        # Print initial status without clearing anything
        print(f"📊 Processing {total_items} chunks...")
        print("Input your command here: ", end="", flush=True)
    
    def update(self, completed, status=""):
        """Update progress status, keeping command prompt at the bottom."""
        with self._lock:
            self.completed_items = completed
            if status:
                self.current_status = status
                self._print_status_with_timing(status)
    
    def _print_status_with_timing(self, message):
        """Print status message with timing information, keeping input prompt at bottom."""
        # Calculate timing information for display
        session_elapsed = time.time() - self._start_time if self._start_time else 0
        total_elapsed = session_elapsed + self._previous_cumulative_time
        
        # Calculate ETA for remaining chunks
        eta_str = "calculating..."
        if self.completed_items > 0 and self.total_items > 0:
            remaining_items = self.total_items - self.completed_items
            if remaining_items > 0:
                # Use session time for ETA calculation (more recent performance)
                if session_elapsed > 0:
                    # Calculate average time per chunk in this session
                    avg_time_per_item = session_elapsed / self.completed_items
                    estimated_remaining_time = avg_time_per_item * remaining_items
                    eta_str = self.format_time(estimated_remaining_time)
                else:
                    eta_str = "calculating..."
            else:
                eta_str = "complete"
        
        # Clear the current line and print updated status
        print(f"\r{' ' * 120}", end="")  # Clear the line
        
        # Print timing info on the next line and return to input prompt
        session_str = self.format_time(session_elapsed)
        total_str = self.format_time(total_elapsed)
        
        if self.total_items > 0:
            next_chunk = self.completed_items + 1
            if next_chunk <= self.total_items:
                print(f"\r📝 Processing chunk {next_chunk}/{self.total_items} | Session: {session_str} | Total: {total_str} | ETA: {eta_str}")
            else:
                print(f"\r📝 Completed {self.completed_items}/{self.total_items} | Session: {session_str} | Total: {total_str}")
        else:
            print(f"\r📝 {message} | Session: {session_str} | Total: {total_str}")
            
        print("\nInput your command here: ", end="", flush=True)
    
    def stop(self, final_status="Stopped"):
        """Stop progress tracking."""
        with self._lock:
            session_elapsed = time.time() - self._start_time if self._start_time else 0
            total_elapsed = session_elapsed + self._previous_cumulative_time
            
            # Update cumulative time in database if possible
            if self._checkpoint_mgr and self._file_path:
                self._checkpoint_mgr.update_cumulative_time(self._file_path, session_elapsed)
        
        # Clear any partial progress lines and print final status
        print(f"\r{' ' * 120}", end="")  # Clear the line
        print(f"\r📝 {final_status}")
    
    def format_time(self, seconds):
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
    
    def start_chunk(self):
        """Mark the start of chunk processing for timing."""
        self._current_chunk_start = time.time()
    
    def complete_chunk(self):
        """Mark chunk completion and return processing time."""
        if self._current_chunk_start:
            chunk_time = time.time() - self._current_chunk_start
            self._chunk_times.append(chunk_time)
            self._current_chunk_start = None
            return chunk_time
        return 0
    
    def complete_chunk_with_size(self, chunk_size=""):
        """Complete a chunk and show completion message with size info."""
        chunk_time = self.complete_chunk()  # Call existing method
        
        with self._lock:
            # Clear the current line and show completion
            print(f"\r{' ' * 120}", end="")  # Clear the line
            size_info = f" ({chunk_size})" if chunk_size else ""
            print(f"\r✅ Chunk {self.completed_items}/{self.total_items} Completed{size_info}")
            
            # Now show processing info for next chunk
            session_elapsed = time.time() - self._start_time if self._start_time else 0
            total_elapsed = session_elapsed + self._previous_cumulative_time
            
            # Calculate ETA for remaining chunks
            eta_str = "calculating..."
            if self.completed_items > 0 and self.total_items > 0:
                remaining_items = self.total_items - self.completed_items
                if remaining_items > 0:
                    if session_elapsed > 0:
                        avg_time_per_item = session_elapsed / self.completed_items
                        estimated_remaining_time = avg_time_per_item * remaining_items
                        eta_str = self.format_time(estimated_remaining_time)
                    else:
                        eta_str = "calculating..."
                else:
                    eta_str = "complete"
            
            session_str = self.format_time(session_elapsed)
            total_str = self.format_time(total_elapsed)
            
            # Show next chunk processing info if not complete
            next_chunk = self.completed_items + 1
            if next_chunk <= self.total_items:
                print(f"📝 Processing chunk {next_chunk}/{self.total_items} | Session: {session_str} | Total: {total_str} | ETA: {eta_str}")
            else:
                print(f"📝 All chunks completed! | Session: {session_str} | Total: {total_str}")
                
            print("\nInput your command here: ", end="", flush=True)
        
        return chunk_time

    def is_running(self):
        """Check if progress tracking is currently running."""
        return self._start_time is not None