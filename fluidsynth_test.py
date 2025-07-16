#!/bin/env python3
import os
import struct
import select
import glob
import fluidsynth
import time

# Constants from <linux/input.h> for keyboard events
EV_KEY = 0x01  # Key press/release event
KEY_1 = 2
KEY_2 = 3
KEY_3 = 4
KEY_4 = 5
KEY_5 = 6
KEY_6 = 7
KEY_7 = 8
KEY_8 = 9
KEY_9 = 10
KEY_0 = 11
KEY_MINUS = 12
KEY_EQUAL = 13
KEY_BACKSPACE = 14
KEY_Q = 16
KEY_W = 17
KEY_E = 18
KEY_R = 19
KEY_T = 20
KEY_Y = 21
KEY_U = 22
KEY_I = 23
KEY_O = 24
KEY_P = 25
KEY_LEFTBRACE = 26
KEY_RIGHTBRACE = 27
KEY_A = 30
KEY_S = 31
KEY_D = 32
KEY_F = 33
KEY_G = 34
KEY_H = 35
KEY_J = 36
KEY_K = 37
KEY_L = 38
KEY_SEMICOLON = 39
KEY_APOSTROPHE = 40
KEY_Z = 44
KEY_X = 45
KEY_C = 46
KEY_V = 47
KEY_B = 48
KEY_N = 49
KEY_M = 50
KEY_COMMA = 51
KEY_DOT = 52
KEY_SLASH = 53
KEY_BACKSLASH = 43

# MIDI note mappings for keyboard rows (semitones, starting from specified notes)
MIDI_MAP = {
    # Row 1: 1 to = (G3 = 55, ascending semitones)
    KEY_1: 55, KEY_2: 56, KEY_3: 57, KEY_4: 58, KEY_5: 59, KEY_6: 60,
    KEY_7: 61, KEY_8: 62, KEY_9: 63, KEY_0: 64, KEY_MINUS: 65, KEY_EQUAL: 66,
    # Row Q: Q to ] (D3 = 50, ascending semitones)
    KEY_Q: 50, KEY_W: 51, KEY_E: 52, KEY_R: 53, KEY_T: 54, KEY_Y: 55,
    KEY_U: 56, KEY_I: 57, KEY_O: 58, KEY_P: 59, KEY_LEFTBRACE: 60, KEY_RIGHTBRACE: 61,
    # Row A: A to ' (A2 = 45, ascending semitones)
    KEY_A: 45, KEY_S: 46, KEY_D: 47, KEY_F: 48, KEY_G: 49, KEY_H: 50,
    KEY_J: 51, KEY_K: 52, KEY_L: 53, KEY_SEMICOLON: 54, KEY_APOSTROPHE: 55,
    # Row Z: Z to / (E2 = 40, ascending semitones)
    KEY_Z: 40, KEY_X: 41, KEY_C: 42, KEY_V: 43, KEY_B: 44, KEY_N: 45,
    KEY_M: 46, KEY_COMMA: 47, KEY_DOT: 48, KEY_SLASH: 49, KEY_BACKSLASH: 50
}

# Size and format of input_event struct
INPUT_EVENT_SIZE = struct.calcsize('LLHHI')
INPUT_EVENT_FORMAT = 'LLHHI'

def find_keyboard_device_path():
    print("Searching for input devices in /dev/input/...")
    device_paths = sorted(glob.glob('/dev/input/event*'))
    if not device_paths:
        print("No event devices found in /dev/input/.")
        return None

    potential_keyboards = []
    for i, path in enumerate(device_paths):
        try:
            with open(path, 'rb') as f:
                pass
            potential_keyboards.append(path)
            print(f"{i}: {path}")
        except OSError:
            pass

    if not potential_keyboards:
        print("No accessible input devices found. Ensure keyboard is connected and you have permissions.")
        return None

    while True:
        try:
            choice = input("Enter the number of the device to use as keyboard (or Q to quit): ").strip().lower()
            if choice == 'q':
                return None
            selected_index = int(choice)
            if 0 <= selected_index < len(potential_keyboards):
                return potential_keyboards[selected_index]
            else:
                print("Invalid choice. Please enter a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number or 'Q'.")

def initialize_fluidsynth():
    # Initialize FluidSynth with a hardcoded soundfont
    soundfont_path = "./FluidR3_GM.sf2"  # Adjust this path to your soundfont
    fs = fluidsynth.Synth()
    fs.start(driver="alsa")  # Use ALSA audio driver (adjust for your system, e.g., "pulseaudio" or "coreaudio")
    sfid = fs.sfload(soundfont_path)
    fs.program_select(0, sfid, 0, 0)  # Select bank 0, preset 0 (e.g., Acoustic Grand Piano)
    return fs

def read_keyboard_events_builtin():
    device_path = find_keyboard_device_path()
    if not device_path:
        print("Exiting.")
        return

    # Initialize FluidSynth
    try:
        fs = initialize_fluidsynth()
    except Exception as e:
        print(f"Failed to initialize FluidSynth: {e}")
        return

    try:
        fd = os.open(device_path, os.O_RDONLY | os.O_NONBLOCK)
        f = os.fdopen(fd, 'rb', buffering=0)
        print(f"Reading keyboard events from {device_path}. Press Backspace to reset MIDI, Ctrl+C to exit.")

        poller = select.poll()
        poller.register(fd, select.POLLIN)
        active_notes = {}  # Track active notes to handle note-off

        while True:
            events = poller.poll(100)
            if not events:
                continue

            try:
                event_data = f.read(INPUT_EVENT_SIZE)
                if not event_data or len(event_data) < INPUT_EVENT_SIZE:
                    print("Device read truncated or disconnected. Exiting.")
                    break

                tv_sec, tv_usec, event_type, event_code, event_value = struct.unpack(INPUT_EVENT_FORMAT, event_data)

                if event_type == EV_KEY:
                    if event_code == KEY_BACKSPACE and event_value == 1:  # Backspace pressed
                        fs.cc(0, 123)  # MIDI Control Change: All Notes Off
                        active_notes.clear()
                    elif event_code in MIDI_MAP:
                        midi_note = MIDI_MAP[event_code]
                        if event_value == 1 or event_value == 2:  # Key press or autorepeat
                            if event_code not in active_notes:
                                fs.noteon(0, midi_note, 100)  # Play note, velocity 100
                                active_notes[event_code] = midi_note
                        elif event_value == 0:  # Key release
                            if event_code in active_notes:
                                fs.noteoff(0, active_notes[event_code])  # Stop note
                                del active_notes[event_code]

            except struct.error as e:
                print(f"Error unpacking event data: {e}")
            except BlockingIOError:
                pass
            except Exception as e:
                print(f"Unexpected error: {e}")
                break

    except FileNotFoundError:
        print(f"Error: Device {device_path} not found.")
    except PermissionError:
        print(f"Error: Permission denied to open {device_path}. Run with 'sudo' or add user to 'input' group.")
    except KeyboardInterrupt:
        print("\nExiting event loop.")
    finally:
        if 'f' in locals() and not f.closed:
            f.close()
            os.close(fd)
        if 'fs' in locals():
            fs.delete()  # Clean up FluidSynth
        print("Device and synthesizer closed.")

if __name__ == "__main__":
    read_keyboard_events_builtin()