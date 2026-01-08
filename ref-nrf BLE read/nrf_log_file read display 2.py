import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox
import os

# Read the log file
file_path = r"G:\Project\FSemi\Temp measurement\nrfLogging\my_log_20240930_122432.txt"

# Initialize lists to hold the data for each channel
channel_0 = []
channel_1 = []
channel_2 = []

# Read the file and extract data
with open(file_path, 'r') as file:
    for line in file:
        if line.startswith("00> <info> app: $$$$Channel 0 final:"):
            value = line[36:].strip()
            channel_0.append(float(value))
        elif line.startswith("00> <info> app: @@@@Channel 1 final:"):
            value = line[36:].strip()
            channel_1.append(float(value))
        elif line.startswith("00> <info> app: ____Channel 2 final:"):
            value = line[36:].strip()
            channel_2.append(float(value))

data_len = len(channel_2)
channel_0 = channel_0[:data_len]
channel_1 = channel_1[:data_len]

# Create a DataFrame
data = pd.DataFrame({
    'Channel 0': channel_0,
    'Channel 1': channel_1,
    'Channel 2': channel_2,
})

# Generate time axis (assuming uniform time intervals)
time = pd.Series(range(len(data)))

# Create the plot
fig, ax = plt.subplots(figsize=(12, 8))
plt.subplots_adjust(bottom=0.2)  # Make space for the button and text box

# Maximize the window
mng = plt.get_current_fig_manager()
try:
    # Maximize for different backends
    mng.window.state('zoomed')  # For TkAgg backend (Windows)
except:
    try:
        mng.window.showMaximized()  # For QtAgg backend (Linux)
    except:
        mng.full_screen_toggle()  # Fallback for other backends

# Plotting
line1, = ax.plot(time, data['Channel 0'], label='Channel 0', marker='o')
line2, = ax.plot(time, data['Channel 1'], label='Channel 1', marker='o')
line3, = ax.plot(time, data['Channel 2'], label='Channel 2', marker='o')

# Customize the plot
plt.title('Channel Data Over Time')
plt.xlabel('Time (arbitrary units)')
plt.ylabel('Value')
plt.legend()
plt.grid()

# Function to generate a new filename if it already exists
def generate_filename(base_path):
    base_filename = os.path.splitext(base_path)[0]
    extension = os.path.splitext(base_path)[1]
    counter = 1
    
    new_filename = base_filename + extension
    while os.path.exists(new_filename):
        new_filename = f"{base_filename}_{counter}{extension}"
        counter += 1
    return new_filename

# Save function
def save_to_excel(event):
    base_path = filename_textbox.text.strip() + '.xlsx'  # Use the input from the text box
    output_file = generate_filename(base_path)
    data.to_excel(output_file, index=False)
    print(f'Data saved to {output_file}')

# Add a text box for filename input
ax_filename_input = plt.axes([0.1, 0.01, 0.6, 0.05])  # [left, bottom, width, height]
filename_textbox = TextBox(ax_filename_input, 'Enter filename:', initial=None)
filename_textbox.set_val('')  # Set initial value

# Add a button for saving
ax_save_button = plt.axes([0.8, 0.01, 0.1, 0.05])  # [left, bottom, width, height]
btn_save = Button(ax_save_button, 'Save Excel')
btn_save.on_clicked(save_to_excel)

# Show the plot
plt.show()
