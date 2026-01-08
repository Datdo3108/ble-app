import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Read the CSV file
df = pd.read_csv(r'11-10\11-10 water fast.csv')

# Extract MAX30205 and NTC data
max30205_data = df['MAX30205'].values - np.mean(df['MAX30205'].values)
ntc_data = df['NTC'].values - np.mean(df['NTC'].values)

# Perform FFT
max30205_fft = np.fft.fft(max30205_data)
ntc_fft = np.fft.fft(ntc_data)

# Calculate frequencies
n = len(df)
freq = np.fft.fftfreq(n, d=df['Time'].diff().mean())

# Plot the results
plt.figure(figsize=(12, 8))

# MAX30205 FFT
plt.subplot(2, 1, 1)
plt.plot(freq[:n//2], np.abs(max30205_fft)[:n//2])
plt.title('FFT of MAX30205 Data')
plt.xlabel('Frequency (Hz)')
plt.ylabel('Magnitude')

# NTC FFT
plt.subplot(2, 1, 2)
plt.plot(freq[:n//2], np.abs(ntc_fft)[:n//2])
plt.title('FFT of NTC Data')
plt.xlabel('Frequency (Hz)')
plt.ylabel('Magnitude')

plt.tight_layout()
plt.show()