import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, TextBox
import os
import subprocess
import time
import keyboard
import threading

# Global variables
channel_0 = np.array([])
channel_1 = np.array([])
channel_2 = np.array([])
channel_3 = np.array([])
time_series = np.array([])
stop_reading = False
file_path = ""

def launch_jlink_rtt_viewer():
    global file_path
    jlink_rtt_viewer_path = "C:/Program Files/SEGGER/JLink_V798i/JLinkRTTViewer.exe"  # Adjust the path

    # Launch the JLinkRTTViewer
    process = subprocess.Popen([jlink_rtt_viewer_path])

    # Give the viewer some time to open
    time.sleep(1)

    # Simulate pressing 'Enter' to connect
    keyboard.send("enter")

    # Simulate pressing F5 to start logging
    keyboard.send("f5")

    # Give some time for the file save dialog to appear
    time.sleep(0.5)

    # Generate a unique filename using a timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    file_name = f"my_log_{timestamp}.txt"

    # Type the unique filename
    keyboard.write(file_name)

    # Press Enter to confirm saving the log with the given filename
    keyboard.send("enter")

    folder_path = r"G:\Project\FSemi\Temp measurement\nrfLogging"
    file_path = os.path.join(folder_path, file_name)

    return process

def read_data_from_file():
    global channel_0, channel_1, channel_2, channel_3, time_series, stop_reading

    start_time = time.time()
    while not stop_reading:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                new_lines = file.readlines()
                for line in new_lines:
                    if line.startswith("00> <info> app: $$$$Channel 0 final:"):
                        value = float(line[36:].strip())
                        channel_0 = np.append(channel_0,value)
                        current_time = time.time() - start_time
                        time_series = np.append(time_series,current_time)
                    elif line.startswith("00> <info> app: @@@@Channel 1 final:"):
                        value = float(line[36:].strip())
                        channel_1 = np.append(channel_1,value)
                    elif line.startswith("00> <info> app: ____Channel 2 final:"):
                        value = float(line[36:].strip())
                        channel_2 = np.append(channel_2,value)
                    elif line.startswith("00> <info> app: MAX30205 temp:"):
                        value = float(line[30:].strip()) / 100
                        channel_3 = np.append(channel_3,value)
                        
        time.sleep(0.1)  # Short delay to prevent excessive CPU usage

def update_plot(frame):
    ax.clear()
    ax.plot(time_series, channel_0, label='NTC', marker='o')
    # ax.plot(time_series, channel_3, label='MAX', marker='o')
    ax.set_title('Channel Data Over Time')
    ax.set_xlabel('Time (seconds)')
    ax.set_ylabel('Channel Value')
    ax.legend()

def save_to_excel(event):
    base_path = filename_textbox.text.strip() + '.xlsx'
    output_file = generate_filename(base_path)
    df = pd.DataFrame({
        'Time': time_series,
        'NTC': channel_0,
        'GPIO offset': channel_1,
        'VDD': channel_2,
        'MAX30205': channel_3
    })
    with pd.ExcelWriter(output_file) as writer:
        df.to_excel(writer, sheet_name="Data", index=False)
    print(f'Data saved to {output_file}')

def generate_filename(base_filename):
    counter = 1
    base, extension = os.path.splitext(base_filename)
    new_filename = base_filename
    while os.path.exists(new_filename):
        new_filename = f"{base}_{counter}{extension}"
        counter += 1
    return new_filename

# Main execution
jlink_process = launch_jlink_rtt_viewer()

# Start the data reading thread
read_thread = threading.Thread(target=read_data_from_file)
read_thread.start()

# Set up the plot
fig, ax = plt.subplots(figsize=(12, 8))
plt.subplots_adjust(bottom=0.2)

# Maximize the window
mng = plt.get_current_fig_manager()
try:
    mng.window.state('zoomed')
except:
    try:
        mng.window.showMaximized()
    except:
        mng.full_screen_toggle()

# Add a text box for filename input
ax_filename_input = plt.axes([0.1, 0.01, 0.6, 0.05])
filename_textbox = TextBox(ax_filename_input, 'Enter filename:', initial='')

# Add a button for saving
ax_save_button = plt.axes([0.8, 0.01, 0.1, 0.05])
btn_save = Button(ax_save_button, 'Save Excel')
btn_save.on_clicked(save_to_excel)

# Create the animation
ani = FuncAnimation(fig, update_plot, interval=100)

plt.show()

# Clean up
stop_reading = True
read_thread.join()
jlink_process.terminate()