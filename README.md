# Google Text-to-Speech Converter

A simple TTS converter with some interactive features

Main Branch (parralel processing)
Old Main Branch (single processing)

## Usage
Simply run the tts_converter_main file with Python3
The instructions will guide your through the process.

For best use, it is advised to put the .txt files you wish to convert into the same folder as the TTS converter.

## Requirements

- Python 3.6+
- Internet connection
- gTTS library
- pydub library

## Break Down

- **Chunking Process**: When you choose a .txt file, it is broken down into chunks, which are then processed through the TTS.
- **Saves Progress**: If the conversion process is interupted, there are many back up systems that can pick up from where you left off. 
- **Custom Commands**: During processing you can issue a series of commands such as pause or resume.
- **Actual Information**: There are also cool features such as time elapsed or the size of the files.
- **File Management**: The code creates organized folders and file structures for output and cleans up after the conversion process is complete.

## Processing Commands

| Command | Function |
|---------|----------|
| `p` or `pause` | Pause after current chunk |
| `r` or `resume` | Resume from pause |
| `s` or `stop` | Stop and save progress |
| `f` or `force` | Force stop immediately |
| `sd` or `delete` | Stop and delete all progress |
| `h` or `help` | Show help |
