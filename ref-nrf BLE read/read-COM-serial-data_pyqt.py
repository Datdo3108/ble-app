import serial
import pyqtgraph as pg
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QPushButton, QLineEdit, QVBoxLayout, QLabel, QWidget
import re
import threading
import queue
from datetime import datetime
import csv
import pandas as pd
import numpy as np
import time
import sys
import os

# Configure serial port
try:
    ser = serial.Serial(
        port='COM22',
        baudrate=115200,
        timeout=1
    )
except serial.SerialException:
    print("Could not open serial port. Please check the connection.")
    sys.exit()

# Data storage and threading queue
max_points = 2000  # Points to display on plot
times = []
values = []
offset_list = []
data_queue = queue.Queue()
counter = 0
animation_running = True
time_0 = time.time()

# PyQtGraph setup
app = QtWidgets.QApplication([])
win = QWidget()
layout = QVBoxLayout()
win.setLayout(layout)

# Create plot widget
plot_widget = pg.PlotWidget()
plot_widget.setTitle("Real-time ADC Data")
plot_widget.setLabel("left", "ADC Value")
plot_widget.setLabel("bottom", "Samples")
# plot_widget.setYRange(0, 2048)
curve = plot_widget.plot([], [], pen='g')
layout.addWidget(plot_widget)

plot_widget_2 = pg.PlotWidget()
plot_widget_2.setTitle("Real-time ADC Data")
plot_widget_2.setLabel("left", "ADC Value")
plot_widget_2.setLabel("bottom", "Samples")
plot_widget_2.setYRange(0, 32768)
curve_2 = plot_widget_2.plot([], [], pen='g')
layout.addWidget(plot_widget_2)

# Filename input
filename_label = QLabel("Filename:")
filename_input = QLineEdit(datetime.now().strftime("%Y%m%d_%H%M%S"))
layout.addWidget(filename_label)
layout.addWidget(filename_input)

# Stop & Save button
stop_button = QPushButton("Stop & Save")
layout.addWidget(stop_button)

# Save as Excel button
save_button = QPushButton("Save Excel")
layout.addWidget(save_button)

win.setWindowTitle("Real-time ADC Plotter")
win.resize(800, 600)
win.show()

# Serial reading in separate thread
def read_serial():
    while animation_running:
        if ser.in_waiting:
            data = ser.readline().decode().strip()
            data_queue.put(data)  # Put raw data in the queue

# Start the serial reading thread
threading.Thread(target=read_serial, daemon=True).start()

def update_plot():
    """Update the plot with data from the queue."""
    global counter

    # Process all data in the queue
    while not data_queue.empty():
        data = data_queue.get()
        match = re.search(r'ADC:\s*(\d+\.\d+)\s*\t\s*(\d+\.\d+)', data)
        if match:
            adc_value = float(match.group(1))
            offset_value = float(match.group(2))
            print(f"ADC: {adc_value}, Offset: {offset_value}")
            
            # Append new data
            times.append(counter)
            values.append(adc_value)
            offset_list.append(offset_value)
            
            # Update display data
            display_times = times[-max_points:]
            display_values = values[-max_points:]
            display_offset_values = offset_list[-max_points:]
            
            # Set curve data
            curve.setData(display_times, display_values)
            curve_2.setData(display_times, display_offset_values)
            
            # Adjust y-axis if necessary
            # if adc_value > plot_widget.getAxis("left").range[1]:
            #     plot_widget.setYRange(0, adc_value * 1.2)

            # if offset_value > plot_widget_2.getAxis("left").range[1]:
            #     plot_widget_2.setYRange(0, offset_value * 1.2)
            
            counter += 1


def stop_and_save():
    """Stop acquisition and save data to CSV."""
    global animation_running
    animation_running = False

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'adc_data_{timestamp}.csv'

    time_end = time.time() - time_0
    time_save_second = np.linspace(0, time_end, len(times))

    print(time_end)
    # print(time_save_second)
    print("Sample rate: ", len(times)/time_end)
    print("NTC average value: ", np.mean(values))
    print("NTC standard deviation: ", np.std(values))
    print("Offset average value: ", np.mean(offset_list))
    print("Offset standard deviation: ", np.std(offset_list))

    # Save data to CSV
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Time', 'ADC_Value', 'Offset'])
        for t, v, o in zip(time_save_second, values, offset_list):
            writer.writerow([t, v, o])

    print(f"Data saved to {filename}")
    if ser.is_open:
        ser.close()

def save_to_excel():
    """Save data to Excel file."""
    base_filename = filename_input.text().strip() + '.xlsx'
    
    # Generate filename to avoid overwriting
    counter = 1
    new_filename = base_filename
    while os.path.exists(new_filename):
        base, extension = os.path.splitext(base_filename)
        new_filename = f"{base}_{counter}{extension}"
        counter += 1

    # Calculate elapsed time and create DataFrame
    time_end = time.time() - time_0
    time_save_seconds = np.linspace(0, time_end, len(times))
    df = pd.DataFrame({
        'Time': time_save_seconds,
        'ADC_Value': values,
        'Offset': offset_list
    })
    
    # Save to Excel
    df.to_excel(new_filename, index=False)
    print(f'Data saved to {new_filename}')

# Connect buttons
stop_button.clicked.connect(stop_and_save)
save_button.clicked.connect(save_to_excel)

# Start the update loop
timer = pg.QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.start(50)  # Set interval to 50 ms

# Start PyQt event loop
app.exec_()
