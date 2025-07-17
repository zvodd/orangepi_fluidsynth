#!/usr/bin/env python3
import os
import struct
import select
import glob
import time
import fcntl
from threading import Thread, Event
from collections import deque
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

class InputDeviceMonitor(Thread):
    def __init__(self, event_queue: deque):
        super().__init__()
        self.daemon = True
        self._stop_event = Event()
        self._device = None
        self._event_queue = event_queue
        self.device_path = None
        self.device_name = None
        print("InputDeviceMonitor initialized.")

    def _find_keyboard_device(self):
        print("InputDeviceMonitor: Searching for keyboard devices automatically...")
        devices = [InputDevice(path) for path in list_devices()]
        for device in devices:
            try:
                if (ecodes.EV_KEY in device.capabilities() and
                    (ecodes.KEY_Q in device.capabilities().get(ecodes.EV_KEY, []) or
                     ecodes.KEY_A in device.capabilities().get(ecodes.EV_KEY, []) or
                     ecodes.KEY_SPACE in device.capabilities().get(ecodes.EV_KEY, []))):
                    print(f"InputDeviceMonitor: Found potential keyboard: {device.name} ({device.path})")
                    return device
                device.close()
            except Exception as e:
                print(f"InputDeviceMonitor: Error checking device {device.path}: {e}")
                if device.is_open():
                    device.close()
        print("InputDeviceMonitor: No suitable keyboard device found.")
        return None

    def _open_device(self, device_obj):
        try:
            device_obj.grab()
            self._device = device_obj
            self.device_path = device_obj.path
            self.device_name = device_obj.name
            print(f"InputDeviceMonitor: Successfully opened and grabbed keyboard device: {self.device_name} ({self.device_path})")
            return True
        except PermissionError:
            print(f"InputDeviceMonitor: Permission denied to open {device_obj.path}.")
            print("InputDeviceMonitor: Ensure the user running this script is in the 'input' group.")
            return False
        except OSError as e:
            print(f"InputDeviceMonitor: Error opening device {device_obj.path}: {e}")
            return False
        except Exception as e:
            print(f"InputDeviceMonitor: Unexpected error opening device {device_obj.path}: {e}")
            return False

    def _close_device(self):
        if self._device:
            print(f"InputDeviceMonitor: Closing device {self.device_name} ({self.device_path})")
            try:
                self._device.ungrab()
            except OSError as e:
                print(f"InputDeviceMonitor: Warning: Could not ungrab device {self.device_name}: {e}")
            self._device.close()
            self._device = None
            self.device_path = None
            self.device_name = None
        self._event_queue.clear()

    def run(self):
        while not self._stop_event.is_set():
            if not self._device or not self._device.is_open():
                self._close_device()
                print("InputDeviceMonitor: Device disconnected or not yet found. Scanning...")
                found_device = self._find_keyboard_device()
                if found_device:
                    if not self._open_device(found_device):
                        print("InputDeviceMonitor: Failed to open found device. Retrying scan.")
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
                        self._event_queue.append(event)
            except OSError as e:
                print(f"InputDeviceMonitor: Error reading from device {self.device_name} ({self.device_path}): {e}")
                self._close_device()
            except Exception as e:
                print(f"InputDeviceMonitor: Unexpected error in read_loop: {e}")
                self._close_device()

            if self._stop_event.is_set():
                break

        self._close_device()
        print("InputDeviceMonitor: Thread stopped.")

    def stop(self):
        self._stop_event.set()
        if self._device:
            try:
                self._device.ungrab()
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
        self.current_program = 52
        self.octave_offset = 0
        self.pressed_modifiers = set()
        self.sfid = None
        self._initialize_fluidsynth()

    def _initialize_fluidsynth(self):
        print("KeyboardMIDISynthesizer: Initializing FluidSynth...")
        try:
            import fluidsynth
            self.fs = fluidsynth.Synth(gain=1.0)
            self.fs.start(driver=self.audio_driver)
            if not os.path.exists(self.soundfont_path):
                print(f"Error: Soundfont not found at {self.soundfont_path}")
                self.fs.delete()
                self.fs = None
                return

            sfid = self.fs.sfload(self.soundfont_path)
            if sfid == -1:
                print(f"Error: Failed to load soundfont {self.soundfont_path}")
                self.fs.delete()
                self.fs = None
                return

            self.sfid = sfid
            self.fs.program_select(0, self.sfid, self.current_bank, self.current_program)
            print("KeyboardMIDISynthesizer: FluidSynth initialized successfully.")
        except ImportError:
            print("Error: fluidsynth library not found. Please install it.")
            self.fs = None
        except Exception as e:
            print(f"KeyboardMIDISynthesizer: Failed to initialize FluidSynth: {e}")
            if self.fs:
                self.fs.delete()
            self.fs = None


    def process_event(self, event):
        if self.fs is None:
            self._initialize_fluidsynth()
            if self.fs is None:
                return

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
                if self.pressed_modifiers:
                    if direction == 'up' and self.octave_offset < 5:
                        self.octave_offset += 1
                        print(f"Octave offset increased to {self.octave_offset}")
                    elif direction == 'down' and self.octave_offset > -5:
                        self.octave_offset -= 1
                        print(f"Octave offset decreased to {self.octave_offset}")
                # else:
                #     if direction == 'up':
                #         self.current_program = (self.current_program + 1) % 128
                #     elif direction == 'down':
                #         self.current_program = (self.current_program - 1) % 128
                #     elif direction == 'left':
                #         self.current_bank = (self.current_bank - 1) % self.banks_max
                #     elif direction == 'right':
                #         self.current_bank = (self.current_bank + 1) % self.banks_max
                #     #try:
                #     self.fs.program_select(0, self.sfid, self.current_bank, self.current_program)
                #         #fluid synth 1.1.11 doesn't have this.
                #         #preset_name = self.fs.sfpreset_name(self.sfid, self.current_bank, self.current_program)
                #         #print(f"Selected program {self.current_program} ({preset_name}) in bank {self.current_bank}")
                #     #except AttributeError:

                #     print(f"Selected program {self.current_program} in bank {self.current_bank}")

            elif key_code == KEY_BACKSPACE and key_value == 1:
                self.fs.cc(0, 123, 0)
                self.active_notes.clear()
                print("KeyboardMIDISynthesizer: All MIDI notes off.")
            elif key_code in MIDI_MAP:
                base_note = MIDI_MAP[key_code]
                midi_note = max(0, min(127, base_note + 12 * self.octave_offset))
                if key_value == 1 or key_value == 2:
                    if key_code not in self.active_notes:
                        self.fs.noteon(0, midi_note, 100)
                        self.active_notes[key_code] = midi_note
                elif key_value == 0:
                    if key_code in self.active_notes:
                        self.fs.noteoff(0, self.active_notes[key_code])
                        del self.active_notes[key_code]

    def cleanup(self):
        if self.fs:
            print("KeyboardMIDISynthesizer: Cleaning up FluidSynth...")
            self.fs.delete()
            self.fs = None

def main():
    event_queue = deque()
    soundfont_path = "/usr/local/share/soundfonts/FluidR3_GM.sf2"
    audio_driver = "alsa"

    print("Main: Starting InputDeviceMonitor thread...")
    monitor = InputDeviceMonitor(event_queue)
    monitor.start()

    print("Main: Initializing KeyboardMIDISynthesizer...")
    synthesizer = KeyboardMIDISynthesizer(soundfont_path, audio_driver)

    try:
        while True:
            try:
                event = event_queue.popleft()
                synthesizer.process_event(event)
            except IndexError:
                time.sleep(0.01)
            
            if not monitor.is_alive():
                print("Main: InputDeviceMonitor thread died unexpectedly. Exiting.")
                break

    except KeyboardInterrupt:
        print("\nMain: Ctrl+C detected. Shutting down...")
    except Exception as e:
        import traceback
        import sys
        traceback.print_exc(file=sys.stdout)
        print(f"Main: An unexpected error occurred in the main loop: {e}")
    finally:
        print("Main: Stopping InputDeviceMonitor...")
        monitor.stop()
        monitor.join(timeout=5)
        if monitor.is_alive():
            print("Main: Warning: InputDeviceMonitor thread did not stop gracefully.")
        
        print("Main: Cleaning up KeyboardMIDISynthesizer...")
        synthesizer.cleanup()
        print("Main: Application finished.")

if __name__ == "__main__":
    main()