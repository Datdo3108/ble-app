import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# Read the CSV data
file_path = r"16-10\FSEMI1_air_armpit2_huge alufoil + thermopaste_16-10.csv"
data = pd.read_csv(file_path)

# Extract time and temperature data
time = data['Time'].values
temperature = data['NTC'].values
time_fit = time - time[0]

# Define the exponential function
def exp_func(x, a, b, c, d):
    return a * np.exp(-b * (x + d)) + c

# Perform the curve fitting
popt, _ = curve_fit(exp_func, time_fit, temperature, p0=[-8.5, 0.01, 36, 0])

# Generate points for the fitted curve
temp_fit = exp_func(time_fit, *popt)

# Create the plot
plt.figure(figsize=(12, 6))
plt.scatter(time_fit, temperature, label='Original data')
plt.plot(time_fit, temp_fit, 'r-', label='Fitted curve')

plt.xlabel('Time')
plt.ylabel('Temperature (MAX30205)')
plt.title('Exponential Curve Fitting of Temperature Data')
plt.legend()

plt.grid(True)
plt.show()

# Print the fitted parameters
print(f"Fitted parameters: a = {popt[0]:.4f}, b = {popt[1]:.4f}, c = {popt[2]:.4f}, d = {popt[3]:.4f}")