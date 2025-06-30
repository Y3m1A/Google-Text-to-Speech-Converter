# Google Text-to-Speech Converter

A modular text-to-speech converter with checkpoint/resume functionality.

## Usage
Simply run the tts_converter_main file

## Requirements

- Python 3.6+
- Internet connection
- gTTS library
- pydub library

## Core Features

- **Text Conversion**: Transforms text files into MP3 audio files using Google's TTS API
- **Checkpoint System**: Automatically saves progress after each processed chunk
- **Resume Capability**: Continues conversion from last successful point if interrupted
- **Interactive Controls**: Real-time commands to pause, resume, or stop conversion
- **File Management**: Creates organized folders and file structures for output
- **Progress Tracking**: Shows detailed status of ongoing conversions

## Processing Commands

| Command | Function |
|---------|----------|
| `p` or `pause` | Pause after current chunk |
| `r` or `resume` | Resume from pause |
| `s` or `stop` | Stop and save progress |
| `f` or `force` | Force stop immediately |
| `sd` or `delete` | Stop and delete all progress |
| `h` or `help` | Show help |
| `Ctrl+C` | Force interrupt |
