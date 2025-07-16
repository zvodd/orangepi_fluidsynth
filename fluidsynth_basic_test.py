#!/bin/env python3
import fluidsynth
import time

def initialize_fluidsynth(soundfont_path, program_number):
    """
    Initializes FluidSynth with a specified soundfont and instrument program.

    Args:
        soundfont_path (str): The path to the soundfont file (.sf2).
        program_number (int): The MIDI program number (0-127) for the desired instrument.

    Returns:
        fluidsynth.Synth: The initialized FluidSynth synthesizer object, or None if failed.
    """
    try:
        fs = fluidsynth.Synth()
        # You might need to change 'alsa' to 'pulseaudio', 'coreaudio', or 'directsound'
        # depending on your operating system.
        fs.start(driver="alsa")
        sfid = fs.sfload(soundfont_path)
        # Select bank 0 and the specified program number
        fs.program_select(0, sfid, 0, program_number)
        print(f"FluidSynth initialized with instrument program: {program_number}")
        return fs
    except Exception as e:
        print(f"Failed to initialize FluidSynth: {e}")
        return None

def play_c_major_arpeggio(fs):
    """
    Plays a C major arpeggio using the initialized FluidSynth synthesizer.
    """
    notes = [60, 64, 67]  # C4 (60), E4 (64), G4 (67)
    velocity = 100        # Note velocity
    note_duration = 0.2   # Duration of each note in seconds

    print("Playing C major arpeggio. Press Ctrl+C to stop.")
    try:
        while True:
            for note in notes:
                fs.noteon(0, note, velocity)
                time.sleep(note_duration)
                fs.noteoff(0, note)
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping arpeggio.")
        fs.cc(0, 123)  # MIDI Control Change: All Notes Off

def main():
    # --- Configuration ---
    soundfont_path = "./FluidR3_GM.sf2" # Adjust this path to your soundfont file

    # Define a dictionary of instrument names and their MIDI program numbers
    # These are standard General MIDI (GM) program numbers.
    instruments = {
        "Piano": 0,
        "Bright Piano": 1,
        "Electric Piano 1": 4,
        "Harpischord": 6,
        "Church Organ": 19,
        "Acoustic Guitar": 25,
        "Electric Guitar (muted)": 28,
        "Violin": 40,
        "Cello": 42,
        "Trumpet": 56,
        "Trombone": 57,
        "Flute": 73,
        "Pan Flute": 75,
        "Synth Pad (New Age)": 88,
        "FX (Rain)": 96,
        "Drums (Standard Kit)": 0 # Drums are typically on MIDI Channel 9 (not Program 0).
                                  # For GM, channel 9 uses preset 0 for Standard Kit.
                                  # However, program_select is per-channel, so we can use 0 here for the program,
                                  # but you'd normally play drums on a different channel (e.g., 9)
                                  # For this example, let's keep it simple and just use program numbers.
                                  # If you want to play drums properly, you'd need to play on channel 9.
                                  # For now, let's use other melodic instruments.
    }

    print("Available Instruments:")
    for name, program in instruments.items():
        print(f"  {name}: Program {program}")

    # --- User Selection ---
    chosen_instrument_name = ""
    while chosen_instrument_name not in instruments:
        chosen_instrument_name = input("Enter the name of the instrument you want to use (e.g., Piano, Violin): ").strip()
        if chosen_instrument_name not in instruments:
            print("Invalid instrument name. Please try again.")

    selected_program_number = instruments[chosen_instrument_name]

    # --- Initialize and Play ---
    fs = initialize_fluidsynth(soundfont_path, selected_program_number)
    if not fs:
        print("Exiting due to FluidSynth initialization failure.")
        return

    try:
        play_c_major_arpeggio(fs)
    finally:
        fs.delete() # Clean up FluidSynth
        print("Synthesizer closed.")

if __name__ == "__main__":
    main()