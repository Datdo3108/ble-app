import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, freqz, lfilter

# Design a Butterworth low-pass filter
def butter_lowpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

# Generate the impulse response
def impulse_response(b, a, num_samples):
    # Create an impulse signal
    impulse = np.zeros(num_samples)
    impulse[0] = 1  # Impulse at the first sample
    # Apply the filter to the impulse
    response = lfilter(b, a, impulse)
    return response

# Frequency response
def plot_frequency_response(b, a, fs):
    w, h = freqz(b, a, fs=fs)
    plt.figure()
    plt.subplot(2, 1, 1)
    plt.plot(0.5 * fs * w / np.pi, np.abs(h), 'b')
    plt.title('Frequency Response')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Gain')
    plt.grid()

# Time response (impulse response)
def plot_impulse_response(response):
    plt.subplot(2, 1, 2)
    plt.plot(response, 'r')
    plt.title('Impulse Response')
    plt.xlabel('Samples')
    plt.ylabel('Amplitude')
    plt.grid()

# Parameters
fs = 3000  # Sample rate, Hz
cutoff = 0.3  # Desired cutoff frequency, Hz
order = 5  # Filter order

# Get the filter coefficients
b, a = butter_lowpass(cutoff, fs, order)

# Get the impulse response
response = impulse_response(b, a, 3000)

# Plotting
plt.figure(figsize=(10, 6))
plot_frequency_response(b, a, fs)
plot_impulse_response(response)
plt.tight_layout()
plt.show()
