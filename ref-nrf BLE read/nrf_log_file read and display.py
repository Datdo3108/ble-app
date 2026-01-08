import ctypes
import sys

# Try to set DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 2 = PROCESS_PER_MONITOR_DPI_AWARE
except AttributeError:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass  # Fail silently if it doesn't work

import subprocess
import time
import keyboard
import re
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from PyQt5.QtCore import QTimer
import pandas as pd
import os

class LoggerAndGrapher(QWidget):
    def __init__(self):
        super().__init__()
        self.process = None
        self.start_time = None
        self.channel_0 = []
        self.channel_1 = []
        self.channel_2 = []
        self.temp = []
        self.output_folder = r"G:\Project\FSemi\Temp measurement\nrfLogging"
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.start_button = QPushButton('Start Logging')
        self.start_button.clicked.connect(self.start_logging)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton('Stop Logging')
        self.stop_button.clicked.connect(self.stop_logging)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.setLayout(layout)
        self.setGeometry(300, 300, 300, 200)
        self.setWindowTitle('NRF Logger and Grapher')
        self.show()

    def start_logging(self):
        jlink_rtt_viewer_path = "C:/Program Files/SEGGER/JLink_V798i/JLinkRTTViewer.exe"
        self.process = subprocess.Popen([jlink_rtt_viewer_path])
        self.start_time = time.time()
        
        QTimer.singleShot(1000, self.connect_and_start_logging)
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def connect_and_start_logging(self):
        keyboard.send("enter")
        QTimer.singleShot(500, self.start_file_logging)

    def start_file_logging(self):
        keyboard.send("f5")
        QTimer.singleShot(500, self.save_log_file)

    def save_log_file(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.file_name = f"my_log_{timestamp}.txt"
        self.file_path = os.path.join(self.output_folder, self.file_name)
        keyboard.write(self.file_path)
        keyboard.send("enter")

    def stop_logging(self):
        if self.process:
            self.process.terminate()
            self.process = None
        self.stop_button.setEnabled(False)
        self.parse_log_file()
        self.display_graphs()
        self.save_to_excel()

    def parse_log_file(self):
        pattern_0 = r"\$\$\$\$Channel 0 final: ([\d\.]+)"
        pattern_1 = r"\@\@\@\@Channel 1 final: ([\d\.]+)"
        pattern_2 = r"____Channel 2 final: ([\d\.]+)"
        pattern_temp = r"MAX30205 temp: (\d+)"

        with open(self.file_path, 'r') as file:
            for line in file:
                match_0 = re.search(pattern_0, line)
                match_1 = re.search(pattern_1, line)
                match_2 = re.search(pattern_2, line)
                match_temp = re.search(pattern_temp, line)
                
                if match_0:
                    self.channel_0.append(float(match_0.group(1)))
                    print("Channel: ", float(match_0.group(1)))
                if match_1:
                    self.channel_1.append(float(match_1.group(1)))
                if match_2:
                    self.channel_2.append(float(match_2.group(1)))
                if match_temp:
                    self.temp.append(int(match_temp.group(1)) / 100.0)

    def display_graphs(self):
        win = pg.GraphicsLayoutWidget(show=True, title="Channel Data Plot")
        win.resize(1000, 600)
        win.setWindowTitle('PyQtGraph: Channel Data')

        pg.setConfigOptions(antialias=True)

        p1 = win.addPlot(title="Channel 0 Data")
        p1.plot(self.channel_0, pen='r')

        win.nextRow()

        p2 = win.addPlot(title="Channel 1 Data")
        p2.plot(self.channel_1, pen='g')

        win.nextRow()

        p3 = win.addPlot(title="Channel 2 Data")
        p3.plot(self.channel_2, pen='b')

        win.nextRow()

        p4 = win.addPlot(title="Temperature Data")
        p4.plot(self.temp, pen='y')

    def save_to_excel(self):
        df1 = pd.DataFrame({
            'Channel 0': self.channel_0,
            # 'Channel 1': self.channel_1,
            # 'Channel 2': self.channel_2,
        })

        df2 = pd.DataFrame({
            'Temperature': self.temp
        })

        with pd.ExcelWriter(os.path.join(self.output_folder, self.file_name.replace('.txt', '.xlsx'))) as writer:
            df1.to_excel(writer, sheet_name="FSEMI1 Data", index=False)
            df2.to_excel(writer, sheet_name="FSEMI2 Data", index=False)

        # excel_file = os.path.join(self.output_folder, self.file_name.replace('.txt', '.xlsx'))
        # df.to_excel(excel_file, index=False)
        # print(f"Data saved to {excel_file}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = LoggerAndGrapher()
    sys.exit(app.exec_())