#!/usr/bin/env python3
"""
Shutdown and user command handling for the TTS converter.
"""
import sys
import time
import signal
import threading
from .config import Config

class ShutdownHandler:
    """Handles graceful shutdown and user commands."""
    
    def __init__(self, progress_tracker):
        self.shutdown_requested = False
        self.pause_requested = False
        self.delete_progress_requested = False
        self.force_stop_requested = False  # New flag for force stop
        self.progress_tracker = progress_tracker
        self.input_thread = None
        self.processing_started = False  # Flag to track if processing has started
        self._setup_signals()
        # Don't start input listener in constructor - will start it when processing begins
    
    def _setup_signals(self):
        """Setup signal handlers."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals (Ctrl+C/SIGINT and SIGTERM)."""
        if signum == signal.SIGINT:  # Ctrl+C
            # Set flags for immediate stop and force stop (to redo current chunk on resume)
            self.shutdown_requested = True
            self.force_stop_requested = True
            
            # Print exit message and exit immediately
            print("\n" + "="*60)
            print(f"{Config.STOP_EMOJI} Process interrupted by user (Ctrl+C)")
            print(f"💾 Progress saved - you can resume from the last completed chunk")
            print(f"⚠️  Current chunk will be redone when resumed")
            print("="*60 + "\n")
            
            # Force immediate exit
            sys.exit(1)
        else:  # SIGTERM or other signals
            self.shutdown_requested = True
            if self.processing_started:
                print(f"\n{Config.STOP_EMOJI} Received shutdown signal ({signum})")
                print("Finishing current chunk and saving progress...")
                try:
                    self.progress_tracker.stop("Interrupted")
                except Exception:
                    pass
            else:
                print("\n❌ Operation canceled.\n")
                sys.exit(0)
    
    def _start_input_listener(self):
        """Start background input listener."""
        self.input_thread = threading.Thread(target=self._listen_for_input, daemon=True)
        self.input_thread.start()
    
    def _listen_for_input(self):
        """Listen for user commands."""
        while not self.shutdown_requested:
            try:
                user_input = input().strip().lower()
                if user_input:
                    self._process_command(user_input)
            except (EOFError, KeyboardInterrupt):
                break
            except Exception:
                time.sleep(0.1)
    
    def _process_command(self, command):
        """Process user command."""
        # Only process commands if actual TTS processing has started
        if not self.processing_started:
            return
            
        if command in ['p', 'pause']:
            self.pause_requested = True
            print(f"{Config.PAUSE_EMOJI} Pause requested. Will pause after current chunk...")
        elif command in ['r', 'resume']:
            if self.pause_requested:
                self.pause_requested = False
                print(f"{Config.RESUME_EMOJI} Resuming...")
        elif command in ['s', 'stop']:
            print(f"{Config.STOP_EMOJI} Stop requested. Finishing current chunk...")
            self.shutdown_requested = True
        elif command in ['q', 'quit']:
            print(f"{Config.STOP_EMOJI} Quit requested. Finishing current chunk...")
            self.shutdown_requested = True
        elif command in ['f', 'force', 'fs', 'force-stop']:
            print(f"⚡ Force stop requested! Stopping immediately without finishing current chunk...")
            self.shutdown_requested = True
            self.force_stop_requested = True
        elif command in ['sd', 'stop-delete', 'delete', 'abort']:
            print(f"🗑️ Stop and delete progress requested. Will delete all progress after current chunk...")
            self.shutdown_requested = True
            self.delete_progress_requested = True
        elif command in ['h', 'help']:
            self._show_help()
        elif command in ['c', 'clear']:
            self._clear_console()
    
    def _show_help(self):
        """Show available commands."""
        print("=" * 60)
        print("📋 AVAILABLE COMMANDS:")
        print("=" * 60)
        print("p/pause     - Pause after current chunk")
        print("r/resume    - Resume from pause") 
        print("s/stop      - Stop and save progress")
        print("f/force     - Force stop immediately (will redo current chunk when resumed)")
        print("sd/delete   - Stop and DELETE all progress")
        print("q/quit      - Stop and save progress")
        print("h/help      - Show this help")
        print("c/clear     - Clear the console")
        print("Ctrl+C      - Force stop")
        print("=" * 60)
        print("⚠️  'sd' or 'delete' will remove ALL progress and temp files!")
        print("⚠️  'f' or 'force' will stop immediately and current chunk will be redone!")
        print("=" * 60)
    
    def _clear_console(self):
        """Clear the console screen."""
        # This is a cross-platform way to clear the console
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _clear_line_and_print(self, message):
        """Clear progress line and print message."""
        self._clear_line()
        sys.stdout.write(f"{message}\n")
        sys.stdout.flush()
    
    def _clear_line(self):
        """Clear current line."""
        sys.stdout.write('\r' + ' ' * Config.TERMINAL_WIDTH + '\r')
        sys.stdout.flush()
    
    def should_continue(self):
        """Check if processing should continue."""
        return not self.shutdown_requested
    
    def handle_pause(self):
        """Handle pause functionality."""
        if self.pause_requested:
            self._clear_line_and_print(f"{Config.PAUSE_EMOJI} PAUSED - Press 'r' and Enter to resume")
            while self.pause_requested and not self.shutdown_requested:
                time.sleep(0.1)
            if not self.shutdown_requested:
                self._clear_line_and_print(f"{Config.RESUME_EMOJI} RESUMED")
                time.sleep(1)
    
    def should_delete_progress(self):
        """Check if progress deletion was requested."""
        return self.delete_progress_requested
    
    def is_force_stop_requested(self):
        """Check if force stop was requested."""
        return self.force_stop_requested
    
    def should_force_stop(self):
        """Check if force stop was requested."""
        return self.force_stop_requested
