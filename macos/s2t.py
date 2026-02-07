#!/usr/bin/env python3
"""
macOS dictation toggle: run once to start recording, run again to stop,
transcribe with Whisper, and paste into the focused app.

Make executable: chmod +x s2t.py
"""

import json
import os
import signal
import sys
import time
import logging
import threading
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import subprocess

# Environment configuration
S2T_MODEL = os.getenv("S2T_MODEL", "base")
S2T_LANG = os.getenv("S2T_LANG", "")
S2T_MAX_SECONDS = int(os.getenv("S2T_MAX_SECONDS", "300"))
S2T_CLIPBOARD = os.getenv("S2T_CLIPBOARD", "clipboard")
S2T_CLIPBOARD_RESTORE_DELAY = float(os.getenv("S2T_CLIPBOARD_RESTORE_DELAY", "0.15"))
S2T_NOTIFY_SUMMARY = os.getenv("S2T_NOTIFY_SUMMARY", "s2t")
S2T_NOTIFY_BODY = os.getenv("S2T_NOTIFY_BODY", "Recording... (run again to stop)")
S2T_NOTIFY_STACK_TAG = os.getenv("S2T_NOTIFY_STACK_TAG", "s2t")
S2T_AUDIO_DEVICE = os.getenv("S2T_AUDIO_DEVICE", "")
S2T_TMP_DIR = os.getenv("S2T_TMP_DIR", "")

# State and temp directories
STATE_DIR = Path(os.getenv("XDG_CACHE_HOME") or Path.home() / "Library" / "Caches") / "s2t"
STATE_FILE = STATE_DIR / "state.json"

if S2T_TMP_DIR:
    TMP_DIR = Path(S2T_TMP_DIR)
else:
    tmpdir_env = os.getenv("TMPDIR", "/tmp")
    TMP_DIR = Path(tmpdir_env) / "s2t"

LOG_FILE = TMP_DIR / "daemon.log"

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1

# Global state for signal handling
stop_event = threading.Event()
audio_data = []


def setup_logging(daemon: bool = False):
    """Set up logging to file for daemon or stderr for parent."""
    if daemon:
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='s2t: %(message)s',
            stream=sys.stderr
        )


def notify(title: str, message: str):
    """Send macOS notification using osascript."""
    title_escaped = title.replace('\\', '\\\\').replace('"', '\\"')
    message_escaped = message.replace('\\', '\\\\').replace('"', '\\"')
    script = f'display notification "{message_escaped}" with title "{title_escaped}"'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
    except Exception:
        pass


def notify_start():
    """Send start notification with dismissible support via terminal-notifier."""
    # Try terminal-notifier first (supports dismissal)
    if shutil.which("terminal-notifier"):
        subprocess.run(
            ["terminal-notifier", "-group", S2T_NOTIFY_STACK_TAG,
             "-title", S2T_NOTIFY_SUMMARY, "-message", S2T_NOTIFY_BODY],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
        return
    # Fallback to osascript
    notify(S2T_NOTIFY_SUMMARY, S2T_NOTIFY_BODY)


def notify_end():
    """Dismiss notification via terminal-notifier if available."""
    if shutil.which("terminal-notifier"):
        subprocess.run(
            ["terminal-notifier", "-remove", S2T_NOTIFY_STACK_TAG],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )


def read_state() -> Optional[Dict[str, Any]]:
    """Read state from JSON file."""
    if not STATE_FILE.exists():
        return None
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to read state: {e}")
        return None


def write_state(pid: int, wav_path: str):
    """Write state to JSON file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "pid": pid,
        "wav_path": wav_path
    }
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        logging.error(f"Failed to write state: {e}")
        sys.exit(1)


def clear_state():
    """Remove state file."""
    try:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
    except Exception as e:
        logging.error(f"Failed to clear state: {e}")


def check_dependencies():
    """Check that required Python packages are available."""
    missing = []
    try:
        import sounddevice
    except ImportError:
        missing.append("sounddevice")

    try:
        import scipy.io.wavfile
    except ImportError:
        missing.append("scipy")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        missing.append("faster-whisper")

    try:
        import pyperclip
    except ImportError:
        missing.append("pyperclip")

    if missing:
        logging.error(f"Missing dependencies: {', '.join(missing)}")
        logging.error("Install with: pip install " + " ".join(missing))
        sys.exit(1)


def signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM by setting stop event."""
    stop_event.set()


def record_audio(wav_path: str):
    """Record audio in daemon mode with timer check in callback."""
    import sounddevice as sd
    import numpy as np
    from scipy.io.wavfile import write

    global audio_data

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    audio_data = []
    timer_triggered = False
    start_time = time.monotonic()

    # Determine audio device
    device = None
    if S2T_AUDIO_DEVICE:
        # Try to parse as integer index first
        try:
            device = int(S2T_AUDIO_DEVICE)
        except ValueError:
            # Otherwise use as string name (sounddevice will match)
            device = S2T_AUDIO_DEVICE

    # Log the selected device
    try:
        if device is None:
            device_info = sd.query_devices(kind='input')
            logging.info(f"Using default input device: {device_info['name']}")
        else:
            device_info = sd.query_devices(device)
            logging.info(f"Using input device: {device_info['name']}")
    except Exception as e:
        logging.warning(f"Could not query device info: {e}")

    def callback(indata, frames, time_info, status):
        """Audio callback with timer check."""
        nonlocal timer_triggered
        if status:
            logging.warning(f"Audio status: {status}")

        # Check if we should stop due to max time
        if S2T_MAX_SECONDS > 0 and not timer_triggered:
            if time.monotonic() - start_time >= S2T_MAX_SECONDS:
                timer_triggered = True
                stop_event.set()
                logging.info(f"Max recording time reached ({S2T_MAX_SECONDS}s)")
                return

        # Append audio data
        if not stop_event.is_set():
            audio_data.append(indata.copy())

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            callback=callback,
            device=device
        ):
            logging.info(f"Recording to {wav_path}")
            if S2T_MAX_SECONDS > 0:
                logging.info(f"Max duration: {S2T_MAX_SECONDS} seconds")
            else:
                logging.info("Max duration: unlimited")

            # Wait until stop signal
            while not stop_event.is_set():
                time.sleep(0.1)

        # Write WAV file
        if audio_data:
            logging.info("Writing WAV file...")
            audio_array = np.concatenate(audio_data, axis=0)
            write(wav_path, SAMPLE_RATE, audio_array)
            logging.info(f"Recording saved to {wav_path}")
        else:
            logging.warning("No audio data recorded")

    except Exception as e:
        logging.error(f"Recording error: {e}")
        sys.exit(1)


def daemonize_and_record(wav_path: str):
    """Fork a daemon process to record audio."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Fork
    pid = os.fork()

    if pid > 0:
        # Parent process: write state and exit
        write_state(pid, wav_path)
        notify_start()
        logging.info("recording started (run again to stop)")
        sys.exit(0)

    # Child process: become daemon and record
    try:
        os.setsid()

        # Set up file logging BEFORE redirecting std streams
        setup_logging(daemon=True)

        # Redirect standard file descriptors to /dev/null
        devnull = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull, sys.stdin.fileno())
        os.dup2(devnull, sys.stdout.fileno())
        os.dup2(devnull, sys.stderr.fileno())
        if devnull > 2:
            os.close(devnull)

        record_audio(wav_path)
    except Exception as e:
        logging.error(f"Daemon error: {e}")
        sys.exit(1)


def stop_daemon(pid: int) -> bool:
    """Stop the recording daemon and wait for it to exit."""
    try:
        # Send SIGINT
        os.kill(pid, signal.SIGINT)

        # Wait up to 5 seconds for process to exit
        for _ in range(50):
            try:
                # Check if process still exists
                os.kill(pid, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                # Process has exited
                return True

        logging.warning("Daemon did not exit within 5 seconds")
        return False

    except ProcessLookupError:
        # Process already exited
        return True
    except Exception as e:
        logging.error(f"Failed to stop daemon: {e}")
        return False


def transcribe(wav_path: str) -> str:
    """Transcribe audio file using faster-whisper."""
    from faster_whisper import WhisperModel

    logging.info(f"Loading model: {S2T_MODEL}")

    # Load model
    model = WhisperModel(S2T_MODEL, device="cpu", compute_type="int8")

    # Transcribe
    logging.info("Transcribing...")
    segments, info = model.transcribe(
        wav_path,
        language=S2T_LANG if S2T_LANG else None,
        beam_size=5
    )

    # Collect text
    text_parts = []
    for segment in segments:
        text_parts.append(segment.text)

    text = "".join(text_parts).strip()
    if len(text) > 100:
        logging.info(f"Transcription: {text[:100]}...")
    else:
        logging.info(f"Transcription: {text}")
    return text


def is_blank_audio(text: str) -> bool:
    """Check if transcription is blank/empty audio."""
    # Check 1: Only whitespace and punctuation
    check = text.translate(str.maketrans('', '', ' \t\n\r.,!?;:\'"'))
    if not check:
        return True

    # Check 2: Only contains "blankaudio" (case-insensitive, alpha only)
    canon = ''.join(c.lower() for c in text if c.isalpha())
    if canon == "blankaudio":
        return True

    return False


def paste_text(text: str):
    """Paste text via clipboard and AppleScript."""
    import pyperclip

    saved_clipboard = None

    # Save clipboard if preserving
    if S2T_CLIPBOARD == "preserve":
        try:
            saved_clipboard = pyperclip.paste()
        except Exception:
            pass

    # Copy transcription to clipboard
    pyperclip.copy(text)

    # Paste using AppleScript (no escaping needed - not interpolated into script)
    script = 'tell application "System Events" to keystroke "v" using command down'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
    except Exception as e:
        logging.warning(f"Failed to paste: {e}")

    # Restore clipboard if needed
    if saved_clipboard is not None:
        time.sleep(S2T_CLIPBOARD_RESTORE_DELAY)
        try:
            pyperclip.copy(saved_clipboard)
        except Exception:
            pass


def main():
    """Main toggle function."""
    setup_logging(daemon=False)
    check_dependencies()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Check if recording is active
    state = read_state()

    if state is not None:
        # Stop recording
        pid = state.get("pid")
        wav_path = state.get("wav_path")

        if not pid or not wav_path:
            logging.error("Invalid state file")
            clear_state()
            sys.exit(1)

        logging.info("Stopping recording...")
        stop_daemon(pid)
        clear_state()
        notify_end()

        # Check WAV file
        wav_file = Path(wav_path)
        if not wav_file.exists():
            logging.error("Recording file missing")
            sys.exit(1)

        if wav_file.stat().st_size == 0:
            logging.error("Recording file is empty")
            sys.exit(1)

        # Transcribe
        text = transcribe(wav_path)

        # Filter blank audio
        if is_blank_audio(text):
            logging.info("Blank audio detected, skipping paste")
            sys.exit(0)

        # Paste
        paste_text(text)
        logging.info("Done")
        sys.exit(0)

    else:
        # Start recording
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        wav_path = str(TMP_DIR / f"rec-{timestamp}.wav")
        daemonize_and_record(wav_path)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
