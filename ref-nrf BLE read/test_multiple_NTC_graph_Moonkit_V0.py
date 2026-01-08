import os
import pandas as pd
import numpy as np
import asyncio
from bleak import BleakScanner
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from qasync import QEventLoop
import time

# Specify the names of the target devices
TARGET_DEVICE_NAME_1 = "FSEMI4"
TARGET_DEVICE_NAME_2 = "FSEMI6"
TARGET_DEVICE_NAME_3 = "FSEMI8"

# Data storage arrays for both devices
bat_sense_list_1 = []
ntc_data_list_1 = []
max30205_data_list_1 = []
time_data_list_1 = []

bat_sense_list_2 = []
ntc_data_list_2 = []
max30205_data_list_2 = []
time_data_list_2 = []

output_data_folder = "Data"
scanning = False
sampling_interval = 1  # assuming data is collected every 1 second
window_duration = 200  # length of the sliding window in seconds

# Create the PyQtGraph window for plotting
app = QtWidgets.QApplication([])  # QApplication is in QtWidgets
win = pg.GraphicsLayoutWidget(show=True, title="Real-Time Data Plot")
win.resize(1200, 600)

# First device plot (FSEMI1)
plot_1 = win.addPlot(title="NTC Data Over Time " + TARGET_DEVICE_NAME_1)
curve_bat_1 = plot_1.plot(pen='g')
curve_ntc_1 = plot_1.plot(pen='y')  # Yellow curve for FSEMI1 NTC data
curve_max_30205_1 = plot_1.plot(pen='w')  # White curve for FSEMI1 MAX30205 data

# Second device plot (FSEMI2)
plot_2 = win.addPlot(title="NTC Data Over Time " + TARGET_DEVICE_NAME_2)
curve_bat_2 = plot_2.plot(pen='g')
curve_ntc_2 = plot_2.plot(pen='y')  # Green curve for FSEMI2 NTC data
curve_max_30205_2 = plot_2.plot(pen='w')  # Blue curve for FSEMI2 MAX30205 data

# Graph marker range
marker_curve_time = [0, 200]
marker_curve_range = [0, 50]

marker_curve_1 = plot_1.plot(pen=(0, 0, 0, 0))
marker_curve_1.setData(marker_curve_time, marker_curve_range)
marker_curve_2 = plot_2.plot(pen=(0, 0, 0, 0))
marker_curve_2.setData(marker_curve_time, marker_curve_range)

# Initialize time tracking and data arrays for plotting
time_0 = time.time()
time_data_1 = []
plot_data_bat_1 = []
plot_data_ntc_1 = []
plot_data_max_30205_1 = []

time_data_2 = []
plot_data_bat_2 = []
plot_data_ntc_2 = []
plot_data_max_30205_2 = []

# Create buttons and input fields for user interaction
save_button = QtWidgets.QPushButton("Save to Excel")
save_button.setFixedHeight(40)

stop_button = QtWidgets.QPushButton("Stop Recording")
stop_button.setFixedHeight(40)

filename_lineedit = QtWidgets.QLineEdit("filename")
filename_lineedit.setFixedHeight(40)

# Layout for buttons and plot
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
    global time_0
    global time_data_1, plot_data_bat_1, plot_data_ntc_1, plot_data_max_30205_1
    global time_data_2, plot_data_bat_2, plot_data_ntc_2, plot_data_max_30205_2

    if not scanning:
        return

    if device.name == TARGET_DEVICE_NAME_1:
        handle_device_data(advertisement_data, bat_sense_list_1, ntc_data_list_1, max30205_data_list_1, time_data_list_1, time_data_1, plot_data_bat_1, plot_data_ntc_1, plot_data_max_30205_1, curve_bat_1, curve_ntc_1, curve_max_30205_1, marker_curve_1, TARGET_DEVICE_NAME_1)
    
    elif device.name == TARGET_DEVICE_NAME_2:
        handle_device_data(advertisement_data, bat_sense_list_2, ntc_data_list_2, max30205_data_list_2, time_data_list_2, time_data_2, plot_data_bat_2, plot_data_ntc_2, plot_data_max_30205_2, curve_bat_2, curve_ntc_2, curve_max_30205_2, marker_curve_2, TARGET_DEVICE_NAME_2)

# Helper function to handle device data (common for both FSEMI1 and FSEMI2)
def handle_device_data(advertisement_data, bat_sense_list, ntc_data_list, max30205_data_list, time_data_list, time_data, plot_data_bat, plot_data_ntc, plot_data_max_30205, curve_bat, curve_ntc, curve_max_30205, marker_curve, device_name):
    global time_0, marker_curve_time, marker_curve_range

    if advertisement_data.manufacturer_data:
        key = next(iter(advertisement_data.manufacturer_data), None)
        if key is not None:
            data = advertisement_data.manufacturer_data[key]
            print(f"Using manufacturer ID {key}, Data: {data}")
        else:
            print("No manufacturer data available.")
        # data = advertisement_data.manufacturer_data[62945]

        # Extract data (assuming these are correct indices)
        bat_data = int.from_bytes(data[18:19], byteorder='little')
        ntc_data = int.from_bytes(data[16:18], byteorder='little')/100
        max_30205_data = int.from_bytes(data[2:4], byteorder='little')/1000

        print("Device: ", device_name, "GPIO offset: ", max_30205_data, "NTC data: ", ntc_data)

        bat_sense_list.append(bat_data)
        ntc_data_list.append(ntc_data)
        max30205_data_list.append(max_30205_data)
        if len(ntc_data_list) == 1:
            time_0 = time.time()
        time_data_list.append(time.time() - time_0)
        time_data.append(time.time() - time_0)
        plot_data_bat.append(bat_data)
        plot_data_ntc.append(ntc_data)
        plot_data_max_30205.append(max_30205_data)

        # Limit data to sliding window
        num_points_in_window = window_duration // sampling_interval
        if time_data[-1] > window_duration:
            time_data[:] = time_data[-num_points_in_window:]
            plot_data_bat[:] = plot_data_bat[-num_points_in_window:]
            plot_data_ntc[:] = plot_data_ntc[-num_points_in_window:]
            plot_data_max_30205[:] = plot_data_max_30205[-num_points_in_window:]

            marker_curve_time = [time_data[0], time_data[-1]]

        # Update the plot with data in the sliding window
        curve_bat.setData(time_data, plot_data_bat)
        curve_ntc.setData(time_data, plot_data_ntc)
        curve_max_30205.setData(time_data, plot_data_max_30205)
        marker_curve.setData(marker_curve_time, marker_curve_range)

        app.processEvents()

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
    print(f"Number of samples for " + TARGET_DEVICE_NAME_1 + " : {len(ntc_data_list_1)}")
    print(f"Number of samples for " + TARGET_DEVICE_NAME_2 + " : {len(ntc_data_list_2)}")
    print(time.time())

# Function to stop recording when stop button is clicked
def stop_recording():
    global scanning 
    scanning = False
    print("Recording stopped.")

# Function to generate a unique filename if it already exists
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
    if ntc_data_list_1 or ntc_data_list_2:
        # Ensure output folder exists
        if not os.path.exists(output_data_folder):
            os.makedirs(output_data_folder)

        # Generate unique filename if file already exists
        base_filename = filename_lineedit.text() + str(".xlsx")
        file_path = generate_unique_filename(output_data_folder, base_filename)

        # Save data to Excel file
        df1 = pd.DataFrame({
            "Time (seconds)": time_data_list_1,
            "NTC Data": ntc_data_list_1,
        })

        df2 = pd.DataFrame({
            "Time (seconds)": time_data_list_2,
            "NTC Data": ntc_data_list_2,
        })

        # Write both dataframes to separate sheets in Excel
        with pd.ExcelWriter(os.path.join(output_data_folder, file_path)) as writer:
            df1.to_excel(writer, sheet_name=TARGET_DEVICE_NAME_1, index=False)
            df2.to_excel(writer, sheet_name=TARGET_DEVICE_NAME_2, index=False)

        print(f"Data saved to {file_path}")
    else:
        print("No data available to save.")

# Connect button clicks to their respective functions
save_button.clicked.connect(save_to_excel)
stop_button.clicked.connect(stop_recording)

# Start the event loop and the BLE scan
loop = QEventLoop(app)
asyncio.set_event_loop(loop)

with loop:
    loop.run_until_complete(start_scan())
    app.exec_()
