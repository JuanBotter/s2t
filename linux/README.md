# s2t (dictation toggle)

A tiny dictation utility for Linux that records audio, transcribes with Whisper, and pastes into the focused app. Run it once to start recording, run it again to stop + transcribe + paste.

**Status / testing**

Developed and tested on **Arch Linux + X11** (DWM + Dunst) using **whisper.cpp from the AUR**. It has **not** been tested on other distros or Wayland, so some tinkering may be required outside that setup.

## Install

## Arch Linux (tested)

1. Install recording + paste tools (X11):

```bash
sudo pacman -S --needed pipewire alsa-utils ffmpeg xdotool xclip
```

If you want Wayland tools instead (not tested):

```bash
sudo pacman -S --needed wl-clipboard wtype
```

2. Install whisper.cpp and download a model (AUR + upstream model):

```bash
paru -S whisper.cpp

git clone https://github.com/ggerganov/whisper.cpp ~/src/whisper.cpp
~/src/whisper.cpp/models/download-ggml-model.sh base.en
```

3. Set the model path:

```bash
export S2T_CPP_MODEL=~/src/whisper.cpp/models/ggml-base.en.bin
```

Optional Python Whisper backend (not required if you use whisper.cpp):

```bash
pipx install openai-whisper
```

## Debian / Ubuntu (untested)

1. Install recording + paste tools (X11):

```bash
sudo apt update
sudo apt install -y ffmpeg pipewire alsa-utils xdotool xclip
```

Wayland tools may be available in your distro, but are untested:

```bash
sudo apt install -y wl-clipboard
```

2. Install whisper.cpp:

If your distro provides a `whisper.cpp` package, install it. Otherwise build from source:

```bash
sudo apt install -y git build-essential pkg-config

git clone https://github.com/ggerganov/whisper.cpp ~/src/whisper.cpp
cd ~/src/whisper.cpp
make -j
```

3. Download a model and set the path:

```bash
~/src/whisper.cpp/models/download-ggml-model.sh base.en
export S2T_CPP_MODEL=~/src/whisper.cpp/models/ggml-base.en.bin
```

## Put the script on PATH

`linux/bin/s2t` is the entrypoint. Add this repo’s `linux/bin/` to your `PATH` or symlink it somewhere in your `PATH`.

## Usage

1. Run `s2t` to start recording.
2. Run `s2t` again to stop, transcribe, and paste.

Bind `s2t` to a hotkey in your desktop environment to get push-to-talk style dictation (press once to start, press again to stop).

## DWM Keybind (Toggle)

Example `config.h` snippet:

```c
static const char *s2tcmd[] = { "systemctl", "--user", "start", "s2t.service", NULL };

/* key bindings */
{ MODKEY, XK_d, spawn, {.v = s2tcmd } },
```

You can also call `s2t` directly in the keybind:

```c
static const char *s2tcmd[] = { "s2t", NULL };
```

## systemd (user service)

Install the unit and reload systemd:

```bash
mkdir -p ~/.config/systemd/user
ln -sf "$(pwd)"/linux/systemd/user/s2t.service ~/.config/systemd/user/s2t.service
systemctl --user daemon-reload
```

If your user systemd session does not inherit `DISPLAY`/`XAUTHORITY`, import them from your X session (e.g. in `~/.xinitrc`):

```bash
systemctl --user import-environment DISPLAY XAUTHORITY PATH
```

## Configuration

Environment variables:

- `S2T_MODEL` (default: `base`) for Python Whisper.
- `S2T_LANG` (optional language code like `en`, `es`).
- `S2T_CPP_MODEL` (required for whisper.cpp) full path to model file.
- `S2T_RECORD_TOOL` (`pw-record`, `arecord`, or `ffmpeg`) to force a recorder.
- `S2T_TMP_DIR` to override temp storage.
- `S2T_TERMINAL_CLASSES` (comma-separated) to treat specific X11 window classes as terminals for paste (uses Ctrl+Shift+V). Default includes common terminals.
- `S2T_NOTIFY_SUMMARY` and `S2T_NOTIFY_BODY` to customize the persistent recording notification.
- `S2T_NOTIFY_STACK_TAG` (default: `s2t`) to control the Dunst stack tag used for styling.
- `S2T_MAX_SECONDS` (default: `300`) to automatically stop recording after a max duration. Set to `0` to disable.
- `S2T_CLIPBOARD` (default: `clipboard`). Set to `preserve` to restore your clipboard after pasting.
- `S2T_CLIPBOARD_RESTORE_DELAY` (default: `0.15`) seconds to wait before restoring clipboard when using `preserve`.

Examples:

```bash
# Use a larger Whisper model (Python backend)
S2T_MODEL=small s2t

# whisper.cpp
S2T_CPP_MODEL=~/src/whisper.cpp/models/ggml-base.en.bin s2t
```

## Notes

- Auto-paste relies on a clipboard tool + a key injection tool. If those aren’t available, the script will print the transcription to stdout.
- On X11, terminals use Ctrl+Shift+V; the script detects common terminal window classes via `xdotool`. Customize with `S2T_TERMINAL_CLASSES`.
- Recording uses a single persistent notification; with Dunst this is closed via `dunstctl` when you stop recording.
- For Dunst, add a rule to style the notification (colors/format) by matching `appname = "s2t"` or `stack_tag = "s2t"`.
- Notifications include `x-dunst-stack-tag` so rules can match reliably even when launched via systemd.
- Auto-stop on silence is not enabled by default; if you want that behavior, ask and I can wire it up using `sox`.
