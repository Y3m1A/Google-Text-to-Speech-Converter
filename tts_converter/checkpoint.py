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
from .config import Config

class CheckpointManager:
    """Manages checkpoint/resume functionality."""
    
    def __init__(self, db_path=None):
        if db_path is None:
            # Use a path relative to the project directory
            self.db_path = os.path.join(Config.get_project_path(), "tts_checkpoints.db")
        else:
            self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize checkpoint database."""
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT * FROM checkpoints WHERE file_path = ? AND status != "completed"',
                (file_path,)
            )
            result = cursor.fetchone()
            
            if result:
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
        return None
    
    def mark_completed(self, file_path):
        """Mark processing as completed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE checkpoints SET status = "completed", updated_at = CURRENT_TIMESTAMP WHERE file_path = ?',
                (file_path,)
            )
    
    def cleanup_temp_files(self, temp_files):
        """Clean up temporary files - PRESERVING .mp3 files as they are the TTS output."""
        # Do not remove .mp3 files as they are the converted TTS files (end product)
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    # Skip cleanup of .mp3 files - they are the TTS conversion results
                    if temp_file.endswith('.mp3'):
                        continue
                    os.remove(temp_file)
            except Exception:
                pass  # Ignore cleanup errors
    
    def cleanup_progress_files(self, file_path):
        """Clean up progress database and boundaries file after successful completion."""
        project_dir = Config.get_project_path()
        
        try:
            # Remove the specific file entry from the database
            entries_remain = True
            with sqlite3.connect(self.db_path) as conn:
                # Delete the specific file entry if file_path provided
                if file_path:
                    conn.execute('DELETE FROM checkpoints WHERE file_path = ?', (file_path,))
                    print(f"🧹 Removed database entry for: {file_path}")
                
                # Check if any entries remain in the database
                cursor = conn.execute('SELECT COUNT(*) FROM checkpoints')
                count = cursor.fetchone()[0]
                entries_remain = count > 0
            
            # Remove progress database if no entries remain or if no file_path specified (global cleanup)
            if not entries_remain or not file_path:
                if os.path.exists(self.db_path):
                    try:
                        os.remove(self.db_path)
                        print(f"🧹 Cleaned up progress database: {self.db_path}")
                    except Exception as e:
                        print(f"⚠️ Could not remove progress database {self.db_path}: {e}")
                        
                        # Additional attempt - try with different permissions
                        try:
                            os.chmod(self.db_path, stat.S_IWRITE | stat.S_IREAD)
                            os.remove(self.db_path)
                            print(f"🧹 Cleaned up progress database (second attempt): {self.db_path}")
                        except Exception as e2:
                            print(f"⚠️ Second attempt failed: {e2}")
            
            # Also look for any other .db files in case the path changed
            db_files = glob.glob(os.path.join(project_dir, "*.db"))
            for db_file in db_files:
                if os.path.abspath(db_file) != os.path.abspath(self.db_path) and "tts" in db_file.lower():
                    try:
                        os.remove(db_file)
                        print(f"🧹 Cleaned up additional database file: {db_file}")
                    except Exception as e:
                        print(f"⚠️ Could not remove additional database {db_file}: {e}")
            
            # Check for checkpoint files
            checkpoint_files = glob.glob(os.path.join(project_dir, "*checkpoint*.db"))
            for ckpt_file in checkpoint_files:
                if os.path.abspath(ckpt_file) != os.path.abspath(self.db_path):
                    try:
                        os.remove(ckpt_file)
                        print(f"🧹 Cleaned up checkpoint file: {ckpt_file}")
                    except Exception as e:
                        print(f"⚠️ Could not remove checkpoint file {ckpt_file}: {e}")
        except Exception as e:
            print(f"⚠️ Error during database cleanup: {e}")
        
        try:
            # Remove boundaries file if file_path is provided
            if file_path:
                boundary_file = file_path + Config.CHUNK_BOUNDARIES_SUFFIX
                if os.path.exists(boundary_file):
                    os.remove(boundary_file)
                    print(f"🧹 Cleaned up boundaries file: {boundary_file}")
            
            # Also look for any boundaries files that might match
            boundary_files = glob.glob(os.path.join(project_dir, "*" + Config.CHUNK_BOUNDARIES_SUFFIX))
            for b_file in boundary_files:
                if not file_path or os.path.abspath(b_file) != os.path.abspath(file_path + Config.CHUNK_BOUNDARIES_SUFFIX):
                    try:
                        os.remove(b_file)
                        print(f"🧹 Cleaned up additional boundaries file: {b_file}")
                    except Exception as e:
                        print(f"⚠️ Could not remove boundaries file {b_file}: {e}")
        except Exception as e:
            print(f"⚠️ Could not remove boundaries files: {e}")
    
    def update_cumulative_time(self, file_path, additional_time):
        """Update the cumulative processing time for a file."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE checkpoints 
                SET cumulative_processing_time = cumulative_processing_time + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
            ''', (additional_time, file_path))
    
    def get_cumulative_time(self, file_path):
        """Get the cumulative processing time for a file."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT cumulative_processing_time FROM checkpoints WHERE file_path = ?',
                (file_path,)
            )
            result = cursor.fetchone()
            return result[0] if result else 0.0
        
    def delete_all_progress(self, file_path):
        """Delete all progress data and temp files for a specific file."""
        project_dir = Config.get_project_path()
        
        try:
            print("🗑️ Deleting all progress data...")
            
            # Remove from database
            entries_remain = True
            with sqlite3.connect(self.db_path) as conn:
                # Delete the specific file entry
                conn.execute('DELETE FROM checkpoints WHERE file_path = ?', (file_path,))
                print(f"🗑️ Removed progress database entry for: {file_path}")
                
                # Check if any entries remain in the database
                cursor = conn.execute('SELECT COUNT(*) FROM checkpoints')
                count = cursor.fetchone()[0]
                entries_remain = count > 0
            
            # If no entries remain, delete the entire database file
            if not entries_remain and os.path.exists(self.db_path):
                try:
                    os.remove(self.db_path)
                    print(f"🗑️ Removed empty checkpoints database: {self.db_path}")
                except Exception as e:
                    print(f"⚠️ Could not remove checkpoints database file: {e}")
            
            # Remove boundaries file
            boundary_file = file_path + Config.CHUNK_BOUNDARIES_SUFFIX
            if os.path.exists(boundary_file):
                os.remove(boundary_file)
                print(f"🗑️ Removed boundaries file: {boundary_file}")
            
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
                                print(f"🗑️ Removed: {temp_file}")
                            except Exception as e:
                                print(f"⚠️ Could not remove {temp_file}: {e}")
            
            print("✅ All progress data deleted successfully!")
            
        except Exception as e:
            print(f"❌ Error deleting progress: {e}")
