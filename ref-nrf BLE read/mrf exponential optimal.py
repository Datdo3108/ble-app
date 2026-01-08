import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.optimize import curve_fit

# Read the CSV data
data = pd.read_csv(r'3 - 12 nrf\csv\3 - 12 nrf - armpit 1.csv')
downsampling_factor = 4
data_downsampled = data.iloc[::downsampling_factor, :]

# Extract time and temperature data
time = data_downsampled['Time'].values
temperature = data_downsampled['NTC'].values
time = time - time[0]  # Start time from 0

# Define the exponential function
# def exp_func(t, a, b, c, d):
#     return -a * np.exp(b * (np.power(t,d))) + c + a

# def exp_func(t, a, b, d):
#     return -a * np.exp(b * (np.power(t,d))) + np.min(data_downsampled['NTC']) + a

# def exp_func(t, a, b, c, d):
#     return b + c - c*np.exp(-np.power(t/d,a))

## For logarithm function
def exp_func(t, a, b, c, d):
    return a + c*np.log(np.power((t+d), b))


# def exp_func(t, a, b, c):
#     return np.min(data_downsampled['NTC']) + b*np.exp(a-np.power(t, -c))

# Initial parameter guesses
# p0 = [10, -0.1, 0.8]  # [a, b, c, d]
# p0 = [0, 10, 0.1]
# p0 = [0.5, 25, 12, 1000]

## For logarithm function
p0 = [30, 0.01, 8, 0]

# Find optimal parameters
popt, pcov = curve_fit(exp_func, time, temperature, p0=p0)
a_opt, b_opt, c_opt, d_opt = popt

# Create smooth time points for the fitted curve
t_fit = np.linspace(time.min(), time.max(), 5000)
temp_fit = exp_func(t_fit, a_opt, b_opt, c_opt, d_opt)

# Calculate R-squared
y_fit = exp_func(time, a_opt, b_opt, c_opt, d_opt)
residuals = temperature - y_fit
ss_res = np.sum(residuals**2)
ss_tot = np.sum((temperature - np.mean(temperature))**2)
r_squared = 1 - (ss_res / ss_tot)

# Print the optimal parameters
print(f"Optimal parameters:")
print(f"a = {a_opt:.4f}")
print(f"b = {b_opt:.4f}")
print(f"c = {c_opt:.4f}")
print(f"d = {d_opt:.4f}")
print(f"R² = {r_squared:.4f}")

# Create the plot
plt.figure(figsize=(10, 6))
plt.scatter(time, temperature, color='blue', alpha=0.5, label='Data', s=20)
plt.plot(t_fit, temp_fit, 'r-', label='Fitted Curve', linewidth=2)

# Add labels and title
plt.xlabel('Time (s)')
plt.ylabel('Temperature (°C)')
plt.title('Exponential Fit to Temperature Data')

# Add the equation and R² value
# equation_text = f'T = {a_opt:.4f} * exp({b_opt:.4f} * t^{d_opt:.4f}) + {c_opt:.4f}\nR² = {r_squared:.4f}\nInitial temp = {c_opt+a_opt:.2f}\nFinal temp = {c_opt:.2f}'
# plt.text(0.05, 0.95, equation_text, transform=plt.gca().transAxes,
#          verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

plt.legend()
plt.grid(True, alpha=0.3)
plt.show()