import numpy as np
import sounddevice as sd
import time
import spidev

# Define the parameters for audio processing
CHANNELS = 1  # Mono audio
RATE = 44100  # Sampling rate (samples per second)
CHUNK_SIZE = 2048  # Number of frames per buffer, increased from 1024
NOISE_THRESHOLD = 1000  # Adjust as needed based on your environment

# Setup SPI for MCP3008 ADC
spi = spidev.SpiDev()
spi.open(0, 0)  # (bus, device)

# Function to read analog input from MCP3008
def read_adc(channel):
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

# Function to apply voice modulation based on preset and noise threshold
def apply_voice_modulation(data, preset, noise_threshold):
    # Calculate RMS (Root Mean Square) amplitude of the input data
    rms = np.sqrt(np.mean(np.square(data)))
    
    if rms < noise_threshold:
        return data.astype(np.int16)  # Pass through unmodified if below noise threshold
    
    if preset == "Robotic":
        # Apply robotic voice effect
        modified_data = data * 0.5  # Example: reduce amplitude for robotic effect
    elif preset == "2 Octaves Lower":
        # Apply 2 octaves lower effect
        modified_data = data // 4  # Example: divide amplitude by 4 for 2 octaves lower
    elif preset == "Glitched 1 Octave Lower":
        # Apply glitched 1 octave lower effect
        glitch = np.roll(data, CHUNK_SIZE // 2)
        modified_data = glitch // 2  # Example: apply glitch effect and divide amplitude by 2
    else:
        # Default: No modification (Normal preset)
        modified_data = data

    return modified_data.astype(np.int16)

# Callback function for sounddevice to process audio in real-time
def audio_callback(indata, outdata, frames, time, status):
    if status:
        print(status)
    input_array = indata[:, 0]
    print(f"Input array: {input_array[:10]}")  # Debugging: Print first 10 samples of input

    # Read analog volume knob position from MCP3008 ADC
    volume_position = read_adc(channel=0)  # Example: read from channel 0 of MCP3008
    print(f"Volume position: {volume_position}")  # Debugging: Print volume position

    # Scale volume based on ADC input (adjust scaling as needed)
    volume_scale = volume_position / 1023.0  # MCP3008 is 10-bit (0-1023)
    print(f"Volume scale: {volume_scale}")  # Debugging: Print volume scale
    
    # Apply voice modulation with the current preset
    output_array = apply_voice_modulation(input_array, preset=current_preset, noise_threshold=NOISE_THRESHOLD)
    print(f"Output array (pre-volume): {output_array[:10]}")  # Debugging: Print first 10 samples of output before volume scaling
    
    # Adjust output volume
    output_array = (output_array * volume_scale).astype(np.int16)
    print(f"Output array (post-volume): {output_array[:10]}")  # Debugging: Print first 10 samples of output after volume scaling
    
    outdata[:] = output_array.reshape(-1, 1)

# Function to set the current preset
def set_preset(preset):
    global current_preset
    current_preset = preset
    print(f"Voice changer preset set to {preset}")

# Main loop to continuously process audio
print("Voice changer running. Press Ctrl+C to quit.")
try:
    # Set the default voice mode on boot
    current_preset = "Robotic"  # Set the default preset here

    # Verify device indexes
    input_device_index = 4  # Change to your actual input device index
    output_device_index = 0  # Use headphone jack for output (hw:0,0)

    with sd.Stream(callback=audio_callback, channels=CHANNELS, samplerate=RATE, blocksize=CHUNK_SIZE,
                   device=(input_device_index, output_device_index)):
        while True:
            time.sleep(1)
except KeyboardInterrupt:
    print("Voice changer stopped.")
finally:
    # Close SPI connection
    spi.close()

