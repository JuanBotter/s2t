# s2t for macOS

Speech-to-text dictation utility for macOS. Run once to start recording, run again to stop, transcribe with Whisper, and paste into the focused app.

## Requirements

- Python 3.9 or later
- PortAudio (for sounddevice)

## Installation

Install PortAudio:

```bash
brew install portaudio
```

Install s2t in editable mode:

```bash
cd macos
pip install -e .
```

This will download the required dependencies:
- sounddevice (audio recording)
- scipy (WAV file handling)
- faster-whisper (transcription)
- pyperclip (clipboard access)
- numpy (audio data handling)

**Note:** On first run, faster-whisper will automatically download the selected model (default: "base"). This may take a few minutes depending on your connection.

## Permissions

Pasting uses AppleScript (`System Events`). macOS will prompt for Accessibility permissions. Allow it for the app launching `s2t` (Terminal, iTerm, etc.).

## Usage

Toggle recording:

```bash
s2t
```

Run once to start recording, run again to stop + transcribe + paste.

Or run the script directly:

```bash
python3 s2t.py
```

## Hotkey Setup

### Using skhd

Install skhd:

```bash
brew install skhd
```

Add to `~/.skhdrc`:

```text
cmd - shift - d : /path/to/s2t/macos/s2t.py
```

Reload:

```bash
skhd --reload
```

## Configuration

All configuration is via environment variables:

### Model Settings

- `S2T_MODEL` (default: `base`) — Whisper model name. Options: `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`. Larger models are more accurate but slower.
- `S2T_LANG` (optional) — Language code (e.g., `en`, `es`, `fr`). If not set, language is auto-detected.

### Recording Settings

- `S2T_MAX_SECONDS` (default: `300`) — Maximum recording length in seconds. Set to `0` for unlimited.
- `S2T_AUDIO_DEVICE` (optional) — Audio input device index (integer) or name (string). If not set, uses system default input.

To list available audio devices:

```python
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

### Clipboard Settings

- `S2T_CLIPBOARD` (default: `clipboard`) — Set to `preserve` to restore your clipboard after pasting.
- `S2T_CLIPBOARD_RESTORE_DELAY` (default: `0.15`) — Delay in seconds before restoring clipboard (only used when `S2T_CLIPBOARD=preserve`).

### Notification Settings

- `S2T_NOTIFY_SUMMARY` (default: `s2t`) — Notification title.
- `S2T_NOTIFY_BODY` (default: `Recording... (run again to stop)`) — Notification message.

### Advanced Settings

- `S2T_TMP_DIR` (optional) — Override temporary directory. Defaults to `$TMPDIR/s2t` or `/tmp/s2t`.

## Example Configuration

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
export S2T_MODEL="small"           # More accurate than base
export S2T_LANG="en"               # English
export S2T_MAX_SECONDS="600"       # 10 minute max
export S2T_CLIPBOARD="preserve"    # Restore clipboard after paste
export S2T_AUDIO_DEVICE="0"        # Use first audio device
```

## Troubleshooting

### Model Downloads

On first run, faster-whisper downloads the selected model to `~/.cache/huggingface/hub/`. If you want to pre-download:

```python
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
```

### Audio Device Issues

List available devices to find the correct index or name:

```python
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

Then set `S2T_AUDIO_DEVICE` to the index number or exact device name.

### Permission Errors

If pasting doesn't work:
1. Go to System Preferences → Security & Privacy → Privacy → Accessibility
2. Ensure your terminal app (Terminal, iTerm, etc.) is in the list and checked
3. You may need to remove and re-add it

### Log Files

Check daemon logs at `$TMPDIR/s2t/daemon.log` (typically `/tmp/s2t/daemon.log`) for debugging recording issues.

## Notes

- Recording uses 16kHz mono audio (optimal for Whisper)
- Audio is saved to `$TMPDIR/s2t/rec-YYYYMMDD-HHMMSS.wav`
- State is stored in `~/Library/Caches/s2t/state.json`
- Blank audio (silence or just noise) is automatically filtered and not pasted
- The daemon process automatically stops after `S2T_MAX_SECONDS` (default 5 minutes)

## Comparison with Bash Version

This Python version replaces the bash script in this directory. Key differences:

- Uses sounddevice instead of ffmpeg for recording (more portable)
- Uses faster-whisper instead of whisper.cpp (easier setup, auto-downloads models)
- Integrated daemon with proper signal handling (no separate timer process)
- Better error handling and logging
- Eliminates need for terminal-notifier (uses built-in osascript, but supports it if installed for dismissible notifications)

### Breaking Changes from Bash Version

The following environment variables from the bash version are **not supported**:

- `S2T_CPP_MODEL` — The Python version uses faster-whisper models instead of whisper.cpp. Use `S2T_MODEL` with values like `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`.
- `S2T_AVFOUNDATION_INPUT` — The Python version uses sounddevice instead of AVFoundation. Use `S2T_AUDIO_DEVICE` to specify input device by index or name.

If you need the bash version features, the original bash script is still available in this directory as `s2t.sh.backup` (if preserved) or in git history.
