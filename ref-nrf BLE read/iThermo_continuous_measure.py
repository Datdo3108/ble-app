import asyncio
from bleak import BleakClient, BleakScanner
import signal
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from qasync import QEventLoop
import pandas as pd
import numpy as np
import time
from collections import deque
import logging
import os

output_data_folder = "FSEMI Temperature Data"

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Use deques with a fixed maximum length
max_points = 100
time_deque = deque(maxlen=max_points)
channel_1_deque = deque(maxlen=max_points)
channel_2_deque = deque(maxlen=max_points)
channel_3_deque = deque(maxlen=max_points)
channel_4_deque = deque(maxlen=max_points)
channel_5_deque = deque(maxlen=max_points)
channel_6_deque = deque(maxlen=max_points)

update_interval = 1  # Update plot every 10 data points
sample_rate = 4     # Sample rate in Hz

# Lists to save channel data
channel_1_list = np.array([])
channel_2_list = np.array([])
channel_3_list = np.array([])
channel_4_list = np.array([])
channel_5_list = np.array([])
channel_6_list = np.array([])
time_list = np.array([])

# Nordic UART Service (NUS) UUIDs
# NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"  # Replace with the correct one if different
# RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"      # RX characteristic for notifications

NUS_SERVICE_UUID = "1234"
RX_CHAR_UUID = "9876"

# Create the PyQtGraph window for plotting
app = QtWidgets.QApplication([])  # QApplication is in QtWidgets
win = pg.GraphicsLayoutWidget(show=True, title="Real-Time Data Plot")
win.resize(1200, 900)  # Adjust size to accommodate 6 plots

# Create six subplots (3 rows, 2 columns)
plots = []
curves = []
marker_curves = []
for i in range(6):
    plot = win.addPlot(title=f"Plot {i+1}")
    plots.append(plot)
    curves.append(plot.plot(pen=(i*40, 255, 255-i*40)))
    marker_curves.append(plot.plot(pen=(0, 0, 0, 0)))
    
    if i % 2 == 1:  # After every two plots, move to the next row
        win.nextRow()

# Set up each plot
for plot in plots:
    plot.setClipToView(True)
    plot.setDownsampling(mode='peak')
    plot.setYRange(20, 50)  # Set Y range based on your data
    # plot.setXRange(0, 20)

# Create buttons and input fields for user interaction
filename_lineedit = QtWidgets.QLineEdit("filename")
filename_lineedit.setFixedHeight(40)

save_button = QtWidgets.QPushButton("Save to Excel")
save_button.setFixedHeight(40)

stop_button = QtWidgets.QPushButton("Stop Recording")
stop_button.setFixedHeight(40)

# Layout for buttons and plot
layout = QtWidgets.QVBoxLayout()
layout.addWidget(filename_lineedit)
layout.addWidget(stop_button)
layout.addWidget(save_button)
layout.addWidget(win)

# Create a container widget and set the layout
container = QtWidgets.QWidget()
container.setLayout(layout)
container.setWindowTitle("BLE Data Plot with 6 Subplots")
container.show()
i = 0

# Global variable to control the loop
stop_flag = False

def handle_rx(sender, data):
    global i, time_deque, max_points
    global channel_1_deque, channel_2_deque, channel_3_deque, channel_4_deque, channel_5_deque, channel_6_deque
    global time_list, channel_1_list, channel_2_list, channel_3_list, channel_4_list, channel_5_list, channel_6_list
    try:
        channel_1 = np.int32(int.from_bytes(data[0:2], byteorder='little', signed=True))/100
        channel_2 = np.int32(int.from_bytes(data[6:9], byteorder='big', signed=True))
        channel_3 = np.int32(int.from_bytes(data[9:12], byteorder='big', signed=True))
        channel_4 = np.int32(int.from_bytes(data[12:15], byteorder='big', signed=True))
        channel_5 = np.int32(int.from_bytes(data[15:18], byteorder='big', signed=True))
        channel_6 = np.int32(int.from_bytes(data[18:21], byteorder='big', signed=True))

        print("Received packet: ", data)
        print("Channel 1 data: ", channel_1)
        
        i += 1/sample_rate
        time_deque.append(i)
        channel_1_deque.append(channel_1)
        channel_2_deque.append(channel_2)
        channel_3_deque.append(channel_3)
        channel_4_deque.append(channel_4)
        channel_5_deque.append(channel_5)
        channel_6_deque.append(channel_6)
        
        channel_1_list = np.append(channel_1_list, channel_1)
        channel_2_list = np.append(channel_2_list, channel_2)
        channel_3_list = np.append(channel_3_list, channel_3)
        channel_4_list = np.append(channel_4_list, channel_4)
        channel_5_list = np.append(channel_5_list, channel_5)
        channel_6_list = np.append(channel_6_list, channel_6)

        # Update plot less frequently
        if i % update_interval == 0:
            # Update the first three plots with raw data
            curves[0].setData(np.array(time_deque), np.array(channel_1_deque))
            curves[1].setData(np.array(time_deque), np.array(channel_2_deque))
            curves[2].setData(np.array(time_deque), np.array(channel_3_deque))
            curves[3].setData(np.array(time_deque), np.array(channel_4_deque))
            curves[4].setData(np.array(time_deque), np.array(channel_5_deque))
            curves[5].setData(np.array(time_deque), np.array(channel_6_deque))

            marker_curves[0].setData(np.array([time_deque[0], time_deque[-1]]), [20, 50])

            
            app.processEvents()

    except Exception as e:
        logging.error(f"Error in handle_rx: {e}")

# Function to stop the program
def stop_program():
    global stop_flag
    stop_flag = True
    print("\nStopping program...")

async def connect_and_notify(device_name):
    global stop_flag, time_0, time_end
    
    # Scan for BLE devices
    devices = await BleakScanner.discover(timeout=5)
    target_device = None
    
    # Find the target device by name, with NoneType check
    for device in devices:
        if device.name and device_name in device.name:
            target_device = device
            break

    if target_device:
        print(f"Found target device: {target_device.name}, {target_device.address}")
        
        async with BleakClient(target_device) as client:
            try:
                print(f"Connected to {target_device.name}")
                await client.start_notify(RX_CHAR_UUID, handle_rx)
                print(f"Listening for notifications on {RX_CHAR_UUID}...")
                
                time_0 = time.time()

                while not stop_flag:
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"Disconnected or error occurred: {e}")
                # Optionally add reconnection logic here
            
            # Stop notifications before exiting
            await client.stop_notify(RX_CHAR_UUID)
            time_end = time.time()
            print("Notifications stopped.")
    else:
        print(f"Device {device_name} not found.")

def generate_unique_filename(directory, filename):
    base, ext = os.path.splitext(filename)
    i = 1
    unique_filename = filename
    while os.path.exists(os.path.join(directory, unique_filename)):
        unique_filename = f"{base}_{i}{ext}"
        i += 1
    return unique_filename

def save_to_excel():
    global time_end, time_0
    if channel_1_list.any():
        # Ensure output folder exists
        if not os.path.exists(output_data_folder):
            os.makedirs(output_data_folder)

        # Generate unique filename if file already exists
        base_filename = filename_lineedit.text() + str(".xlsx")
        file_path = generate_unique_filename(output_data_folder, base_filename)
        # time_list = np.linspace(0, time_end - time_0, len(channel_1_list))
        time_list = np.linspace(0, time_deque[-2], len(channel_1_list))

        print(len(time_list))
        print(len(channel_1_list))

        # Save data to Excel file
        df1 = pd.DataFrame({
            "Time (seconds)": time_list,
            "Channel 1": channel_1_list,
            "Channel 2": channel_2_list,
            "Channel 3": channel_3_list,
            "Channel 4": channel_4_list,
            "Channel 5": channel_5_list,
            "Channel 6": channel_6_list
        })

        # Write both dataframes to separate sheets in Excel
        with pd.ExcelWriter(os.path.join(output_data_folder, file_path)) as writer:
            df1.to_excel(writer, sheet_name="Data", index=False)

        print(f"Data saved to {file_path}")
    else:
        print("No data available to save.")

save_button.clicked.connect(save_to_excel)
stop_button.clicked.connect(stop_program)

# Start the event loop and the BLE scan
device_name = "FSEMI4"
loop = QEventLoop(app)
asyncio.set_event_loop(loop)

with loop:
    loop.run_until_complete(connect_and_notify(device_name))
    app.exec()