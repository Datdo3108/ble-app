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
        port='COM4',
        baudrate=115200,
        timeout=1
    )
except serial.SerialException:
    print("Could not open serial port. Please check the connection.")
    sys.exit()

# Data storage and threading queue
max_points = 2000  # Points to display on plot
times = []
times = []
values = []
IDS_list = []
VDS_list = []
dac_value = 0
adc_0_value = 0
adc_1_value = 0
start_measuring = False
measure_once = True

data_queue = queue.Queue()
counter = 0
data_flag_1 = 0
data_flag_2 = 0
data_flag_3 = 0
animation_running = True
time_0 = time.time()

# PyQtGraph setup
app = QtWidgets.QApplication([])
win = QWidget()
layout = QVBoxLayout()
win.setLayout(layout)

# Create plot widget
plot_widget = pg.PlotWidget()
plot_widget.setTitle("Real-time Vg Data")
plot_widget.setLabel("left", "Vg (mV)")
plot_widget.setLabel("bottom", "Samples")
# plot_widget.setYRange(0, 2048)
curve = plot_widget.plot([], [], pen='g')
layout.addWidget(plot_widget)

plot_widget_2 = pg.PlotWidget()
plot_widget_2.setTitle("Real-time Ids Data")
plot_widget_2.setLabel("left", "Ids (uA)")
plot_widget_2.setLabel("bottom", "Samples")
# plot_widget_2.setYRange(0, 32768)
curve_2 = plot_widget_2.plot([], [], pen='g')
layout.addWidget(plot_widget_2)

plot_widget_5 = pg.PlotWidget()
plot_widget_5.setTitle("Real-time Vds Data")
plot_widget_5.setLabel("left", "Vds (mV)")
plot_widget_5.setLabel("bottom", "Samples")
# plot_widget_5.setYRange(0, 32768)
curve_5 = plot_widget_5.plot([], [], pen='g')
layout.addWidget(plot_widget_5)

plot_widget_3 = pg.PlotWidget()
plot_widget_3.setTitle("Ids vs Vg Data")
plot_widget_3.setLabel("left", "Ids (uA)")
plot_widget_3.setLabel("bottom", "Vg (mV)")
# plot_widget_3.setYRange(1200, 1500)
plot_widget_3.setYRange(0, 0.070)
plot_widget_3.setXRange(0, 1400)
curve_3 = plot_widget_3.plot([], [], pen='g')
marker_3 = plot_widget_3.plot([], [], pen='g', symbol='o', symbolSize=15, symbolBrush='b', symbolPen='b')
layout.addWidget(plot_widget_3)

plot_widget_4 = pg.PlotWidget()
plot_widget_4.setTitle("Vds vs ID Data")
plot_widget_4.setLabel("left", "Ids (uA)")
plot_widget_4.setLabel("bottom", "Vds (mV)")
plot_widget_4.setYRange(0, 400)
plot_widget_4.setXRange(0, 0.070)
curve_4 = plot_widget_4.plot([], [], pen='g')
marker_4 = plot_widget_4.plot([], [], pen='g', symbol='o', symbolSize=15, symbolBrush='r', symbolPen='r')
layout.addWidget(plot_widget_4)

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
    global data_flag_1
    global data_flag_2 
    global data_flag_3
    global dac_value
    global adc_0_value
    global adc_1_value
    global start_measuring
    global measure_once

    # Process all data in the queue
    while not data_queue.empty():
        data = data_queue.get()

        if measure_once:
            match_start = re.search(r'Start measuring', data)
            if match_start:
                start_measuring = True
                measure_once = False

        if start_measuring:
            # match_1 = re.search(r'DAC:\s*Channel:\s* 1+\s*Set value \(mV\):\s*(\d+\.\d+)', data)
            match_1 = re.search(r'ADC\s*Channel:\s* 2+\s*Read value:\s*[\d.]+\s*Voltage value:\s*(\d+)mV',data)
            if match_1:
                data_flag_1 = 1
                dac_value = float(match_1.group(1))
                print(f"DAC value: {dac_value}")
                values.append(dac_value)

            # Update IDS data
            match_2 = re.search(r'ADC\s*Channel:\s* 0+\s*Read value:\s*[\d.]+\s*Voltage value:\s*(\d+)mV',data)
            if match_2:
                data_flag_2 = 1
                # adc_0_value = float(int(match_2.group(1)) - 1280)/-10000        # Formula for ID, BBL
                adc_0_value = float(int(match_2.group(1)) - 1280)/-326        # Formula for ID, PEDOT
                print(f"--Channel 0: ADC value: {adc_0_value}")
                IDS_list.append(adc_0_value)

            # Update VDS data
            match_3 = re.search(r'ADC\s*Channel:\s* 1+\s*Read value:\s*[\d.]+\s*Voltage value:\s*(\d+)mV',data)
            if match_3:
                data_flag_3 = 1
                adc_1_value = float(int(match_3.group(1)))
                print(f"**Channel 1: ADC value: {adc_1_value}")
                VDS_list.append(adc_1_value)

            if (data_flag_1==1)&(data_flag_2==1)&(data_flag_3==1):
                times.append(counter)
                # values.append(dac_value)
                # IDS_list.append(adc_0_value)
                # VDS_list.append(adc_1_value)

                counter += 1
                data_flag_1 = 0
                data_flag_2 = 0
                data_flag_3 = 0

                display_times = times[-max_points:]
                display_values = values[-max_points:]
                display_IDS_values = IDS_list[-max_points:]
                display_VDS_values = VDS_list[-max_points:]

                curve.setData(display_times, display_values)
                curve_2.setData(display_times, display_IDS_values)
                curve_5.setData(display_times, display_VDS_values)
                curve_3.setData(display_values, display_IDS_values)
                curve_4.setData(display_VDS_values, display_IDS_values)
                marker_3.setData(display_values[-1:], display_IDS_values[-1:])
                marker_4.setData(display_VDS_values[-1:], display_IDS_values[-1:])

                plot_widget_3.setYRange(min(min(display_IDS_values), 0), max(max(display_IDS_values), 0.03))
                plot_widget_3.setXRange(min(min(display_values), 0), max(max(display_values), 200))
                plot_widget_4.setYRange(min(min(display_IDS_values), 0), max(max(display_IDS_values), 0.02))
                plot_widget_4.setXRange(min(min(display_VDS_values), 0), max(max(display_VDS_values), 200))


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
    print("DAC average value: ", np.mean(values))
    print("DAC standard deviation: ", np.std(values))
    print("IDS average value: ", np.mean(IDS_list))
    print("IDS standard deviation: ", np.std(IDS_list))

    # Save data to CSV
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Time', 'VG (mV)', 'IDS (mA)', 'VDS (mV)'])
        for t, v, o, s in zip(time_save_second, values, IDS_list, VDS_list):
            writer.writerow([t, v, o, s])

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

    # Create DataFrames for each sheet
    df_time = pd.DataFrame({
        'Time (s)': time_save_seconds
    })

    df_vg = pd.DataFrame({
        'VG (mV)': values
    })

    df_ids = pd.DataFrame({
        'IDS (mA)': IDS_list
    })

    df_vds = pd.DataFrame({
        'VDS (mV)': VDS_list
    })

    # Write to Excel with multiple sheets
    with pd.ExcelWriter(new_filename) as writer:
        df_time.to_excel(writer, sheet_name='Time (s)', index=False)
        df_vg.to_excel(writer, sheet_name='VG', index=False)
        df_ids.to_excel(writer, sheet_name='IDS', index=False)
        df_vds.to_excel(writer, sheet_name='VDS', index=False)

    print(f'Data saved to {new_filename}')

# Connect buttons
stop_button.clicked.connect(stop_and_save)
save_button.clicked.connect(save_to_excel)

# Start the update loop
timer = pg.QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.start(25)  # Set interval to 50 ms

# Start PyQt event loop
app.exec_()
