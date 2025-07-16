#!/usr/bin/env python3
import os
import struct
import select
import glob
import time
import fcntl
from threading import Thread, Event
from collections import deque

# Import evdev for robust device identification
try:
    from evdev import InputDevice, categorize, ecodes, list_devices
except ImportError:
    print("Error: python3-evdev is not installed.")
    print("Please install it using: sudo apt-get install python3-evdev")
    exit(1)

# --- Constants from <linux/input.h> ---
EV_KEY = ecodes.EV_KEY
KEY_BACKSPACE = ecodes.KEY_BACKSPACE

# --- MIDI note mappings for keyboard rows (semitones, starting from specified notes) ---
# Using ecodes for direct key references now
MIDI_MAP = {
    # Row 1: 1 to = (G3 = 55, ascending semitones)
    ecodes.KEY_1: 55, ecodes.KEY_2: 56, ecodes.KEY_3: 57, ecodes.KEY_4: 58, ecodes.KEY_5: 59, ecodes.KEY_6: 60,
    ecodes.KEY_7: 61, ecodes.KEY_8: 62, ecodes.KEY_9: 63, ecodes.KEY_0: 64, ecodes.KEY_MINUS: 65, ecodes.KEY_EQUAL: 66,
    # Row Q: Q to ] (D3 = 50, ascending semitones)
    ecodes.KEY_Q: 50, ecodes.KEY_W: 51, ecodes.KEY_E: 52, ecodes.KEY_R: 53, ecodes.KEY_T: 54, ecodes.KEY_Y: 55,
    ecodes.KEY_U: 56, ecodes.KEY_I: 57, ecodes.KEY_O: 58, ecodes.KEY_P: 59, ecodes.KEY_LEFTBRACE: 60, ecodes.KEY_RIGHTBRACE: 61,
    # Row A: A to ' (A2 = 45, ascending semitones)
    ecodes.KEY_A: 45, ecodes.KEY_S: 46, ecodes.KEY_D: 47, ecodes.KEY_F: 48, ecodes.KEY_G: 49, ecodes.KEY_H: 50,
    ecodes.KEY_J: 51, ecodes.KEY_K: 52, ecodes.KEY_L: 53, ecodes.KEY_SEMICOLON: 54, ecodes.KEY_APOSTROPHE: 55,
    # Row Z: Z to / (E2 = 40, ascending semitones)
    ecodes.KEY_Z: 40, ecodes.KEY_X: 41, ecodes.KEY_C: 42, ecodes.KEY_V: 43, ecodes.KEY_B: 44, ecodes.KEY_N: 45,
    ecodes.KEY_M: 46, ecodes.KEY_COMMA: 47, ecodes.KEY_DOT: 48, ecodes.KEY_SLASH: 49, ecodes.KEY_BACKSLASH: 50
}

# --- InputDeviceMonitor Class ---
class InputDeviceMonitor(Thread):
    """
    A transparent class to automatically detect, open, and read events
    from a keyboard input device, handling disconnections.
    It runs in its own thread and provides a thread-safe way to get events.
    """
    def __init__(self, event_queue: deque):
        super().__init__()
        self.daemon = True  # Allow main program to exit even if this thread is running
        self._stop_event = Event()
        self._device = None
        self._event_queue = event_queue  # Queue to put raw evdev events into
        self.device_path = None
        self.device_name = None
        print("InputDeviceMonitor initialized.")

    def _find_keyboard_device(self):
        """
        Automatically finds a suitable keyboard device using evdev.
        Returns an InputDevice object or None.
        """
        print("InputDeviceMonitor: Searching for keyboard devices automatically...")
        devices = [InputDevice(path) for path in list_devices()]
        for device in devices:
            try:
                # Check if the device emits EV_KEY events and has some common keyboard keys
                # This is a more robust way to identify keyboards.
                if (ecodes.EV_KEY in device.capabilities() and
                    (ecodes.KEY_Q in device.capabilities().get(ecodes.EV_KEY, []) or
                     ecodes.KEY_A in device.capabilities().get(ecodes.EV_KEY, []) or
                     ecodes.KEY_SPACE in device.capabilities().get(ecodes.EV_KEY, []))):
                    print(f"InputDeviceMonitor: Found potential keyboard: {device.name} ({device.path})")
                    return device
                device.close() # Close devices that are not keyboards
            except Exception as e:
                print(f"InputDeviceMonitor: Error checking device {device.path}: {e}")
                if device.is_open():
                    device.close()
        print("InputDeviceMonitor: No suitable keyboard device found.")
        return None

    def _open_device(self, device_obj):
        """Opens the specified evdev InputDevice."""
        try:
            device_obj.grab() # Grab the device to prevent other processes from reading events
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
        """Closes the currently open input device."""
        if self._device:
            print(f"InputDeviceMonitor: Closing device {self.device_name} ({self.device_path})")
            try:
                self._device.ungrab() # Release the device
            except OSError as e:
                print(f"InputDeviceMonitor: Warning: Could not ungrab device {self.device_name}: {e}")
            self._device.close()
            self._device = None
            self.device_path = None
            self.device_name = None
        # Clear the queue on disconnect to avoid processing stale events
        self._event_queue.clear()

    def run(self):
        """Main loop for the monitor thread."""
        while not self._stop_event.is_set():
            if not self._device or not self._device.is_open():
                self._close_device() # Ensure clean state
                print("InputDeviceMonitor: Device disconnected or not yet found. Scanning...")
                found_device = self._find_keyboard_device()
                if found_device:
                    if not self._open_device(found_device):
                        print("InputDeviceMonitor: Failed to open found device. Retrying scan.")
                        time.sleep(1) # Small delay before next scan attempt
                        continue # Continue to the next iteration to re-scan
                else:
                    time.sleep(3) # Wait before rescanning if no device found
                    continue # Continue to the next iteration to re-scan

            # If device is open, try to read events
            try:
                # Read events with a timeout to allow periodic checks and graceful shutdown
                for event in self._device.read_loop():
                    if self._stop_event.is_set():
                        break # Exit if stop event is set
                    
                    if event.type == EV_KEY:
                        self._event_queue.append(event)
                        
            except OSError as e:
                # Device disconnected or error reading
                print(f"InputDeviceMonitor: Error reading from device {self.device_name} ({self.device_path}): {e}")
                self._close_device()
            except Exception as e:
                print(f"InputDeviceMonitor: Unexpected error in read_loop: {e}")
                self._close_device()

            if self._stop_event.is_set():
                break # Final check to ensure loop exits

        self._close_device()
        print("InputDeviceMonitor: Thread stopped.")

    def stop(self):
        """Signals the monitoring thread to stop."""
        self._stop_event.set()
        if self._device:
            # Attempt to interrupt the read_loop if it's blocking
            try:
                self._device.ungrab() # Releasing grab can sometimes unblock
            except OSError:
                pass # Ignore if already closed or ungrabbed


# --- KeyboardMIDISynthesizer Class ---
class KeyboardMIDISynthesizer:
    """
    Manages FluidSynth and translates keyboard input events into MIDI notes.
    """
    def __init__(self, soundfont_path, audio_driver="alsa"):
        self.soundfont_path = soundfont_path
        self.audio_driver = audio_driver
        self.fs = None
        self.active_notes = {}  # Tracks active notes by evdev event code
        self._initialize_fluidsynth()

    def _initialize_fluidsynth(self):
        """Initializes FluidSynth."""
        print("KeyboardMIDISynthesizer: Initializing FluidSynth...")
        try:
            import fluidsynth
            self.fs = fluidsynth.Synth()
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

            self.fs.program_select(0, sfid, 0, 0)  # Select bank 0, preset 0 (e.g., Acoustic Grand Piano)
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
        """
        Processes a single evdev event and controls FluidSynth.
        """
        if self.fs is None:
            # Try to re-initialize if it was previously none (e.g., soundfont not found initially)
            self._initialize_fluidsynth()
            if self.fs is None:
                return # Still couldn't initialize, can't play notes

        if event.type == EV_KEY:
            key_code = event.code
            key_value = event.value # 0=release, 1=press, 2=autorepeat

            if key_code == KEY_BACKSPACE and key_value == 1:  # Backspace pressed
                self.fs.cc(0, 123)  # MIDI Control Change: All Notes Off
                self.active_notes.clear()
                print("KeyboardMIDISynthesizer: All MIDI notes off.")
            elif key_code in MIDI_MAP:
                midi_note = MIDI_MAP[key_code]
                if key_value == 1 or key_value == 2:  # Key press or autorepeat
                    if key_code not in self.active_notes:
                        self.fs.noteon(0, midi_note, 100)  # Play note, velocity 100
                        self.active_notes[key_code] = midi_note
                        # print(f"Note ON: {midi_note} (Key: {key_code})") # For debugging
                elif key_value == 0:  # Key release
                    if key_code in self.active_notes:
                        self.fs.noteoff(0, self.active_notes[key_code])  # Stop note
                        del self.active_notes[key_code]
                        # print(f"Note OFF: {midi_note} (Key: {key_code})") # For debugging

    def cleanup(self):
        """Cleans up FluidSynth resources."""
        if self.fs:
            print("KeyboardMIDISynthesizer: Cleaning up FluidSynth...")
            self.fs.delete()
            self.fs = None

# --- Main Application Logic ---
def main():
    # Centralized event queue for communication between monitor and synthesizer threads
    event_queue = deque() 

    # Configuration for soundfont and audio driver
    # Adjust these paths as necessary for your setup when deployed as a service
    soundfont_path = "/usr/local/share/soundfonts/FluidR3_GM.sf2"
    audio_driver = "alsa" # Common for Armbian

    print("Main: Starting InputDeviceMonitor thread...")
    monitor = InputDeviceMonitor(event_queue)
    monitor.start() # Start the device monitoring in a separate thread

    print("Main: Initializing KeyboardMIDISynthesizer...")
    synthesizer = KeyboardMIDISynthesizer(soundfont_path, audio_driver)

    try:
        while True:
            try:
                # Non-blocking read from the event queue
                event = event_queue.popleft() 
                synthesizer.process_event(event)
            except IndexError:
                # Queue is empty, wait a bit before checking again
                time.sleep(0.01) # Small delay to prevent busy-waiting
            
            # Periodically check if the monitor thread is still alive
            # If it's not, something went wrong, and we should stop or restart
            if not monitor.is_alive():
                print("Main: InputDeviceMonitor thread died unexpectedly. Exiting.")
                break # Exit main loop if monitor thread dies

    except KeyboardInterrupt:
        print("\nMain: Ctrl+C detected. Shutting down...")
    except Exception as e:
        print(f"Main: An unexpected error occurred in the main loop: {e}")
    finally:
        print("Main: Stopping InputDeviceMonitor...")
        monitor.stop()
        monitor.join(timeout=5) # Wait for the monitor thread to finish, with a timeout
        if monitor.is_alive():
            print("Main: Warning: InputDeviceMonitor thread did not stop gracefully.")
        
        print("Main: Cleaning up KeyboardMIDISynthesizer...")
        synthesizer.cleanup()
        print("Main: Application finished.")

if __name__ == "__main__":
    main()
