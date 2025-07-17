import os
import struct
import fcntl # Not strictly used for ioctl in this example, but often needed for device control
import select
import glob

# Constants from <linux/input.h> (common values for keyboards)
# Event types
EV_SYN = 0x00 # Synchronization event
EV_KEY = 0x01 # Key press/release event
EV_REL = 0x02 # Relative (e.g., mouse movement)
EV_ABS = 0x03 # Absolute (e.g., joystick axes, touchscreen)

# Event codes (KEY codes for a standard keyboard)
# A very small subset, you'd extend this significantly for a full keyboard
KEY_RESERVED = 0
KEY_ESC = 1
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
KEY_TAB = 15
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
KEY_LEFTBRACE = 26 # [
KEY_RIGHTBRACE = 27 # ]
KEY_ENTER = 28
KEY_LEFTCTRL = 29
KEY_A = 30
KEY_S = 31
KEY_D = 32
KEY_F = 33
KEY_G = 34
KEY_H = 35
KEY_J = 36
KEY_K = 37
KEY_L = 38
KEY_SEMICOLON = 39 # ;
KEY_APOSTROPHE = 40 # '
KEY_GRAVE = 41 # ` (tilde)
KEY_LEFTSHIFT = 42
KEY_BACKSLASH = 43
KEY_Z = 44
KEY_X = 45
KEY_C = 46
KEY_V = 47
KEY_B = 48
KEY_N = 49
KEY_M = 50
KEY_COMMA = 51 # ,
KEY_DOT = 52 # .
KEY_SLASH = 53 # /
KEY_RIGHTSHIFT = 54
KEY_KPASTERISK = 55 # Keypad *
KEY_LEFTALT = 56
KEY_SPACE = 57
KEY_CAPSLOCK = 58
KEY_F1 = 59
KEY_F2 = 60
KEY_F3 = 61
KEY_F4 = 62
KEY_F5 = 63
KEY_F6 = 64
KEY_F7 = 65
KEY_F8 = 66
KEY_F9 = 67
KEY_F10 = 68
KEY_NUMLOCK = 69
KEY_SCROLLLOCK = 70
KEY_KP7 = 71
KEY_KP8 = 72
KEY_KP9 = 73
KEY_KPMINUS = 74
KEY_KP4 = 75
KEY_KP5 = 76
KEY_KP6 = 77
KEY_KPPLUS = 78
KEY_KP1 = 79
KEY_KP2 = 80
KEY_KP3 = 81
KEY_KP0 = 82
KEY_KPDOT = 83
KEY_F11 = 87
KEY_F12 = 88
KEY_KPENTER = 96
KEY_RIGHTCTRL = 97
KEY_KPSLASH = 98
KEY_SYSRQ = 99 # Print Screen
KEY_RIGHTALT = 100 # AltGr
KEY_HOME = 102
KEY_UP = 103
KEY_PAGEUP = 104
KEY_LEFT = 105
KEY_RIGHT = 106
KEY_END = 107
KEY_DOWN = 108
KEY_PAGEDOWN = 109
KEY_INSERT = 110
KEY_DELETE = 111
KEY_PAUSE = 119
KEY_LEFTMETA = 125 # Windows/Super key
KEY_RIGHTMETA = 126
KEY_COMPOSE = 127 # Menu key

# Mapping event codes to human-readable names
# This is a very partial mapping, extend as needed.
EV_CODE_NAMES = {
    EV_SYN: {0: "SYN_REPORT"},
    EV_KEY: {
        KEY_RESERVED: "KEY_RESERVED", KEY_ESC: "KEY_ESC", KEY_1: "KEY_1",
        KEY_2: "KEY_2", KEY_3: "KEY_3", KEY_4: "KEY_4", KEY_5: "KEY_5",
        KEY_6: "KEY_6", KEY_7: "KEY_7", KEY_8: "KEY_8", KEY_9: "KEY_9",
        KEY_0: "KEY_0", KEY_MINUS: "KEY_MINUS", KEY_EQUAL: "KEY_EQUAL",
        KEY_BACKSPACE: "KEY_BACKSPACE", KEY_TAB: "KEY_TAB", KEY_Q: "KEY_Q",
        KEY_W: "KEY_W", KEY_E: "KEY_E", KEY_R: "KEY_R", KEY_T: "KEY_T",
        KEY_Y: "KEY_Y", KEY_U: "KEY_U", KEY_I: "KEY_I", KEY_O: "KEY_O",
        KEY_P: "KEY_P", KEY_LEFTBRACE: "KEY_LEFTBRACE", KEY_RIGHTBRACE: "KEY_RIGHTBRACE",
        KEY_ENTER: "KEY_ENTER", KEY_LEFTCTRL: "KEY_LEFTCTRL", KEY_A: "KEY_A",
        KEY_S: "KEY_S", KEY_D: "KEY_D", KEY_F: "KEY_F", KEY_G: "KEY_G",
        KEY_H: "KEY_H", KEY_J: "KEY_J", KEY_K: "KEY_K", KEY_L: "KEY_L",
        KEY_SEMICOLON: "KEY_SEMICOLON", KEY_APOSTROPHE: "KEY_APOSTROPHE",
        KEY_GRAVE: "KEY_GRAVE", KEY_LEFTSHIFT: "KEY_LEFTSHIFT",
        KEY_BACKSLASH: "KEY_BACKSLASH", KEY_Z: "KEY_Z", KEY_X: "KEY_X",
        KEY_C: "KEY_C", KEY_V: "KEY_V", KEY_B: "KEY_B", KEY_N: "KEY_N",
        KEY_M: "KEY_M", KEY_COMMA: "KEY_COMMA", KEY_DOT: "KEY_DOT",
        KEY_SLASH: "KEY_SLASH", KEY_RIGHTSHIFT: "KEY_RIGHTSHIFT",
        KEY_KPASTERISK: "KEY_KPASTERISK", KEY_LEFTALT: "KEY_LEFTALT",
        KEY_SPACE: "KEY_SPACE", KEY_CAPSLOCK: "KEY_CAPSLOCK", KEY_F1: "KEY_F1",
        KEY_F2: "KEY_F2", KEY_F3: "KEY_F3", KEY_F4: "KEY_F4", KEY_F5: "KEY_F5",
        KEY_F6: "KEY_F6", KEY_F7: "KEY_F7", KEY_F8: "KEY_F8", KEY_F9: "KEY_F9",
        KEY_F10: "KEY_F10", KEY_NUMLOCK: "KEY_NUMLOCK", KEY_SCROLLLOCK: "KEY_SCROLLLOCK",
        KEY_KP7: "KEY_KP7", KEY_KP8: "KEY_KP8", KEY_KP9: "KEY_KP9",
        KEY_KPMINUS: "KEY_KPMINUS", KEY_KP4: "KEY_KP4", KEY_KP5: "KEY_KP5",
        KEY_KP6: "KEY_KP6", KEY_KPPLUS: "KEY_KPPLUS", KEY_KP1: "KEY_KP1",
        KEY_KP2: "KEY_KP2", KEY_KP3: "KEY_KP3", KEY_KP0: "KEY_KP0",
        KEY_KPDOT: "KEY_KPDOT", KEY_F11: "KEY_F11", KEY_F12: "KEY_F12",
        KEY_KPENTER: "KEY_KPENTER", KEY_RIGHTCTRL: "KEY_RIGHTCTRL",
        KEY_KPSLASH: "KEY_KPSLASH", KEY_SYSRQ: "KEY_SYSRQ", KEY_RIGHTALT: "KEY_RIGHTALT",
        KEY_HOME: "KEY_HOME", KEY_UP: "KEY_UP", KEY_PAGEUP: "KEY_PAGEUP",
        KEY_LEFT: "KEY_LEFT", KEY_RIGHT: "KEY_RIGHT", KEY_END: "KEY_END",
        KEY_DOWN: "KEY_DOWN", KEY_PAGEDOWN: "KEY_PAGEDOWN", KEY_INSERT: "KEY_INSERT",
        KEY_DELETE: "KEY_DELETE", KEY_PAUSE: "KEY_PAUSE",
        KEY_LEFTMETA: "KEY_LEFTMETA", KEY_RIGHTMETA: "KEY_RIGHTMETA",
        KEY_COMPOSE: "KEY_COMPOSE",
        # Add more KEY codes as needed from <linux/input-event-codes.h> or evtest
    }
}

def get_event_name(event_type, event_code):
    type_name = "UNKNOWN_TYPE"
    code_name = "UNKNOWN_CODE"
    if event_type in EV_CODE_NAMES:
        type_name = {
            EV_SYN: "EV_SYN", EV_KEY: "EV_KEY",
            EV_REL: "EV_REL", EV_ABS: "EV_ABS"
        }.get(event_type, f"TYPE_{hex(event_type)}")
        code_name = EV_CODE_NAMES[event_type].get(event_code, f"CODE_{hex(event_code)}")
    return type_name, code_name

# Size of the input_event struct (same as for joystick)
# On a 64-bit Linux system:
# timeval (tv_sec, tv_usec): 2 * 8 bytes (long long)
# type: 2 bytes (unsigned short)
# code: 2 bytes (unsigned short)
# value: 4 bytes (int)
# Total: 16 + 2 + 2 + 4 = 24 bytes
# Format string: "LLHHI" (unsigned long long, unsigned long long, unsigned short, unsigned short, int)
INPUT_EVENT_SIZE = struct.calcsize('LLHHI')
INPUT_EVENT_FORMAT = 'LLHHI'


def find_keyboard_device_path():
    """
    Tries to find a keyboard device path in /dev/input/.
    This is heuristic and might need manual adjustment.
    Keyboards are often not obvious by name alone.
    """
    print("Searching for input devices in /dev/input/...")
    device_paths = sorted(glob.glob('/dev/input/event*'))

    potential_keyboards = []
    if not device_paths:
        print("No event devices found in /dev/input/.")
        return None

    print("\nPotential input devices found (choose your keyboard):")
    for i, path in enumerate(device_paths):
        # A very basic heuristic: attempt to open and check if it's an event device
        # without further introspection (which requires ioctl and thus ctypes or CFFI)
        try:
            with open(path, 'rb') as f:
                # You might try to read a small amount to ensure it's not empty,
                # but direct 'open' is usually enough to check existence and permissions.
                pass
            potential_keyboards.append(path)
            print(f"{i}: {path}")
        except OSError:
            pass # Skip if not accessible

    if not potential_keyboards:
        print("No accessible input devices found. "
              "Please ensure your keyboard is connected and you have read permissions.")
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


def read_keyboard_events_builtin():
    device_path = find_keyboard_device_path()
    if not device_path:
        print("Exiting.")
        return

    try:
        # Open the device file in binary read mode with non-blocking
        fd = os.open(device_path, os.O_RDONLY | os.O_NONBLOCK)
        f = os.fdopen(fd, 'rb', buffering=0) # buffering=0 for raw reads

        print(f"Reading raw keyboard events from {device_path}. Press Ctrl+C to exit.")
        print("WARNING: This will consume events, potentially preventing them from reaching your terminal/desktop environment.")

        # Use select to wait for data without busy-waiting
        poller = select.poll()
        poller.register(fd, select.POLLIN)

        while True:
            # Wait for data with a timeout (e.g., 100ms)
            events = poller.poll(100) # Timeout in milliseconds
            if not events:
                continue # No data, just loop again

            try:
                # Read the exact size of an input_event struct
                event_data = f.read(INPUT_EVENT_SIZE)
                if not event_data or len(event_data) < INPUT_EVENT_SIZE:
                    print("Device read truncated or disconnected. Exiting.")
                    break

                # Unpack the binary data
                tv_sec, tv_usec, event_type, event_code, event_value = struct.unpack(INPUT_EVENT_FORMAT, event_data)

                type_name, code_name = get_event_name(event_type, event_code)

                if event_type == EV_KEY:  # Key press/release events
                    if event_value == 1:  # Key pressed
                        print(f"Key Pressed: {code_name}")
                    elif event_value == 0:  # Key released
                        print(f"Key Released: {code_name}")
                    elif event_value == 2: # Key autorepeat
                        print(f"Key Autorepeat: {code_name}")
                elif event_type == EV_SYN:  # Synchronization event
                    # print("--- Sync ---") # Uncomment if you want to see sync events
                    pass
                else:
                    print(f"Other Event: Type={type_name}, Code={code_name}, Value={event_value}")

            except struct.error as e:
                print(f"Error unpacking event data: {e}. Data: {event_data.hex()}")
            except BlockingIOError:
                pass # No data available immediately, continue polling
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                break

    except FileNotFoundError:
        print(f"Error: Device {device_path} not found. "
              "Please ensure your keyboard is connected and the path is correct.")
    except PermissionError:
        print(f"Error: Permission denied to open {device_path}. "
              "You MUST run this script with 'sudo' or ensure your user "
              "is in the 'input' group (e.g., `sudo usermod -a -G input $USER`). "
              "Note: Reading directly from a keyboard device often 'grabs' it, "
              "preventing input from reaching your desktop environment.")
    except OSError as e:
        print(f"OS Error: {e}")
    except KeyboardInterrupt:
        print("\nExiting event loop.")
    finally:
        if 'f' in locals() and not f.closed:
            f.close()
            os.close(fd) # Close the file descriptor directly
            print("Device closed.")

if __name__ == "__main__":
    read_keyboard_events_builtin()