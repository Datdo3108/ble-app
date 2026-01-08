import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import pandas as pd

# Read the CSV data
# data = pd.read_csv(r'16-10\FSEMI1_air_armpit1_huge alufoil_16-10_test.csv')
data = pd.read_csv(r'3 - 12 nrf\csv\3 - 12 nrf - armpit 1.csv')
downsampling_factor = 16
data_downsampled = data.iloc[::downsampling_factor, :]

# Extract time and temperature data
time = data_downsampled['Time'].values
# temperature = data_downsampled['MAX30205'].values
temperature = data_downsampled['NTC'].values
time = time - time[0]

# Define the exponential function
def exp_func(t, a, b, c, d):
    return a * np.exp(b * t) + c

# def exp_func(t, a, b, c, d):
#     return a * np.exp(b * (t + d)) + c

# def exp_func(t, a, b, c):
#     return b + c - c*(a*t + 1)*np.exp(-a*t)

# def exp_func(t, a, b, c):
#     return b + c*np.exp(-np.power(t, -a))

# def exp_func(t, a, b, c, d):
#     return 26 + c - c*np.exp(-np.power((t-b)/d,a))

# def exp_func(t, a, b, c, d):
#     return a + c - c*np.exp(-(t-b)/d)

# ## For logarithm function
# def exp_func(t, a, b, c, d):
#     return a + c*np.log(np.power((t+d), b))

# Create the main plot
fig, ax = plt.subplots(figsize=(10, 8))
plt.subplots_adjust(left=0.1, bottom=0.25)

# Plot the original data
scatter = ax.scatter(time, temperature, color='blue', label='Original Data')

# Initial parameter values
a_init, b_init, c_init, d_init = 0, 0, 8, 10

# ## For logarithm function
# a_init, b_init, c_init, d_init = 30, 0, 8, 0

# Create the initial plot
t_fit = np.linspace(-20, time.max(), 5000)
line, = ax.plot(t_fit, exp_func(t_fit, a_init, b_init, c_init, d_init), 'r-', label='Fitted Curve')

ax.set_xlabel('Time')
ax.set_ylabel('Temperature (MAX30205)')
ax.set_title('Interactive Exponential Fit')
ax.legend()

# Create sliders
slider_color = 'lightgoldenrodyellow'
a_slider_ax = plt.axes([0.1, 0.15, 0.65, 0.03], facecolor=slider_color)
b_slider_ax = plt.axes([0.1, 0.1, 0.65, 0.03], facecolor=slider_color)
c_slider_ax = plt.axes([0.1, 0.05, 0.65, 0.03], facecolor=slider_color)
d_slider_ax = plt.axes([0.1, 0.00, 0.65, 0.03], facecolor=slider_color)

# a_slider = Slider(a_slider_ax, 'a', 0, 40, valinit=a_init)
# b_slider = Slider(b_slider_ax, 'b', 0, 10, valinit=b_init)
# c_slider = Slider(c_slider_ax, 'c', 0, 20, valinit=c_init)
# d_slider = Slider(d_slider_ax, 'd', 1, 100, valinit=d_init)

## For logarithm function
a_slider = Slider(a_slider_ax, 'a', 0, 40, valinit=a_init)
b_slider = Slider(b_slider_ax, 'b', 0, 10, valinit=b_init)
c_slider = Slider(c_slider_ax, 'c', 0, 20, valinit=c_init)
d_slider = Slider(d_slider_ax, 'd', -10, 10, valinit=d_init)

# Update function for the plot
def update(val):
    a = a_slider.val
    b = b_slider.val
    c = c_slider.val
    d = d_slider.val
    line.set_ydata(exp_func(t_fit, a, b, c, d))
    
    # Update the equation text
    # equation.set_text(f'T = {a:.4f} * exp({b:.4f} * t) + {c:.4f}')
    
    # Calculate and update R-squared
    # y_fit = exp_func(time, a, b, c)
    # residuals = temperature - y_fit
    # ss_res = np.sum(residuals**2)
    # ss_tot = np.sum((temperature - np.mean(temperature))**2)
    # r_squared = 1 - (ss_res / ss_tot)
    # r_squared_text.set_text(f'R² = {r_squared:.4f}')
    
    fig.canvas.draw_idle()

    
def auto_scale(event=None):
    # Get the current y-data
    y_data = line.get_ydata()
    y_scatter = scatter.get_offsets()[:, 1]
    
    # Calculate padding (10% of data range)
    y_min = min(np.min(y_data), np.min(y_scatter))
    y_max = max(np.max(y_data), np.max(y_scatter))
    y_padding = (y_max - y_min) * 0.1
    
    # Set y-axis limits with padding
    ax.set_ylim(y_min - y_padding, y_max + y_padding)
    
    # Set x-axis limits to show all data points
    x_min = min(np.min(t_fit), np.min(time))
    x_max = max(np.max(t_fit), np.max(time))
    x_padding = (x_max - x_min) * 0.05
    ax.set_xlim(x_min - x_padding, x_max + x_padding)
    
    fig.canvas.draw_idle()

autoscale_button_ax = plt.axes([0.8, 0.05, 0.15, 0.04])
autoscale_button = Button(autoscale_button_ax, 'Auto Scale')
autoscale_button.on_clicked(auto_scale)

# Connect the sliders to the update function
a_slider.on_changed(update)
b_slider.on_changed(update)
c_slider.on_changed(update)
d_slider.on_changed(update)

# Add text for the equation and R-squared
equation = ax.text(0.05, 0.95, '', transform=ax.transAxes, 
                   verticalalignment='top', fontsize=10,
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))

# r_squared_text = ax.text(0.05, 0.85, '', transform=ax.transAxes, 
#                          verticalalignment='top', fontsize=10,
#                          bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))

# Initial update to set the text
auto_scale()
update(None)

plt.show()