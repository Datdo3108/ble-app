import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
import os

# Read the CSV file
file_path = r'3 - 12 nrf\csv\3 - 12 nrf - armpit 1.csv'
df = pd.read_csv(file_path)

# Extract Time, NTC, and MAX30205 columns
time = df['Time']
ntc = df['NTC']
# max30205 = df['MAX30205']

# Convert Time to seconds since the start
time_seconds = time - time.iloc[0]

# Downsample the data by taking the average of every 50 points
def downsample(x, y, n=16):
    x_downsampled = x[::n]
    y_downsampled = [np.mean(y[i:i+n]) for i in range(0, len(y), n)]
    return x_downsampled, y_downsampled

time_downsampled, ntc_downsampled = downsample(time_seconds, ntc)
# _, max30205_downsampled = downsample(time_seconds, max30205)

# Function to fit polynomial and calculate MSE
def fit_polynomial(X, y, degree):
    coeffs = np.polyfit(X, y, degree)
    poly = np.poly1d(coeffs)
    return poly

def calculate_mse(y_true, y_pred):
    return mean_squared_error(y_true, y_pred)

# Determine optimal polynomial degree for both NTC and MAX30205 data
max_degree = 25
degrees = range(1, max_degree + 1)

def find_optimal_degree(X_downsampled, y_downsampled):
    mse_scores = []
    for degree in degrees:
        X_train, X_test, y_train, y_test = train_test_split(X_downsampled, y_downsampled, test_size=0.2, random_state=42)
        poly = fit_polynomial(X_train, y_train, degree)
        y_pred = poly(X_test)
        mse = calculate_mse(y_test, y_pred)
        mse_scores.append(mse)
    optimal_degree = degrees[np.argmin(mse_scores)]
    return optimal_degree, mse_scores

# # Find optimal degrees and MSE for both NTC and MAX30205
# optimal_degree_ntc, mse_scores_ntc = find_optimal_degree(time_downsampled, ntc_downsampled)
# # optimal_degree_max30205, mse_scores_max30205 = find_optimal_degree(time_downsampled, max30205_downsampled)

# # Fit the polynomials with the optimal degrees
# optimal_poly_ntc = fit_polynomial(time_downsampled, ntc_downsampled, optimal_degree_ntc)
# # optimal_poly_max30205 = fit_polynomial(time_downsampled, max30205_downsampled, optimal_degree_max30205)

# # Calculate predicted values and errors
# y_pred_ntc = optimal_poly_ntc(time_downsampled)
# errors_ntc = np.array(ntc_downsampled) - y_pred_ntc

# y_pred_max30205 = optimal_poly_max30205(time_downsampled)
# errors_max30205 = np.array(max30205_downsampled) - y_pred_max30205

# Create a DataFrame to store downsampled time, NTC, MAX30205, and their polynomial predictions
results_df = pd.DataFrame({
    'Time (s)': time_downsampled,
    'NTC (downsampled)': ntc_downsampled,
    # 'NTC (polyfit)': y_pred_ntc,
    # 'MAX30205 (downsampled)': max30205_downsampled,
    # 'MAX30205 (polyfit)': y_pred_max30205
})

# Save the results to a CSV file
output_file_path = os.path.splitext(file_path)[0] + '_polynomial_fit_results.csv'
results_df.to_csv(output_file_path, index=False)

# Create a figure with subplots
fig, axs = plt.subplots(2, 3, figsize=(24, 16))
fig.suptitle('Temperature Analysis Results (Downsampled Data)', fontsize=16)

# Plot 1: NTC - Original and downsampled data with polynomial fit
axs[0, 0].scatter(time_seconds, ntc, label='Original Data (NTC)', alpha=0.5, s=10)
axs[0, 0].scatter(time_downsampled, ntc_downsampled, label='Downsampled Data (NTC)', color='red', s=20)
x_fit_ntc = np.linspace(time_downsampled.min(), time_downsampled.max(), 100)
# y_fit_ntc = optimal_poly_ntc(x_fit_ntc)
# axs[0, 0].plot(x_fit_ntc, y_fit_ntc, color='green', label=f'Polynomial Fit (degree {optimal_degree_ntc})')
axs[0, 0].set_xlabel('Time (seconds)')
axs[0, 0].set_ylabel('Temperature (°C)')
axs[0, 0].set_title('NTC Temperature Over Time')
axs[0, 0].legend()
axs[0, 0].grid(True)

# Plot 2: MAX30205 - Original and downsampled data with polynomial fit
# axs[0, 0].scatter(time_seconds, max30205, label='Original Data (MAX30205)', alpha=0.5, s=10)
# axs[0, 0].scatter(time_downsampled, max30205_downsampled, label='Downsampled Data (MAX30205)', color='blue', s=20)
x_fit_max30205 = np.linspace(time_downsampled.min(), time_downsampled.max(), 100)
# y_fit_max30205 = optimal_poly_max30205(x_fit_max30205)
# axs[0, 0].plot(x_fit_max30205, y_fit_max30205, color='green', label=f'Polynomial Fit (degree {optimal_degree_max30205})')
axs[0, 0].set_xlabel('Time (seconds)')
axs[0, 0].set_ylabel('Temperature (°C)')
axs[0, 0].set_title('MAX30205 Temperature Over Time')
axs[0, 0].legend()
axs[0, 0].grid(True)

# Plot 3: MSE vs Degree for NTC
# axs[0, 2].plot(degrees, mse_scores_ntc, marker='o', label='NTC')
axs[0, 2].set_xlabel('Polynomial Degree')
axs[0, 2].set_ylabel('Mean Squared Error')
axs[0, 2].set_title('MSE vs Polynomial Degree (NTC)')
axs[0, 2].grid(True)

# Plot 4: MSE vs Degree for MAX30205
# axs[1, 0].plot(degrees, mse_scores_max30205, marker='o', label='MAX30205', color='blue')
axs[1, 0].set_xlabel('Polynomial Degree')
axs[1, 0].set_ylabel('Mean Squared Error')
axs[1, 0].set_title('MSE vs Polynomial Degree (MAX30205)')
axs[1, 0].grid(True)

# Plot 5: Error over time for NTC
# axs[1, 1].scatter(time_downsampled, errors_ntc, alpha=0.5, label='NTC Errors')
axs[1, 1].axhline(y=0, color='r', linestyle='--')
axs[1, 1].set_xlabel('Time (seconds)')
axs[1, 1].set_ylabel('Error (°C)')
axs[1, 1].set_title('NTC Error Over Time')
axs[1, 1].grid(True)

# Plot 6: Error over time for MAX30205
# axs[1, 2].scatter(time_downsampled, errors_max30205, alpha=0.5, label='MAX30205 Errors', color='blue')
axs[1, 2].axhline(y=0, color='r', linestyle='--')
axs[1, 2].set_xlabel('Time (seconds)')
axs[1, 2].set_ylabel('Error (°C)')
axs[1, 2].set_title('MAX30205 Error Over Time')
axs[1, 2].grid(True)

# Adjust layout and display the plot
plt.tight_layout()
plt.show()

# Print error statistics for NTC
# mean_error_ntc = np.mean(errors_ntc)
# std_error_ntc = np.std(errors_ntc)
# max_error_ntc = np.max(np.abs(errors_ntc))

# print(f"\nError statistics for NTC:")
# print(f"Mean error: {mean_error_ntc:.4f}°C")
# print(f"Standard deviation of error: {std_error_ntc:.4f}°C")
# print(f"Maximum absolute error: {max_error_ntc:.4f}°C")

# # Calculate and print RMSE for NTC
# rmse_ntc = np.sqrt(np.mean(errors_ntc**2))
# print(f"Root Mean Square Error (RMSE) for NTC: {rmse_ntc:.4f}°C")

# Print error statistics for MAX30205
# mean_error_max30205 = np.mean(errors_max30205)
# std_error_max30205 = np.std(errors_max30205)
# max_error_max30205 = np.max(np.abs(errors_max30205))

print(f"\nError statistics for MAX30205:")
# print(f"Mean error: {mean_error_max30205:.4f}°C")
# print(f"Standard deviation of error: {std_error_max30205:.4f}°C")
# print(f"Maximum absolute error: {max_error_max30205:.4f}°C")

# Calculate and print RMSE for MAX30205
# rmse_max30205 = np.sqrt(np.mean(errors_max30205**2))
# print(f"Root Mean Square Error (RMSE) for MAX30205: {rmse_max30205:.4f}°C")
