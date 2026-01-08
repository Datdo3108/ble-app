import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# Load the CSV file
original_path = r'17-10\FSEMI2_air_armpit3_half copper+thermalpad_17-10.csv'
file_path = os.path.splitext(original_path)[0] + '_polynomial_fit_results.csv'
df = pd.read_csv(file_path)

# Calculate the derivative of each signal with respect to time
df['dNTC (downsampled)/dt'] = np.gradient(df['NTC (downsampled)'], df['Time (s)'])
# df['dNTC (polyfit)/dt'] = np.gradient(df['NTC (polyfit)'], df['Time (s)'])
# df['dMAX30205 (downsampled)/dt'] = np.gradient(df['MAX30205 (downsampled)'], df['Time (s)'])
# df['dMAX30205 (polyfit)/dt'] = np.gradient(df['MAX30205 (polyfit)'], df['Time (s)'])

print(len(df['NTC (downsampled)']))
print(len(df['dNTC (downsampled)/dt']))

# Define a threshold to consider points as stable (where derivative is close to zero)
threshold = 0.01

# Find points where the rate of change (derivatives) is small (stable points)
stable_points = df[(df['dNTC (downsampled)/dt'].abs() > threshold) 
                  #  (df['dNTC (polyfit)/dt'].abs() > threshold) &
                #    (df['dMAX30205 (downsampled)/dt'].abs() > threshold) & 
                #    (df['dMAX30205 (polyfit)/dt'].abs() > threshold)
                   ]

print(np.max(df['dNTC (downsampled)/dt']))

# Plot the data
plt.figure(figsize=(10, 6))

# Plot the NTC downsampled and polynomial fit data
plt.plot(df['Time (s)'], df['NTC (downsampled)'], label='NTC (downsampled)', color='blue')
plt.plot(df['Time (s)'], df['dNTC (downsampled)/dt'], label='NTC (d/dt)', linestyle='--', color='blue')
# plt.plot(df['Time (s)'], np.power(np.e, df['dNTC (downsampled)/dt']) - 1, label='NTC (d/dt)', linestyle='--', color='r')


# Plot the MAX30205 downsampled and polynomial fit data
# plt.plot(df['Time (s)'], df['MAX30205 (downsampled)'], label='MAX30205 (downsampled)', color='red')
# plt.plot(df['Time (s)'], df['dMAX30205 (downsampled)/dt'], label='MAX30205 (polyfit)', linestyle='--', color='red')

# Highlight stable points
plt.scatter(stable_points['Time (s)'], stable_points['NTC (downsampled)'], color='green', marker='o', label='Stable NTC Points')
# plt.scatter(stable_points['Time (s)'], stable_points['MAX30205 (downsampled)'], color='black', marker='o', label='Stable MAX30205 Points')

# Add labels and title
plt.xlabel('Time (s)')
plt.ylabel('Values')
plt.title('Data with Stable Points Highlighted')
plt.legend()
plt.grid(True)

# Show the plot
plt.show()

# Save the stable points to CSV
derivate_file_path = file_path.replace('_polynomial_fit_results.csv', '_derivative.csv')
df[['Time (s)', 'NTC (downsampled)', 'dNTC (downsampled)/dt']].to_csv(derivate_file_path, index=False)

