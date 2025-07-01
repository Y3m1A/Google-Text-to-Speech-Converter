#!/usr/bin/env python3
"""
Configuration settings for the TTS converter.
"""
import os

class Config:
    """Configuration settings for the TTS converter."""
    
    # TTS Settings
    DEFAULT_LANGUAGE = 'en'
    # Chunk size matching TTS 1.py for consistency (5000 characters)
    # This creates fewer, larger chunks compared to smaller sizes
    DEFAULT_CHUNK_SIZE = 5000  # Matches TTS 1.py chunk size
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    
    # Progress Settings
    PROGRESS_UPDATE_INTERVAL = 1.0
    TERMINAL_WIDTH = 120
    
    # Multiprocessing Settings
    MAX_PARALLEL_CHUNKS = 4  # Maximum number of chunks to process simultaneously
    _multiprocessing_enabled = True  # Enable parallel processing by default
    
    @classmethod
    def get_multiprocessing_enabled(cls):
        """Get current multiprocessing setting."""
        return cls._multiprocessing_enabled
    
    @classmethod
    def set_multiprocessing_enabled(cls, enabled):
        """Set multiprocessing enabled/disabled."""
        cls._multiprocessing_enabled = enabled
    
    @property
    def MULTIPROCESSING_ENABLED(self):
        """Property to access multiprocessing setting."""
        return self._multiprocessing_enabled
    
    # Base directory - will be dynamically set
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # File Settings
    DEFAULT_OUTPUT_DIR = "tts_audio_output"  # Default directory name for output files
    DEFAULT_PREFIX = "audio"  # Default prefix for chunk files
    TEMP_FILE_PREFIX = 'temp_chunk_'  # Legacy prefix - will be replaced with custom naming
    CHUNK_BOUNDARIES_SUFFIX = '_chunk_boundaries.json'
    
    # Display Elements
    PROGRESS_EMOJI = '🎵'
    COMPLETION_EMOJI = '✅'
    ERROR_EMOJI = '❌'
    PAUSE_EMOJI = '⏸️'
    RESUME_EMOJI = '▶️'
    STOP_EMOJI = '🛑'
    
    @staticmethod
    def get_project_path():
        """Get the path to the directory containing the tts_converter package."""
        return Config.BASE_DIR
    
    @staticmethod
    def get_absolute_path(relative_path):
        """Convert a relative path to an absolute path based on the project directory."""
        if os.path.isabs(relative_path):
            return relative_path
        return os.path.join(Config.BASE_DIR, relative_path)
    
    @staticmethod
    def get_default_output_dir():
        """Get the absolute path to the default output directory."""
        return os.path.join(Config.BASE_DIR, Config.DEFAULT_OUTPUT_DIR)
    
    @staticmethod
    def get_temp_filename(chunk_index, output_dir=None, prefix=None):
        """Get the temporary filename for a chunk, optionally in an output directory with custom prefix."""
        # Use custom prefix if provided, otherwise use default
        file_prefix = prefix or Config.DEFAULT_PREFIX
        
        # Format: prefix + " " + number + .mp3  (e.g., "book audio 1.mp3")
        filename = f"{file_prefix} {chunk_index + 1}.mp3"
        
        if output_dir:
            # Make sure output_dir is absolute
            abs_output_dir = Config.get_absolute_path(output_dir) if not os.path.isabs(output_dir) else output_dir
            return os.path.join(abs_output_dir, filename)
        return filename
        
    @staticmethod
    def ensure_output_dir(output_dir=None):
        """Ensure the output directory exists, create if it doesn't."""
        if not output_dir:
            dir_path = Config.get_default_output_dir()
        else:
            # If output_dir is not absolute, make it relative to the project directory
            dir_path = Config.get_absolute_path(output_dir) if not os.path.isabs(output_dir) else output_dir
            
        os.makedirs(dir_path, exist_ok=True)
        return dir_path
