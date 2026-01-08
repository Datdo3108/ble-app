import os
import pandas as pd
import numpy as np
import asyncio
from bleak import BleakScanner
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from qasync import QEventLoop
import time

# Specify the name of the target device
TARGET_DEVICE_NAME = "FSEMI1"

# Save output data as an empty list (easier to append and then convert to NumPy array)
# ntc_data_list = []
# time_data_list = []
ntc_data_list = np.array([])
time_data_list = np.array([])
output_data_folder = "Data"
scanning = False
sampling_interval = 1  # assuming data is collected every 1 second
window_duration = 80  # length of the sliding window in seconds

# Create the PyQtGraph window for plotting
app = QtWidgets.QApplication([])  # QApplication is in QtWidgets
win = pg.GraphicsLayoutWidget(show=True, title="Real-Time NTC Data Plot")
win.resize(1200, 600)
plot = win.addPlot(title="NTC Data Over Time (Sliding Window - 60 seconds)")
curve = plot.plot(pen='y')  # Create a curve to update with new data

marker_curve_time = [0, 60]
marker_curve_range = [2500, 4500]
marker_curve = plot.plot(pen=(0, 0, 0, 0))
marker_curve.setData(marker_curve_time, marker_curve_range)

# Initialize X-axis for time and Y-axis for data
# time_data = []
# plot_data = []
time_data = np.array([])
plot_data = np.array([])
time_0 = time.time()



# Create buttons and input fields for user interaction
save_button = QtWidgets.QPushButton("Save to Excel")
save_button.setFixedHeight(40)

stop_button = QtWidgets.QPushButton("Stop Recording")
stop_button.setFixedHeight(40)

filename_lineedit = QtWidgets.QLineEdit("filename")
filename_lineedit.setFixedHeight(40)

# Layout for button
layout = QtWidgets.QVBoxLayout()
layout.addWidget(filename_lineedit)
layout.addWidget(save_button)
layout.addWidget(stop_button)
layout.addWidget(win)

# Create a container widget and set the layout
container = QtWidgets.QWidget()
container.setLayout(layout)
container.setWindowTitle("BLE Data Plot with Save Option")
container.show()

# Callback to process discovered devices
def detection_callback(device, advertisement_data):
    global ntc_data_list, time_data_list, time_data, plot_data, scanning, marker_curve_time, marker_curve_range, time_0
    
    if not scanning:
        return

    # Check if the discovered device matches the target name
    if device.name == TARGET_DEVICE_NAME:
        print(f"Found target device: {device.name}, {device.address}")
        print(f"RSSI: {device.rssi}")
        
        # Access the advertisement data
        if advertisement_data.manufacturer_data:
            data = advertisement_data.manufacturer_data[62945]

            # Extract data (assuming these are correct indices)
            ntc_data = int.from_bytes(data[10:12], byteorder='little')

            # Append the extracted ntc_data to the list
            # ntc_data_list.append(ntc_data)
            # time_data_list.append(time.time() - time_0)
            ntc_data_list = np.append(ntc_data_list, ntc_data)
            if(len(ntc_data_list) == 1):
                time_0 = time.time()
            time_data_list = np.append(time_data_list, time.time() - time_0)
            # time_data.append(time.time() - time_0)
            # plot_data.append(ntc_data)
            time_data = np.append(time_data, time.time() - time_0)
            plot_data = np.append(plot_data, ntc_data)

            # Limit the data displayed to the last 20 seconds
            num_points_in_window = window_duration // sampling_interval
            # if len(time_data) > num_points_in_window:
            if time_data[-1] > window_duration:
                time_data = time_data[-num_points_in_window:]
                plot_data = plot_data[-num_points_in_window:]

                marker_curve_time = [time_data[0], time_data[-1]]

            # Update the plot with data in the sliding window
            curve.setData(time_data, plot_data)
            marker_curve.setData(marker_curve_time, marker_curve_range)
            app.processEvents()  # This ensures the plot gets updated in real-time

            print("NTC data:", ntc_data)
        
        if advertisement_data.service_uuids:
            print("Service UUIDs:", advertisement_data.service_uuids)
        
        if advertisement_data.local_name:
            print("Local Name:", advertisement_data.local_name)

# Function to start scanning for BLE devices
async def start_scan():
    global scanning
    scanner = BleakScanner()
    scanner.register_detection_callback(detection_callback)

    scanning = True
    print("Scanning for BLE devices...")

    await scanner.start()
    
    # Continue scanning until the stop button is pressed
    while scanning:
        await asyncio.sleep(1)
    
    await scanner.stop()
    print("Scan stopped.")
    print("Number of samples: ", len(ntc_data_list))

# Function to stop recording when stop button is clicked
def stop_recording():
    global scanning
    scanning = False
    print("Recording stopped.")

# Function to check and generate a unique filename
def generate_unique_filename(directory, filename):
    base, ext = os.path.splitext(filename)
    i = 1
    unique_filename = filename
    while os.path.exists(os.path.join(directory, unique_filename)):
        unique_filename = f"{base}_{i}{ext}"
        i += 1
    return unique_filename

# Function to save data to Excel when the button is clicked
def save_to_excel():
    if ntc_data_list.any():
        # Convert the data list to NumPy array
        ntc_data_array = np.array(ntc_data_list)
        time_data_array = np.array(time_data_list)
        
        # Ensure the output folder exists
        if not os.path.exists(output_data_folder):
            os.makedirs(output_data_folder)

        # Generate a unique filename if the file already exists
        base_filename = filename_lineedit.text() + str(".xlsx")
        file_path = generate_unique_filename(output_data_folder, base_filename)

        print(len(time_data_array))
        print(len(ntc_data_array))
        
        # Save the data to an Excel file
        df = pd.DataFrame({
            "Time (seconds)": time_data_array,
            "NTC Data": ntc_data_array
        })
        
        df.to_excel(os.path.join(output_data_folder, file_path), index=False)
        print(f"Data saved to {file_path}")
    else:
        print("No data available to save.")

# Connect the button click events to their respective functions
save_button.clicked.connect(save_to_excel)
stop_button.clicked.connect(stop_recording)

# Create and run the asyncio event loop with qasync
loop = QEventLoop(app)
asyncio.set_event_loop(loop)

# Start the scan loop
with loop:
    loop.run_until_complete(start_scan())
    app.exec_()  # Start the PyQtGraph application
