import re
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication  # Adjust import based on your setup
import sys

# Read the log file and extract data
file_path = r"G:\Project\FSemi\Temp measurement\nrfLogging\my_log_20240930_122432.txt"

channel_0 = []
channel_1 = []
channel_2 = []
temp = []

# Regular expressions to match the data patterns
pattern_0 = r"\$\$\$\$Channel 0 final: ([\d\.]+)"
pattern_1 = r"\@\@\@\@Channel 1 final: ([\d\.]+)"
pattern_2 = r"____Channel 2 final: ([\d\.]+)"
pattern_temp = r"MAX30205 temp: (\d+)"

# Read the file and extract data
with open(file_path, 'r') as file:
    for line in file:
        match_0 = re.search(pattern_0, line)
        match_1 = re.search(pattern_1, line)
        match_2 = re.search(pattern_2, line)
        match_temp = re.search(pattern_temp, line)
        
        if match_0:
            channel_0.append(float(match_0.group(1)))
        if match_1:
            channel_1.append(float(match_1.group(1)))
        if match_2:
            channel_2.append(float(match_2.group(1)))
        if match_temp:
            temp.append(int(match_temp.group(1)) / 100.0)  # Temp is divided by 100 to convert

# Create a PyQtGraph application window
app = QApplication(sys.argv)

# Create plot window
win = pg.GraphicsLayoutWidget(show=True, title="Channel Data Plot")
win.resize(1000, 600)
win.setWindowTitle('PyQtGraph: Channel Data')

# Enable antialiasing for prettier plots
pg.setConfigOptions(antialias=True)

# Add a plot for each channel
p1 = win.addPlot(title="Channel 0 Data")
p1.plot(channel_0, pen='r')

win.nextRow()

p2 = win.addPlot(title="Channel 1 Data")
p2.plot(channel_1, pen='g')

win.nextRow()

p3 = win.addPlot(title="Channel 2 Data")
p3.plot(channel_2, pen='b')

win.nextRow()

p4 = win.addPlot(title="Temperature Data")
p4.plot(temp, pen='y')

# Start Qt event loop
sys.exit(app.exec_())
