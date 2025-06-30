#!/usr/bin/env python3
"""
Text processing functionality for the TTS converter.
"""
import os
import json
import glob
import hashlib
from .config import Config

class TextProcessor:
    """Handles text extraction and chunking."""
    
    @staticmethod
    def extract_from_file(file_path):
        """Extract text from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"Error reading file: {e}")
    
    @staticmethod 
    def split_into_chunks(text, max_chars=Config.DEFAULT_CHUNK_SIZE, file_path=None):
        """Split text into processable chunks."""
        if not text.strip():
            return []
        
        # Try to load existing chunk boundaries for consistency
        if file_path:
            existing_chunks = TextProcessor._load_chunk_boundaries(file_path, text)
            if existing_chunks:
                return existing_chunks
        
        # Create new chunks
        chunks = []
        current_pos = 0
        boundaries = []
        
        while current_pos < len(text):
            chunk_start = current_pos
            chunk_end = min(current_pos + max_chars, len(text))
            
            # Adjust to sentence/word boundaries
            if chunk_end < len(text):
                # Try sentence boundary first
                sentence_end = text.rfind('. ', chunk_start, chunk_end)
                if sentence_end != -1 and sentence_end > chunk_start + max_chars // 2:
                    chunk_end = sentence_end + 2
                else:
                    # Try word boundary
                    while chunk_end > chunk_start and not text[chunk_end - 1].isspace():
                        chunk_end -= 1
                    if chunk_end == chunk_start:
                        chunk_end = min(current_pos + max_chars, len(text))
            
            chunk = text[chunk_start:chunk_end].strip()
            if chunk:
                chunks.append(chunk)
                boundaries.append([chunk_start, chunk_end])
            
            current_pos = chunk_end
        
        # Save chunk boundaries for future consistency
        if file_path and boundaries:
            TextProcessor._save_chunk_boundaries(file_path, text, boundaries)
        
        return chunks
    
    @staticmethod
    def _get_boundary_file_path(file_path):
        """Get standardized path for the boundary file.
        This will store the boundary file in the project directory with a unique name."""
        # Get the project directory
        project_dir = Config.get_project_path()
        
        # Create a unique filename based on the original file name and path hash
        file_name = os.path.basename(file_path)
        path_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()[:8]  # Use first 8 chars of hash
        boundary_file_name = f"{file_name}_{path_hash}{Config.CHUNK_BOUNDARIES_SUFFIX}"
        
        # Return the full path to the boundary file in the project directory
        return os.path.join(project_dir, boundary_file_name)

    @staticmethod
    def _load_chunk_boundaries(file_path, text):
        """Load existing chunk boundaries."""
        boundary_file = TextProcessor._get_boundary_file_path(file_path)
        try:
            with open(boundary_file, 'r') as f:
                data = json.load(f)
            
            # Verify text hasn't changed
            text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
            if data.get('text_hash') == text_hash:
                chunks = []
                for start, end in data['boundaries']:
                    chunk = text[start:end].strip()
                    if chunk:
                        chunks.append(chunk)
                return chunks
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        return None
    
    @staticmethod
    def _save_chunk_boundaries(file_path, text, boundaries):
        """Save chunk boundaries for consistency."""
        boundary_file = TextProcessor._get_boundary_file_path(file_path)
        try:
            data = {
                'text_hash': hashlib.md5(text.encode('utf-8')).hexdigest(),
                'boundaries': boundaries
            }
            with open(boundary_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ Could not save chunk boundaries: {e}")
    
    @staticmethod
    def cleanup_chunk_boundaries(file_path):
        """Clean up chunk boundary files."""
        if file_path:
            # Clean up specific file's boundaries
            boundary_file = TextProcessor._get_boundary_file_path(file_path)
            try:
                if os.path.exists(boundary_file):
                    os.remove(boundary_file)
                    return True
            except Exception as e:
                print(f"⚠️ Could not remove boundary file: {e}")
                return False
        else:
            # Clean up all boundary files in the project directory
            project_dir = Config.get_project_path()
            boundary_files = glob.glob(os.path.join(project_dir, f"*{Config.CHUNK_BOUNDARIES_SUFFIX}"))
            cleaned = False
            for boundary_file in boundary_files:
                try:
                    os.remove(boundary_file)
                    cleaned = True
                except Exception as e:
                    print(f"⚠️ Could not remove boundary file {boundary_file}: {e}")
            return cleaned
