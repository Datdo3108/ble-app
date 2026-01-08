import numpy as np
import pandas as pd
from scipy import signal
import matplotlib.pyplot as plt

# Read the CSV file
df = pd.read_csv(r'11-10 exp fit\fsemi1_armpit4_11-10 test.csv')

# Extract time and temperature data
time = df['Time (s)'].values
temp_ntc = df['NTC (polyfit)'].values
temp_max = df['MAX30205 (polyfit)'].values

# Define STFT parameters
fs = 1 / (time[1] - time[0])  # Sampling frequency
window = 'hann'
nperseg = 256  # Length of each segment
noverlap = nperseg // 2  # 50% overlap

# Perform STFT on both temperature datasets
f_ntc, t_ntc, Zxx_ntc = signal.stft(temp_ntc, fs=fs, window=window, nperseg=nperseg, noverlap=noverlap)
# f_max, t_max, Zxx_max = signal.stft(temp_max, fs=fs, window=window, nperseg=nperseg, noverlap=noverlap)

# Plot the results
plt.figure(figsize=(12, 10))

# NTC Temperature STFT
# plt.subplot(2, 1, 1)
plt.pcolormesh(t_ntc, f_ntc, np.abs(Zxx_ntc), shading='gouraud')
plt.title('STFT Magnitude - NTC Temperature')
plt.ylabel('Frequency [Hz]')
plt.colorbar(label='Magnitude')

# # MAX30205 Temperature STFT
# plt.subplot(2, 1, 2)
# plt.pcolormesh(t_max, f_max, np.abs(Zxx_max), shading='gouraud')
# plt.title('STFT Magnitude - MAX30205 Temperature')
# plt.ylabel('Frequency [Hz]')
# plt.xlabel('Time [sec]')
# plt.colorbar(label='Magnitude')

plt.tight_layout()
plt.show()

# Print some statistics
print(f"NTC Temperature - Mean: {np.mean(temp_ntc):.2f}°C, Std: {np.std(temp_ntc):.2f}°C")
# print(f"MAX30205 Temperature - Mean: {np.mean(temp_max):.2f}°C, Std: {np.std(temp_max):.2f}°C")
print(f"Dominant frequency NTC: {f_ntc[np.argmax(np.mean(np.abs(Zxx_ntc), axis=1))]:.4f} Hz")
# print(f"Dominant frequency MAX30205: {f_max[np.argmax(np.mean(np.abs(Zxx_max), axis=1))]:.4f} Hz")