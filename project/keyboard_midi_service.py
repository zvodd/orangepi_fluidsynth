#!/usr/bin/env python3
import os
import signal
import sys
import time
import traceback
from queue import Queue, Empty
from threading import Thread, Event
import logging
from evdev import InputDevice, categorize, ecodes, list_devices

# --- Constants from <linux/input.h> ---
EV_KEY = ecodes.EV_KEY
KEY_BACKSPACE = ecodes.KEY_BACKSPACE

# --- MIDI note mappings for keyboard rows ---
MIDI_MAP = {
    ecodes.KEY_1: 55, ecodes.KEY_2: 56, ecodes.KEY_3: 57, ecodes.KEY_4: 58, ecodes.KEY_5: 59, ecodes.KEY_6: 60,
    ecodes.KEY_7: 61, ecodes.KEY_8: 62, ecodes.KEY_9: 63, ecodes.KEY_0: 64, ecodes.KEY_MINUS: 65, ecodes.KEY_EQUAL: 66,
    ecodes.KEY_Q: 50, ecodes.KEY_W: 51, ecodes.KEY_E: 52, ecodes.KEY_R: 53, ecodes.KEY_T: 54, ecodes.KEY_Y: 55,
    ecodes.KEY_U: 56, ecodes.KEY_I: 57, ecodes.KEY_O: 58, ecodes.KEY_P: 59, ecodes.KEY_LEFTBRACE: 60, ecodes.KEY_RIGHTBRACE: 61,
    ecodes.KEY_A: 45, ecodes.KEY_S: 46, ecodes.KEY_D: 47, ecodes.KEY_F: 48, ecodes.KEY_G: 49, ecodes.KEY_H: 50,
    ecodes.KEY_J: 51, ecodes.KEY_K: 52, ecodes.KEY_L: 53, ecodes.KEY_SEMICOLON: 54, ecodes.KEY_APOSTROPHE: 55,
    ecodes.KEY_Z: 40, ecodes.KEY_X: 41, ecodes.KEY_C: 42, ecodes.KEY_V: 43, ecodes.KEY_B: 44, ecodes.KEY_N: 45,
    ecodes.KEY_M: 46, ecodes.KEY_COMMA: 47, ecodes.KEY_DOT: 48, ecodes.KEY_SLASH: 49, ecodes.KEY_BACKSLASH: 50
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class InputDeviceMonitor(Thread):
    def __init__(self, event_queue: Queue):
        super().__init__()
        self.daemon = True
        self._stop_event = Event()
        self._device = None
        self._event_queue = event_queue
        self.device_path = None
        self.device_name = None
        logging.info("InputDeviceMonitor initialized.")

    def _find_keyboard_device(self):
        logging.info("Searching for keyboard devices automatically...")
        for path in list_devices():
            device = None
            try:
                device = InputDevice(path)
                logging.debug(f"Checking device: {device.name} ({device.path})")
                capabilities = device.capabilities()
                if (ecodes.EV_KEY in capabilities and
                    any(key in capabilities.get(ecodes.EV_KEY, []) for key in [ecodes.KEY_Q, ecodes.KEY_A, ecodes.KEY_SPACE])):
                    logging.info(f"Found potential keyboard: {device.name} ({device.path})")
                    return device  # Return without closing; we'll grab it later
            except Exception as e:
                logging.error(f"Error checking device {path}: {e}")
            finally:
                if device and device.fd != -1 and device.path != path:  # Close only if not returning it
                    device.close()
        logging.warning("No suitable keyboard device found.")
        return None

    def _open_device(self, device_obj):
        try:
            device_obj.grab()
            self._device = device_obj
            self.device_path = device_obj.path
            self.device_name = device_obj.name
            logging.info(f"Successfully opened and grabbed keyboard device: {self.device_name} ({self.device_path})")
            return True
        except PermissionError:
            logging.error(f"Permission denied to open {device_obj.path}. Ensure user is in 'input' group.")
            return False
        except OSError as e:
            logging.error(f"Error opening device {device_obj.path}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error opening device {device_obj.path}: {e}")
            return False

    def _close_device(self):
        if self._device and self._device.fd != -1:
            logging.info(f"Closing device {self.device_name} ({self.device_path})")
            try:
                self._device.ungrab()
            except OSError as e:
                logging.warning(f"Could not ungrab device {self.device_name}: {e}")
            self._device.close()
        self._device = None
        self.device_path = None
        self.device_name = None
        self._event_queue.queue.clear()  # Clear queue safely

    def run(self):
        while not self._stop_event.is_set():
            if not self._device or self._device.fd == -1:
                self._close_device()
                logging.info("Device disconnected or not yet found. Scanning...")
                found_device = self._find_keyboard_device()
                if found_device:
                    if not self._open_device(found_device):
                        logging.warning("Failed to open found device. Retrying in 1s.")
                        time.sleep(1)
                        continue
                else:
                    time.sleep(3)
                    continue
            try:
                for event in self._device.read_loop():
                    if self._stop_event.is_set():
                        break
                    if event.type == EV_KEY:
                        self._event_queue.put(event)
            except OSError as e:
                logging.error(f"Error reading from device {self.device_name} ({self.device_path}): {e}")
                self._close_device()
            except Exception as e:
                logging.error(f"Unexpected error in read_loop: {e}")
                self._close_device()
        self._close_device()
        logging.info("InputDeviceMonitor: Thread stopped.")

    def stop(self):
        self._stop_event.set()
        if self._device and self._device.fd != -1:
            try:
                self._device.ungrab()
                self._device.close()  # Interrupt any blocking read
            except OSError:
                pass

class KeyboardMIDISynthesizer:
    MODIFIER_KEYS = {ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT}
    ARROW_KEYS = {
        ecodes.KEY_UP: 'up',
        ecodes.KEY_DOWN: 'down',
        ecodes.KEY_LEFT: 'left',
        ecodes.KEY_RIGHT: 'right'
    }

    def __init__(self, soundfont_path, audio_driver="alsa"):
        self.soundfont_path = soundfont_path
        self.audio_driver = audio_driver
        self.fs = None
        self.active_notes = {}
        self.current_bank = 0
        self.current_program = 52  # Choir Aahs
        self.max_banks = 128  # Assume GM standard; adjust for your SoundFont
        self.octave_offset = 0
        self.pressed_modifiers = set()
        self.sfid = None
        self._initialize_fluidsynth()

    def _initialize_fluidsynth(self):
        logging.info("Initializing FluidSynth...")
        try:
            import fluidsynth
            self.fs = fluidsynth.Synth(gain=1.0)
            self.fs.start(driver=self.audio_driver)
            if not os.path.exists(self.soundfont_path):
                raise FileNotFoundError(f"Soundfont not found at {self.soundfont_path}")
            self.sfid = self.fs.sfload(self.soundfont_path)
            if self.sfid == -1:
                raise RuntimeError(f"Failed to load soundfont {self.soundfont_path}")
            self._select_program()
            logging.info("FluidSynth initialized successfully.")
        except ImportError:
            logging.error("fluidsynth library not found. Please install it.")
            self.fs = None
        except Exception as e:
            logging.error(f"Failed to initialize FluidSynth: {e}")
            if self.fs:
                self.fs.delete()
            self.fs = None

    def _select_program(self):
        if self.fs:
            self.fs.program_select(0, self.sfid, self.current_bank, self.current_program)
            logging.info(f"Selected program {self.current_program} in bank {self.current_bank}")

    def process_event(self, event):
        if self.fs is None:
            return  # Don't retry here; init happens once
        if event.type == EV_KEY:
            key_code = event.code
            key_value = event.value
            if key_code in self.MODIFIER_KEYS:
                if key_value == 1:
                    self.pressed_modifiers.add(key_code)
                elif key_value == 0:
                    self.pressed_modifiers.discard(key_code)
            elif key_code in self.ARROW_KEYS and key_value == 1:
                direction = self.ARROW_KEYS[key_code]
                if self.pressed_modifiers:  # Shift + Arrow: Octave shift
                    if direction == 'up' and self.octave_offset < 5:
                        self.octave_offset += 1
                        logging.info(f"Octave offset increased to {self.octave_offset}")
                    elif direction == 'down' and self.octave_offset > -5:
                        self.octave_offset -= 1
                        logging.info(f"Octave offset decreased to {self.octave_offset}")
                else:  # Arrow alone: Program/Bank change
                    if direction == 'up':
                        self.current_program = (self.current_program + 1) % 128
                    elif direction == 'down':
                        self.current_program = (self.current_program - 1) % 128
                    elif direction == 'left':
                        self.current_bank = (self.current_bank - 1) % self.max_banks
                    elif direction == 'right':
                        self.current_bank = (self.current_bank + 1) % self.max_banks
                    self._select_program()
            elif key_code == KEY_BACKSPACE and key_value == 1:
                self.fs.cc(0, 123, 0)  # All notes off
                self.active_notes.clear()
                logging.info("All MIDI notes off.")
            elif key_code in MIDI_MAP:
                base_note = MIDI_MAP[key_code]
                midi_note = max(0, min(127, base_note + 12 * self.octave_offset))
                if key_value == 1 or key_value == 2:  # Press or repeat
                    if key_code not in self.active_notes:
                        self.fs.noteon(0, midi_note, 100)
                        self.active_notes[key_code] = midi_note
                elif key_value == 0:  # Release
                    if key_code in self.active_notes:
                        self.fs.noteoff(0, self.active_notes[key_code])
                        del self.active_notes[key_code]

    def cleanup(self):
        if self.fs:
            logging.info("Cleaning up FluidSynth...")
            self.fs.delete()
            self.fs = None

def signal_handler(sig, frame):
    logging.info("SIGTERM received. Shutting down...")
    sys.exit(0)

def main():
    signal.signal(signal.SIGTERM, signal_handler)  # For systemd stop
    event_queue = Queue()
    soundfont_path = os.environ.get('SOUNDFONT_PATH', '/usr/local/share/soundfonts/FluidR3_GM.sf2')
    audio_driver = "alsa"
    logging.info("Starting InputDeviceMonitor thread...")
    monitor = InputDeviceMonitor(event_queue)
    monitor.start()
    logging.info("Initializing KeyboardMIDISynthesizer...")
    synthesizer = KeyboardMIDISynthesizer(soundfont_path, audio_driver)
    if synthesizer.fs is None:
        logging.error("Failed to initialize synthesizer. Exiting.")
        sys.exit(1)
    try:
        while True:
            try:
                event = event_queue.get(timeout=0.1)  # Block with timeout to check thread health
                synthesizer.process_event(event)
            except Empty:
                if not monitor.is_alive():
                    logging.error("InputDeviceMonitor thread died unexpectedly. Exiting.")
                    break
    except KeyboardInterrupt:
        logging.info("Ctrl+C detected. Shutting down...")
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        logging.error(f"An unexpected error occurred in the main loop: {e}")
    finally:
        logging.info("Stopping InputDeviceMonitor...")
        monitor.stop()
        monitor.join(timeout=5)
        if monitor.is_alive():
            logging.warning("InputDeviceMonitor thread did not stop gracefully.")
        logging.info("Cleaning up KeyboardMIDISynthesizer...")
        synthesizer.cleanup()
        logging.info("Application finished.")

if __name__ == "__main__":
    main()