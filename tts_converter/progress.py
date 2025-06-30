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
        
        print(f"📊 Processing {total_items} chunks...")
        if self._previous_cumulative_time > 0:
            prev_time_str = self.format_time(self._previous_cumulative_time)
            print(f"⏱️ Previous processing time: {prev_time_str}")
        print()  # Add a new line for the status updates to appear below
        if status != "Starting...":
            self._print_status(status)
    
    def update(self, completed, status=""):
        """Update progress status on the same line."""
        with self._lock:
            self.completed_items = completed
            if status:
                self.current_status = status
                # For all status updates, use the appropriate print method
                self._print_status_with_timing(status)
                    
    def _print_status_with_timing(self, message):
        """Print status message with enhanced timing information."""
        # Calculate session elapsed time
        session_elapsed = time.time() - self._start_time if self._start_time else 0
        session_elapsed_str = self.format_time(session_elapsed)
        
        # Calculate total elapsed time (including previous sessions)
        total_elapsed = self._previous_cumulative_time + session_elapsed
        total_elapsed_str = self.format_time(total_elapsed)
        
        # Enhanced time remaining calculation
        if self.completed_items > 0 and self.total_items > 0:
            remaining_items = self.total_items - self.completed_items
            
            # Use recent chunk times for better accuracy (last 5 chunks or all if fewer)
            recent_chunks = self._chunk_times[-5:] if len(self._chunk_times) >= 5 else self._chunk_times
            
            if len(recent_chunks) >= 2:
                # Use average of recent chunk times (more accurate for current conditions)
                avg_recent_time = sum(recent_chunks) / len(recent_chunks)
                eta_seconds = avg_recent_time * remaining_items
                timing_info = f" | Session: {session_elapsed_str} | Total: {total_elapsed_str} | Remaining: {self.format_time(eta_seconds)}"
            else:
                # Fall back to overall average for first few chunks
                avg_time_per_item = session_elapsed / self.completed_items
                eta_seconds = avg_time_per_item * remaining_items
                timing_info = f" | Session: {session_elapsed_str} | Total: {total_elapsed_str} | Remaining: {self.format_time(eta_seconds)}"
        else:
            timing_info = f" | Session: {session_elapsed_str} | Total: {total_elapsed_str}"
        
        # Add current chunk progress if available
        if self._current_chunk_start:
            chunk_elapsed = time.time() - self._current_chunk_start
            timing_info += f" | Current chunk: {self.format_time(chunk_elapsed)}"
        
        # Check if the message indicates a new chunk processing has started
        # If it's a new chunk, print on a new line
        if "Processing chunk" in message and self.completed_items > 0:
            # First clear the previous line if needed
            if self._last_status_length > 0:
                print()  # Move to a new line instead of clearing the current one
            
            # Print the new status with timing on a new line
            status_line = f"📝 {message}{timing_info}"
            print(status_line, flush=True)
            self._last_status_length = 0  # Reset since we've moved to a new line
        elif "Starting chunk processing" in message:
            # For "Starting chunk processing..." message, don't add timing info
            if self._last_status_length > 0:
                print('\r' + ' ' * self._last_status_length, end='')
                
            # Print the status without timing information on a new line
            print(f"\n📝 {message}", flush=True)
            self._last_status_length = 0  # Reset since we've moved to a new line
        else:
            # For other status updates or the first chunk, update the current line
            # Clear the previous line by printing spaces
            if self._last_status_length > 0:
                print('\r' + ' ' * self._last_status_length, end='')
            
            # Print the new status with timing
            status_line = f"\r📝 {message}{timing_info}"
            print(status_line, end='', flush=True)
            self._last_status_length = len(status_line)
    
    def _print_status(self, message):
        """Print status message, overwriting the previous line or creating a new line for new chunks."""
        # Check if the message indicates a new chunk processing has started
        if "Processing chunk" in message and self.completed_items > 0:
            # For new chunks, print on a new line
            if self._last_status_length > 0:
                print()  # Move to a new line
            
            status_line = f"📝 {message}"
            print(status_line, flush=True)
            self._last_status_length = 0  # Reset since we've moved to a new line
        elif "Starting chunk processing" in message:
            # For "Starting chunk processing..." message, print on a new line
            if self._last_status_length > 0:
                print()  # Move to a new line
            
            print(f"📝 {message}", flush=True)
            self._last_status_length = 0  # Reset since we've moved to a new line
        else:
            # For other status updates or the first chunk, update the current line
            # Clear the previous line by printing spaces
            if self._last_status_length > 0:
                print('\r' + ' ' * self._last_status_length, end='')
            
            # Print the new status
            status_line = f"\r📝 {message}"
            print(status_line, end='', flush=True)
            self._last_status_length = len(status_line)
    
    def format_time(self, seconds):
        """Format time in a readable format."""
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
    
    def stop(self, final_message="Complete"):
        """Stop progress tracking and show final statistics with cumulative time."""
        # Always create a new line for the final message
        print()  # Ensure we're on a new line
        
        # Calculate session elapsed time
        session_elapsed = time.time() - self._start_time if self._start_time else 0
        session_elapsed_str = self.format_time(session_elapsed)
        
        # Calculate total cumulative time
        total_cumulative = self._previous_cumulative_time + session_elapsed
        total_cumulative_str = self.format_time(total_cumulative)
        
        # Update cumulative time in database
        if self._checkpoint_mgr and self._file_path and session_elapsed > 0:
            self._checkpoint_mgr.update_cumulative_time(self._file_path, session_elapsed)
        
        print(f"🏁 {final_message}")
        print(f"⏱️ Session time: {session_elapsed_str}")
        print(f"🕒 Total processing time: {total_cumulative_str}")
        
        # Show chunk processing statistics if available
        stats = self.get_chunk_stats()
        if stats and stats['count'] > 1:
            print(f"📊 Chunk Statistics:")
            print(f"   • Average time per chunk: {self.format_time(stats['average'])}")
            print(f"   • Fastest chunk: {self.format_time(stats['minimum'])}")
            print(f"   • Slowest chunk: {self.format_time(stats['maximum'])}")
            print(f"   • Total chunks processed: {stats['count']}")
        
        print()  # Add newline for terminal input
        self._last_status_length = 0
    
    def show_completion(self, item_name):
        """Show completion message for an item."""
        # Always create a new line for completion messages
        print()  # Ensure we're on a new line
        print(f"{Config.COMPLETION_EMOJI} {item_name} completed!")
        print()  # Add newline for terminal input
        self._last_status_length = 0
    
    def show_status(self, message):
        """Show a status message."""
        self._print_status(message)
    
    def start_chunk(self):
        """Mark the start of processing a new chunk."""
        self._current_chunk_start = time.time()
    
    def complete_chunk(self):
        """Mark the completion of a chunk and record its processing time."""
        if self._current_chunk_start:
            chunk_time = time.time() - self._current_chunk_start
            self._chunk_times.append(chunk_time)
            self._current_chunk_start = None
            return chunk_time
        return None
    
    def get_chunk_stats(self):
        """Get statistics about chunk processing times."""
        if not self._chunk_times:
            return None
        
        avg_time = sum(self._chunk_times) / len(self._chunk_times)
        min_time = min(self._chunk_times)
        max_time = max(self._chunk_times)
        
        return {
            'average': avg_time,
            'minimum': min_time,
            'maximum': max_time,
            'count': len(self._chunk_times)
        }
