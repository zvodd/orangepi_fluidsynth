import os
import struct
import math
from array import array

def generate_tone(frequency=440, duration=1, sample_rate=44100):
    """Generate a sine wave tone."""
    # Calculate parameters
    length = int(sample_rate * duration)
    factor = float(2 * math.pi * frequency / sample_rate)
    
    # Generate samples
    samples = []
    for i in range(length):
        samples.append(math.sin(factor * i))
    
    return samples

def play_samples(samples, sample_rate=44100):
    """Play samples through ALSA."""
    # Open PCM device
    pcm_device = os.open("/dev/dsp", os.O_WRONLY)
    
    # Set parameters
    params = f"{sample_rate} {1} {16} {4}"
    os.write(pcm_device, params.encode())
    
    # Convert samples to 16-bit integers and play
    audio_data = array('h', [int(sample * 32767) for sample in samples])
    os.write(pcm_device, audio_data.tobytes())
    
    # Close device
    os.close(pcm_device)

def main(frequency=440, duration=1):
    """Play a test tone."""
    try:
        samples = generate_tone(frequency, duration)
        play_samples(samples)
    except Exception as e:
        print(f"Error playing tone: {str(e)}")

# Example usage
if __name__ == "__main__":
    main()  # Plays default 440Hz tone for 1 second
    # main(880, 0.5)  # Example: Play 880Hz tone for half a second