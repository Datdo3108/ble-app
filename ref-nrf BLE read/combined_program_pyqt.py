import pandas as pd
import numpy as np
import os
import subprocess
import time
import keyboard
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLineEdit
from PyQt5.QtCore import QTimer
import pyqtgraph as pg

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
                        channel_0 = np.append(channel_0, value)
                        current_time = time.time() - start_time
                        time_series = np.append(time_series, current_time)
                    elif line.startswith("00> <info> app: @@@@Channel 1 final:"):
                        value = float(line[36:].strip())
                        channel_1 = np.append(channel_1, value)
                    elif line.startswith("00> <info> app: ____Channel 2 final:"):
                        value = float(line[36:].strip())
                        channel_2 = np.append(channel_2, value)
                    elif line.startswith("00> <info> app: MAX30205 temp:"):
                        value = float(line[30:].strip()) / 100
                        channel_3 = np.append(channel_3, value)
                        
        time.sleep(0.1)  # Short delay to prevent excessive CPU usage

def generate_filename(base_filename):
    counter = 1
    base, extension = os.path.splitext(base_filename)
    new_filename = base_filename
    while os.path.exists(new_filename):
        new_filename = f"{base}_{counter}{extension}"
        counter += 1
    return new_filename

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Real-time Data Plot")
        self.setGeometry(100, 100, 1000, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)

        self.plot = self.plot_widget.plot(pen='y')
        self.plot_widget.setLabel('left', 'Channel Value')
        self.plot_widget.setLabel('bottom', 'Time (seconds)')
        self.plot_widget.setTitle('Channel Data Over Time')

        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Enter filename for Excel")
        layout.addWidget(self.filename_input)

        self.save_button = QPushButton("Save to Excel")
        self.save_button.clicked.connect(self.save_to_excel)
        layout.addWidget(self.save_button)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(100)  # Update every 100 ms

    def update_plot(self):
        self.plot.setData(time_series, channel_0)

    def save_to_excel(self):
        base_path = self.filename_input.text().strip() + '.xlsx'
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

if __name__ == '__main__':
    jlink_process = launch_jlink_rtt_viewer()

    # Start the data reading thread
    read_thread = threading.Thread(target=read_data_from_file)
    read_thread.start()

    app = QApplication([])
    main_window = MainWindow()
    main_window.show()
    app.exec_()

    # Clean up
    stop_reading = True
    read_thread.join()
    jlink_process.terminate()