import os
import struct
import fcntl
import select
import glob

# Constants from <linux/input.h> (common values)
# Event types
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02 # Relative (e.g., mouse movement)
EV_ABS = 0x03 # Absolute (e.g., joystick axes)

# Event codes (examples - there are many more)
# ABS codes (joystick axes)
ABS_X = 0x00
ABS_Y = 0x01
ABS_Z = 0x02
ABS_RX = 0x03 # RZ in some contexts
ABS_RY = 0x04 # RTHROTTLE in some contexts
ABS_RZ = 0x05 # RUDDER in some contexts
ABS_HAT0X = 0x10 # D-pad horizontal
ABS_HAT0Y = 0x11 # D-pad vertical

# KEY codes (buttons)
BTN_JOYSTICK = 0x120
BTN_GAMEPAD = 0x130
BTN_A = 0x130 # Common A button on gamepads
BTN_B = 0x131 # Common B button
BTN_C = 0x132
BTN_X = 0x133
BTN_Y = 0x134
BTN_Z = 0x135
BTN_TL = 0x136 # Top Left trigger/shoulder
BTN_TR = 0x137 # Top Right trigger/shoulder
BTN_TL2 = 0x138 # Top Left 2nd trigger
BTN_TR2 = 0x139 # Top Right 2nd trigger
BTN_SELECT = 0x13A
BTN_START = 0x13B
BTN_MODE = 0x13C # Mode button (e.g., PS button)
BTN_THUMBL = 0x13D # Left stick button
BTN_THUMBR = 0x13E # Right stick button


# Mapping event codes to human-readable names (incomplete, add as needed)
# This is a basic mapping. A real evdev library has a comprehensive one.
EV_CODE_NAMES = {
    EV_SYN: {0: "SYN_REPORT"},
    EV_KEY: {
        BTN_JOYSTICK: "BTN_JOYSTICK", BTN_GAMEPAD: "BTN_GAMEPAD",
        BTN_A: "BTN_A", BTN_B: "BTN_B", BTN_C: "BTN_C",
        BTN_X: "BTN_X", BTN_Y: "BTN_Y", BTN_Z: "BTN_Z",
        BTN_TL: "BTN_TL", BTN_TR: "BTN_TR", BTN_TL2: "BTN_TL2", BTN_TR2: "BTN_TR2",
        BTN_SELECT: "BTN_SELECT", BTN_START: "BTN_START", BTN_MODE: "BTN_MODE",
        BTN_THUMBL: "BTN_THUMBL", BTN_THUMBR: "BTN_THUMBR",
        # Add more KEY codes as you discover them for your joystick
    },
    EV_ABS: {
        ABS_X: "ABS_X", ABS_Y: "ABS_Y", ABS_Z: "ABS_Z",
        ABS_RX: "ABS_RX", ABS_RY: "ABS_RY", ABS_RZ: "ABS_RZ",
        ABS_HAT0X: "ABS_HAT0X", ABS_HAT0Y: "ABS_HAT0Y",
        # Add more ABS codes as you discover them for your joystick
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

# Size of the input_event struct (adjust for your system's architecture if necessary)
# On a 64-bit Linux system:
# timeval (tv_sec, tv_usec): 2 * 8 bytes (long long)
# type: 2 bytes (unsigned short)
# code: 2 bytes (unsigned short)
# value: 4 bytes (int)
# Total: 16 + 2 + 2 + 4 = 24 bytes
# Format string: "LLHHI" (unsigned long long, unsigned long long, unsigned short, unsigned short, int)
INPUT_EVENT_SIZE = struct.calcsize('LLHHI')
INPUT_EVENT_FORMAT = 'LLHHI'


def find_joystick_device_path():
    """
    Tries to find a joystick device path in /dev/input/.
    This is heuristic and might need manual adjustment.
    """
    print("Searching for joystick devices in /dev/input/...")
    device_paths = sorted(glob.glob('/dev/input/event*'))
    
    potential_joysticks = []
    for path in device_paths:
        try:
            # Try to open the device to check for permissions and existence
            with open(path, 'rb') as f:
                # Attempt to get device name using EVIOCGNAME ioctl
                # EVIOCGNAME (IOC_READ, 'E', 0x06, 256) for a 256-byte buffer
                # This requires fcntl and ioctl numbers, which is getting into ctypes territory
                # without an evdev library. Let's skip direct ioctl for pure built-in,
                # as it's non-trivial to define the ioctl calls without ctypes.
                # Instead, we'll just check if it's readable and assume if it's in /dev/input/eventX
                # it might be an input device.
                
                # A more robust check without external libs is hard.
                # Users will likely need to know their device path.
                
                # For this built-in-only example, we'll just list all event devices
                # and let the user pick, or assume common joystick names if possible.
                potential_joysticks.append(path)
        except OSError:
            pass # Cannot open, skip

    if not potential_joysticks:
        print("No event devices found or accessible in /dev/input/event*. "
              "Please ensure your joystick is connected and you have read permissions.")
        return None
    
    print("\nPotential input devices found:")
    for i, path in enumerate(potential_joysticks):
        print(f"{i}: {path}")

    while True:
        try:
            choice = input("Enter the number of the device to use (or Q to quit): ").strip().lower()
            if choice == 'q':
                return None
            
            selected_index = int(choice)
            if 0 <= selected_index < len(potential_joysticks):
                return potential_joysticks[selected_index]
            else:
                print("Invalid choice. Please enter a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number or 'Q'.")


def read_joystick_events_builtin():
    device_path = find_joystick_device_path()
    if not device_path:
        print("Exiting.")
        return

    try:
        # Open the device file in binary read mode
        # O_NONBLOCK is important to prevent blocking indefinitely
        fd = os.open(device_path, os.O_RDONLY | os.O_NONBLOCK)
        f = os.fdopen(fd, 'rb', buffering=0) # buffering=0 for raw reads

        print(f"Reading raw events from {device_path}. Press Ctrl+C to exit.")

        # Use select to wait for data without busy-waiting
        poller = select.poll()
        poller.register(fd, select.POLLIN)

        while True:
            # Wait for data with a timeout (e.g., 100ms)
            # This makes the loop responsive to Ctrl+C
            events = poller.poll(100) # Timeout in milliseconds
            if not events:
                continue # No data, just loop again

            try:
                # Read the exact size of an input_event struct
                event_data = f.read(INPUT_EVENT_SIZE)
                if not event_data or len(event_data) < INPUT_EVENT_SIZE:
                    # Device might have been disconnected or EOF
                    print("Device read truncated or disconnected. Exiting.")
                    break

                # Unpack the binary data
                tv_sec, tv_usec, event_type, event_code, event_value = struct.unpack(INPUT_EVENT_FORMAT, event_data)

                type_name, code_name = get_event_name(event_type, event_code)

                # Print the event
                # print(f"Time: {tv_sec}.{tv_usec:06d}, Type: {hex(event_type)} ({type_name}), "
                #       f"Code: {hex(event_code)} ({code_name}), Value: {event_value}")

                # More user-friendly output for common events
                if event_type == EV_ABS:  # Absolute events (joystick axes)
                    print(f"Axis Event: {code_name} = {event_value}")
                elif event_type == EV_KEY:  # Key events (buttons)
                    if event_value == 1:  # Button pressed
                        print(f"Button Pressed: {code_name}")
                    elif event_value == 0:  # Button released
                        print(f"Button Released: {code_name}")
                    # else: event_value == 2 for autorepeat
                elif event_type == EV_SYN:  # Synchronization event
                    # print("--- Sync ---") # Uncomment if you want to see sync events
                    pass
                else:
                    print(f"Other Event: Type={type_name}, Code={code_name}, Value={event_value}")

            except struct.error as e:
                print(f"Error unpacking event data: {e}. Data: {event_data.hex()}")
                # This can happen if reads are not aligned to event boundaries.
                # For robust code, you might need to handle partial reads and buffer.
                # For this example, we'll just skip to the next read.
            except BlockingIOError:
                # No data available immediately, continue polling
                pass
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                break

    except FileNotFoundError:
        print(f"Error: Device {device_path} not found. "
              "Please ensure your joystick is connected and the path is correct.")
    except PermissionError:
        print(f"Error: Permission denied to open {device_path}. "
              "You might need to run the script with 'sudo' or ensure your user "
              "is in the 'input' group (e.g., `sudo usermod -a -G input $USER`).")
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
    read_joystick_events_builtin()