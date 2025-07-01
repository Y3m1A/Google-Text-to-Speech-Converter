#!/usr/bin/env python3
"""
Checkpoint and resume functionality for the TTS converter.
"""
import os
import glob
import json
import time
import stat
import sqlite3
import hashlib
from .config import Config

class CheckpointManager:
    """Manages checkpoint/resume functionality."""
    
    def __init__(self, db_path=None):
        # Store the main database path but don't create it yet
        if db_path is None:
            self.main_db_path = os.path.join(Config.get_project_path(), "tts_checkpoints.db")
        else:
            self.main_db_path = db_path
        self.current_db_path = self.main_db_path  # Default to main path
    
    def _get_prefixed_db_path(self, file_path, prefix=None):
        """Get the database path specific to this file/prefix."""
        project_dir = Config.get_project_path()
        
        # If no prefix provided, use the base filename without extension
        if not prefix:
            prefix = os.path.splitext(os.path.basename(file_path))[0]
            
        # Create a sanitized prefix for filenames
        safe_prefix = "".join(c for c in prefix if c.isalnum() or c in ('-', '_')).lower()
        
        # Create a unique identifier from the file path
        file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        
        # Create the prefixed database path
        return os.path.join(project_dir, f"tts_checkpoints_{safe_prefix}_{file_hash}.db")
    
    def _init_database(self, db_path):
        """Initialize checkpoint database at the specified path."""
        with sqlite3.connect(db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY,
                    file_path TEXT UNIQUE,
                    total_chunks INTEGER,
                    completed_chunks INTEGER,
                    failed_chunks TEXT,
                    temp_files TEXT,
                    output_file TEXT,
                    language TEXT,
                    slow INTEGER,
                    status TEXT,
                    cumulative_processing_time REAL DEFAULT 0.0,
                    session_start_time REAL,
                    file_prefix TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    
    def save_progress(self, file_path, total_chunks, completed_chunks, failed_chunks, 
                     temp_files, output_file, language, slow, status, cumulative_time=None, session_start=None, prefix=None):
        """Save processing progress with timing information."""
        # Get the prefixed database path
        self.current_db_path = self._get_prefixed_db_path(file_path, prefix)
        
        # Ensure the database exists
        if not os.path.exists(self.current_db_path):
            self._init_database(self.current_db_path)
        
        with sqlite3.connect(self.current_db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO checkpoints 
                (file_path, total_chunks, completed_chunks, failed_chunks, temp_files, 
                 output_file, language, slow, status, cumulative_processing_time, session_start_time, file_prefix, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (file_path, total_chunks, completed_chunks, json.dumps(failed_chunks),
                  json.dumps(temp_files), output_file, language, int(slow), status, 
                  cumulative_time or 0.0, session_start or time.time(), prefix))
    
    def load_progress(self, file_path):
        """Load existing progress with timing information."""
        # First check for any existing prefixed database for this file
        project_dir = Config.get_project_path()
        file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        possible_dbs = glob.glob(os.path.join(project_dir, f"tts_checkpoints_*_{file_hash}.db"))
        
        # Also check the main database for legacy entries
        if os.path.exists(self.main_db_path):
            possible_dbs.append(self.main_db_path)
        
        for db_path in possible_dbs:
            try:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.execute(
                        'SELECT * FROM checkpoints WHERE file_path = ? AND status != "completed"',
                        (file_path,)
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        # Store the current database path for future operations
                        self.current_db_path = db_path
                        
                        return {
                            'file_path': result[1],
                            'total_chunks': result[2], 
                            'completed_chunks': result[3],
                            'failed_chunks': json.loads(result[4]) if result[4] else [],
                            'temp_files': json.loads(result[5]) if result[5] else [],
                            'output_file': result[6],
                            'language': result[7],
                            'slow': bool(result[8]),
                            'status': result[9],
                            'cumulative_processing_time': result[10] if len(result) > 10 else 0.0,
                            'session_start_time': result[11] if len(result) > 11 else time.time(),
                            'file_prefix': result[12] if len(result) > 12 else None
                        }
            except sqlite3.Error:
                continue  # Try next database if this one fails
                
        return None
    
    def mark_completed(self, file_path):
        """Mark processing as completed."""
        if self.current_db_path:
            with sqlite3.connect(self.current_db_path) as conn:
                conn.execute(
                    'UPDATE checkpoints SET status = "completed", updated_at = CURRENT_TIMESTAMP WHERE file_path = ?',
                    (file_path,)
                )
            
            # After marking as completed, try to clean up this specific database
            try:
                # Check if there are any incomplete entries
                with sqlite3.connect(self.current_db_path) as conn:
                    cursor = conn.execute('SELECT COUNT(*) FROM checkpoints WHERE status != "completed"')
                    incomplete = cursor.fetchone()[0]
                
                if incomplete == 0:
                    # No incomplete entries, safe to remove this database
                    os.remove(self.current_db_path)
                    print(f"🧹 Removed completed checkpoint database: {os.path.basename(self.current_db_path)}")
            except Exception as e:
                print(f"⚠️ Could not clean up completed database: {e}")
    
    def cleanup_database_files(self, project_dir=None):
        """Clean up all checkpoint database files."""
        if project_dir is None:
            project_dir = Config.get_project_path()
            
        try:
            files_cleaned = 0
            
            # Find and remove all checkpoint database files
            db_files = glob.glob(os.path.join(project_dir, "tts_checkpoints_*.db"))
            for db_file in db_files:
                try:
                    with sqlite3.connect(db_file) as conn:
                        # Check if all entries are completed
                        cursor = conn.execute('SELECT COUNT(*) FROM checkpoints WHERE status != "completed"')
                        incomplete = cursor.fetchone()[0]
                        
                        if incomplete == 0:
                            # All entries completed, safe to remove
                            os.remove(db_file)
                            print(f"🧹 Removed completed checkpoint database: {os.path.basename(db_file)}")
                            files_cleaned += 1
                        else:
                            print(f"ℹ️ Database {os.path.basename(db_file)} has {incomplete} active conversions")
                except sqlite3.Error:
                    # Database might be corrupted
                    os.remove(db_file)
                    print(f"🧹 Removed corrupted database file: {os.path.basename(db_file)}")
                    files_cleaned += 1
                except Exception as e:
                    print(f"⚠️ Error processing database file {os.path.basename(db_file)}: {e}")
                    
            return files_cleaned
            
        except Exception as e:
            print(f"⚠️ Error during database cleanup: {e}")
            return 0
    
    def cleanup_progress_files(self, file_path=None):
        """Clean up progress files for a specific file or all completed files."""
        try:
            if file_path:
                # Get the specific database for this file
                self.current_db_path = self._get_prefixed_db_path(file_path)
                
                if os.path.exists(self.current_db_path):
                    with sqlite3.connect(self.current_db_path) as conn:
                        # Check if there are any incomplete entries
                        cursor = conn.execute('SELECT COUNT(*) FROM checkpoints WHERE status != "completed"')
                        incomplete = cursor.fetchone()[0]
                        
                        if incomplete == 0:
                            # No incomplete entries, safe to remove database
                            os.remove(self.current_db_path)
                            print(f"🧹 Removed completed checkpoint database: {os.path.basename(self.current_db_path)}")
                
                # Clean up boundaries file
                boundary_file = file_path + Config.CHUNK_BOUNDARIES_SUFFIX
                if os.path.exists(boundary_file):
                    os.remove(boundary_file)
                    print(f"🧹 Removed boundaries file: {os.path.basename(boundary_file)}")
            else:
                # Clean up all completed progress files
                self.cleanup_database_files()
                
                # Clean up all boundary files for completed conversions
                project_dir = Config.get_project_path()
                boundaries = glob.glob(os.path.join(project_dir, "*_chunk_boundaries.json"))
                for b_file in boundaries:
                    try:
                        # Check if there's an active database for this file
                        file_path = b_file[:-len(Config.CHUNK_BOUNDARIES_SUFFIX)]
                        db_path = self._get_prefixed_db_path(file_path)
                        
                        if not os.path.exists(db_path):
                            # No active database, safe to remove boundary file
                            os.remove(b_file)
                            print(f"🧹 Removed boundaries file: {os.path.basename(b_file)}")
                    except Exception as e:
                        print(f"⚠️ Could not check/remove boundary file: {e}")
                
        except Exception as e:
            print(f"⚠️ Error cleaning up progress files: {e}")
    
    def update_cumulative_time(self, file_path, additional_time):
        """Update the cumulative processing time for a file."""
        if self.current_db_path and os.path.exists(self.current_db_path):
            with sqlite3.connect(self.current_db_path) as conn:
                conn.execute('''
                    UPDATE checkpoints 
                    SET cumulative_processing_time = cumulative_processing_time + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE file_path = ?
                ''', (additional_time, file_path))
    
    def get_cumulative_time(self, file_path):
        """Get the cumulative processing time for a file."""
        if self.current_db_path and os.path.exists(self.current_db_path):
            with sqlite3.connect(self.current_db_path) as conn:
                cursor = conn.execute(
                    'SELECT cumulative_processing_time FROM checkpoints WHERE file_path = ?',
                    (file_path,)
                )
                result = cursor.fetchone()
                return result[0] if result else 0.0
        return 0.0
    
    def delete_all_progress(self, file_path):
        """Delete all progress data and temp files for a specific file."""
        project_dir = Config.get_project_path()
        
        try:
            print("🗑️ Deleting all progress data...")
            
            # Get the specific database path for this file
            db_path = self._get_prefixed_db_path(file_path)
            
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                    print(f"🗑️ Removed checkpoint database: {os.path.basename(db_path)}")
                except Exception as e:
                    print(f"⚠️ Could not remove checkpoint database: {e}")
            
            # Remove boundaries file
            boundary_file = file_path + Config.CHUNK_BOUNDARIES_SUFFIX
            if os.path.exists(boundary_file):
                os.remove(boundary_file)
                print(f"🗑️ Removed boundaries file: {os.path.basename(boundary_file)}")
            
            # Remove all temp chunk files for this conversion - check both current directory and output directory
            for search_dir in [project_dir, Config.get_default_output_dir()]:
                if os.path.exists(search_dir):
                    # Check for legacy pattern files (temp_chunk_*.mp3)
                    temp_pattern = os.path.join(search_dir, f"{Config.TEMP_FILE_PREFIX}*.mp3")
                    temp_files = glob.glob(temp_pattern)
                    
                    # Also check for custom named files (any mp3 files in the directory)
                    custom_pattern = os.path.join(search_dir, "*.mp3")
                    custom_files = glob.glob(custom_pattern)
                    
                    all_files = temp_files + custom_files
                    if all_files:
                        print(f"🗑️ Found {len(all_files)} audio files in {search_dir} to remove...")
                        for temp_file in all_files:
                            try:
                                os.remove(temp_file)
                                print(f"🗑️ Removed: {os.path.basename(temp_file)}")
                            except Exception as e:
                                print(f"⚠️ Could not remove {temp_file}: {e}")
            
            print("✅ All progress data deleted successfully!")
            
        except Exception as e:
            print(f"❌ Error deleting progress: {e}")
