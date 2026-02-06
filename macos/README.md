# s2t for macOS (experimental)

This is a macOS-focused variant of `s2t`. It uses ffmpeg for recording, whisper.cpp for transcription, and AppleScript for pasting.

**Status**: Experimental. This has not been tested beyond the basic implementation here. Expect some setup and permission prompts.

## Requirements

- Homebrew
- `ffmpeg`
- `whisper-cpp` (or a locally built `whisper.cpp`)
- Optional: `terminal-notifier` for notifications
- Optional: `skhd` for global hotkeys

## Install (Homebrew)

```bash
brew install ffmpeg whisper-cpp
brew install terminal-notifier   # optional
brew install skhd                # optional (global hotkeys)
```

## Download a model

whisper.cpp doesn’t ship models. Download one using the upstream script:

```bash
git clone https://github.com/ggerganov/whisper.cpp ~/src/whisper.cpp
~/src/whisper.cpp/models/download-ggml-model.sh base.en
```

Then set:

```bash
export S2T_CPP_MODEL=~/src/whisper.cpp/models/ggml-base.en.bin
```

## Pick your audio input

List devices:

```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

Set the audio input index (example uses audio device index 0):

```bash
export S2T_AVFOUNDATION_INPUT=":0"
```

## Put the script on PATH

```bash
ln -sf /path/to/s2t/macos/s2t ~/bin/s2t
```

## Permissions

Pasting uses AppleScript (`System Events`). macOS will prompt for Accessibility permissions. Allow it for the app launching `s2t` (Terminal, iTerm, etc.).

## Usage

Toggle record:

```bash
s2t
```

Run once to start recording, run again to stop + transcribe + paste.

## Hotkey (skhd)

`~/.skhdrc` example:

```text
cmd - shift - d : /path/to/s2t/macos/s2t
```

Reload:

```bash
skhd --reload
```

## Configuration

- `S2T_CPP_MODEL` (required) full path to model file.
- `S2T_LANG` optional language code.
- `S2T_AVFOUNDATION_INPUT` (default `:0`) audio device index for ffmpeg.
- `S2T_MAX_SECONDS` (default `300`) max recording length; set to `0` to disable.
- `S2T_CLIPBOARD` (default `clipboard`). Set to `preserve` to restore your clipboard after pasting.
- `S2T_CLIPBOARD_RESTORE_DELAY` (default `0.15`).
- `S2T_NOTIFY_SUMMARY`, `S2T_NOTIFY_BODY` customize notifications.

## Notes

- If you don’t want AppleScript paste, you can comment it out and just use the clipboard manually.
- On macOS, `cmd+v` is used for paste in both GUI apps and terminals.
