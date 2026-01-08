
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox
import os
import subprocess
import time
import keyboard

# Step 1: Launch JLinkRTTViewer to generate the log file
jlink_rtt_viewer_path = "C:/Program Files/SEGGER/JLink_V798i/JLinkRTTViewer.exe"  # Adjust the path

# Launch the JLinkRTTViewer
process = subprocess.Popen([jlink_rtt_viewer_path])

# Give the viewer some time to open
time.sleep(1)

# Simulate pressing 'Enter' to connect (assuming Enter works to initiate)
keyboard.send("enter")

# Simulate pressing F5 to start logging (if F5 starts logging)
keyboard.send("f5")
time_0 = time.time()

# Give some time for the file save dialog to appear
time.sleep(0.5)

# Step 2: Generate a unique filename using a timestamp
timestamp = time.strftime("%Y%m%d_%H%M%S")  # Example: 20240925_153012
file_name = f"my_log_{timestamp}.txt"       # File name with timestamp

# Type the unique filename
keyboard.write(file_name)

# Press Enter to confirm saving the log with the given filename
keyboard.send("enter")

# Wait for the user to close the viewer
process.wait()
time_end = time.time() - time_0

# Step 3: Read the log file and extract the data
# Initialize lists to hold the data for each channel
channel_0 = np.array([])
channel_1 = np.array([])
channel_2 = np.array([])
channel_3 = np.array([])

folder_path = r"G:\Project\FSemi\Temp measurement\nrfLogging"
file_path = os.path.join(folder_path, file_name)

# Read the file and extract data
with open(file_path, 'r') as file:
    for line in file:
        if line.startswith("00> <info> app: $$$$Channel 0 final:"):
            value = line[36:].strip()
            channel_0 = np.append(channel_0, np.float32(value))
        elif line.startswith("00> <info> app: @@@@Channel 1 final:"):
            value = line[36:].strip()
            channel_1 = np.append(channel_1, np.float32(value))
        elif line.startswith("00> <info> app: ____Channel 2 final:"):
            value = line[36:].strip()
            channel_2 = np.append(channel_2, np.float32(value))
        # elif line.startswith("00> <info> app: MAX30205 temp:"):
        #     value = line[30:].strip()
        #     channel_3 = np.append(channel_3, np.float32(value)/100)

end_time = time.time()
print(end_time)

# Ensure all channels have the same length
data_len = min(len(channel_0), len(channel_1))
channel_0 = channel_0[:data_len]
channel_1 = channel_1[:data_len]
# channel_2 = channel_2[:data_len]

# Generate time axis (assuming uniform time intervals)
# time_series = pd.Series(range(len(data)))
time_series = np.linspace(0, time_end, data_len)
time_series_max = np.linspace(0, time_end, len(channel_3))

# Create a DataFrame
data = pd.DataFrame({
    'Time': time_series,
    'NTC': channel_0,
    # 'GPIO offset': channel_1,
    'VDD': channel_1,
})

# data_max = pd.DataFrame({
#     'Time': time_series_max,
#     'MAX30205': channel_3,
# })

# Step 4: Plot the data
fig, ax = plt.subplots(figsize=(12, 8))
plt.subplots_adjust(bottom=0.2)  # Make space for the button and text box

# Maximize the window
mng = plt.get_current_fig_manager()
try:
    mng.window.state('zoomed')  # For TkAgg backend (Windows)
except:
    try:
        mng.window.showMaximized()  # For QtAgg backend (Linux)
    except:
        mng.full_screen_toggle()  # Fallback for other backends

# Plotting
line1, = ax.plot(time_series, data['NTC'], label='NTC', marker='o')
# line2, = ax.plot(time_series, data['GPIO offset'], label='GPIO offset', marker='o')
line3, = ax.plot(time_series, data['VDD'], label='VDD', marker='o')
# line4, = ax.plot(time_series_max, data_max['MAX30205'], label='MAX', marker='o')

# Customize the plot
plt.title('Channel Data Over Time')
plt.xlabel('Time (arbitrary units)')
plt.ylabel('Channel Value')
plt.legend()

# Generate a unique filename to prevent overwriting
def generate_filename(base_filename):
    counter = 1
    base, extension = os.path.splitext(base_filename)
    new_filename = base_filename
    while os.path.exists(new_filename):
        new_filename = f"{base}_{counter}{extension}"
        counter += 1
    return new_filename

# Save function
def save_to_excel(event):
    base_path = filename_textbox.text.strip() + '.xlsx'  # Use the input from the text box
    output_file = generate_filename(base_path)
    with pd.ExcelWriter(output_file) as writer:
        data.to_excel(writer, sheet_name="NTC Data", index=False)
        # data_max.to_excel(writer, sheet_name="MAX30205 Data", index=False)
    
    # data.to_excel(output_file, index=False)
    print(f'Data saved to {output_file}')

# Add a text box for filename input
ax_filename_input = plt.axes([0.1, 0.01, 0.6, 0.05])  # [left, bottom, width, height]
filename_textbox = TextBox(ax_filename_input, 'Enter filename:', initial=None)
filename_textbox.set_val(end_time)  # Set initial value

# Add a button for saving
ax_save_button = plt.axes([0.8, 0.01, 0.1, 0.05])  # [left, bottom, width, height]
btn_save = Button(ax_save_button, 'Save Excel')
btn_save.on_clicked(save_to_excel)

print("Average value NTC: ", np.average(data['NTC']))
print("STD: ", np.std(data['NTC']))

print("Average value Offset: ", np.average(data['VDD']))
print("STD: ", np.std([data['VDD']]))


# Show the plot
plt.show()
