import sys
import os
import numpy as np
import asyncio
import time
import csv
import pyqtgraph as pg
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLineEdit,
    QTextEdit, QLabel, QComboBox, QCheckBox,
    QTabWidget,
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from bleak import BleakScanner, BleakClient
from dataclasses import dataclass

@dataclass
class ChannelConfig:
    start: int
    stop: int
    step: int
    fixed_value: int
    enabled: bool


# SERVICE_UUID = "00001234-0000-1000-8000-00805f9b34fb"
# CHAR_UUID    = "00009876-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "1234"
CHAR_UUID    = "9876"

# ================ SET DATA SEND IN A LOOP ================
# class LoopWorker(QThread):
#     update_value = pyqtSignal(int)  # optional, for GUI display

#     def __init__(self, ble_worker, start, stop, step, interval_ms):
#         super().__init__()
#         self.ble_worker = ble_worker
#         self.start = start
#         self.stop = stop
#         self.step = step
#         self.interval = interval_ms / 1000
#         self._running = True

#     def run(self):
#         val = self.start
#         while self._running and val <= self.stop:
#             # emit signal if you want to display
#             self.update_value.emit(val)
            
#             # send via BLE
#             asyncio.run_coroutine_threadsafe(
#                 self.ble_worker.write_data(bytes([val])),
#                 self.ble_worker.loop
#             )

#             val += self.step
#             time.sleep(self.interval)  # simple delay

#     def stop_run(self):
#         self._running = False


# ================= BLE THREAD =================
class BLEWorker(QThread):
    device_found = pyqtSignal(str)
    scan_failed = pyqtSignal()
    rx_data = pyqtSignal(bytes)

    def __init__(self, device_name):
        super().__init__()
        self.device_name = device_name
        self.client = None

    async def scan_and_connect(self):
        devices = await BleakScanner.discover(timeout=4.0)

        for d in devices:
            if d.name == self.device_name:
                self.client = BleakClient(d.address)
                await self.client.connect()

                await self.client.start_notify(
                    CHAR_UUID, self.notification_handler
                )

                self.device_found.emit(d.address)
                return

        self.scan_failed.emit()

    def notification_handler(self, sender, data):
        self.rx_data.emit(bytes(data))

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.scan_and_connect())
        self.loop.run_forever()

    # def run(self):
    #     asyncio.run(self.scan_and_connect())

    async def write_data(self, data: bytes):
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(CHAR_UUID, data)

    # async def send_loop_data(self, start, stop, step, interval_s):
    #     val = start
    #     self.loop_running = True
    #     while self.loop_running and val < stop:
    #         # await self.write_data(bytes([val]))
    #         await self.write_data(val.to_bytes(2, byteorder='big', signed=False))
    #         await asyncio.sleep(interval_s)
    #         val += step
    #         print(val)

    # async def send_loop_data(
    #         self,
    #         ch1_start, ch1_stop, ch1_step,
    #         ch2_start, ch2_stop, ch2_step,
    #         interval_s
    #     ):
    #     ch1 = ch1_start
    #     ch2 = ch2_start
    #     self.loop_running = True

    #     while self.loop_running and ch1 < ch1_stop and ch2 < ch2_stop:
    #         packet = (
    #             ch1.to_bytes(2, byteorder='big', signed=False) +
    #             ch2.to_bytes(2, byteorder='big', signed=False)
    #         )

    #         await self.write_data(packet)
    #         await asyncio.sleep(interval_s)

    #         ch1 += ch1_step
    #         ch2 += ch2_step

    #         print(f"CH1={ch1}, CH2={ch2}")

    # async def send_loop_data(
    #         self,
    #         ch1_start, ch1_stop, ch1_step,
    #         ch2_start, ch2_stop, ch2_step,
    #         interval_s
    #     ):
    #     ch1_loop = ch1_start
    #     ch2_loop = ch2_start
    #     self.loop_running = True

    #     while self.loop_running:
    #         ch1 = self.get_ch1_value(ch1_loop)
    #         ch2 = self.get_ch2_value(ch2_loop)

    #         packet = (
    #             ch1.to_bytes(2, 'big', signed=False) +
    #             ch2.to_bytes(2, 'big', signed=False)
    #         )

    #         await self.write_data(packet)
    #         await asyncio.sleep(interval_s)

    #         if self.ch1_enable.isChecked():
    #             ch1_loop += ch1_step
    #             if ch1_loop >= ch1_stop:
    #                 break

    #         if self.ch2_enable.isChecked():
    #             ch2_loop += ch2_step
    #             if ch2_loop >= ch2_stop:
    #                 break

    # async def disconnect_ble(self):
    #     if self.client and self.client.is_connected:
    #         await self.client.disconnect()

    async def disconnect(self):
        if self.client and self.client.is_connected:
            try:
                await self.client.stop_notify(CHAR_UUID)
                await self.client.disconnect()
            except Exception:
                pass

    async def send_loop_data(self, ch1: ChannelConfig, ch2: ChannelConfig, interval_s: float):
        ch1_loop = ch1.start
        ch2_loop = ch2.start

        self.loop_running = True

        while self.loop_running:
            # Decide values
            v1 = ch1_loop if ch1.enabled else ch1.fixed_value
            v2 = ch2_loop if ch2.enabled else ch2.fixed_value

            # Merge packet
            packet = (
                v1.to_bytes(2, 'big', signed=False) +
                v2.to_bytes(2, 'big', signed=False)
            )

            await self.write_data(packet)
            await asyncio.sleep(interval_s)

            # Advance enabled channels only
            if ch1.enabled:
                ch1_loop += ch1.step
                if ch1_loop >= ch1.stop:
                    break

            if ch2.enabled:
                ch2_loop += ch2.step
                if ch2_loop >= ch2.stop:
                    break



# ================= MAIN UI =================
class BLEApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SoftElectronicsGroup-OECT App")
        # self.setGeometry(200, 200, 520, 800)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(screen.width(), screen.height())

        # ---- Side Tab window, for display graph ----
        self.tabs = QTabWidget(self)
        self.tabs.setGeometry(490, 5, 1300, 970)  # adjust freely    500, 670, 1400, 300

        self.tab_main = QWidget()
        self.tabs.addTab(self.tab_main, "Main")

        self.tab_oect = QWidget()
        self.tabs.addTab(self.tab_oect, "OECT")

        # ---- Main Tab window ----
        # ---- Device name ----
        QLabel("Device Name:", self).setGeometry(20, 20, 100, 25)
        self.device_edit = QLineEdit(self)
        self.device_edit.setGeometry(130, 20, 200, 25)

        self.scan_btn = QPushButton("Scan", self)                   # Scan & connect
        self.scan_btn.setGeometry(350, 20, 120, 25)
        self.scan_btn.clicked.connect(self.start_scan)

        self.disconnect_btn = QPushButton("Disconnect", self)       # Disconnect
        self.disconnect_btn.setGeometry(350, 45, 120, 25)
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self.disconnect_device)

        # ---- TX data ----
        QLabel("TX Data:", self).setGeometry(20, 70, 100, 25)
        self.tx_edit = QLineEdit(self)
        self.tx_edit.setGeometry(130, 70, 200, 25)

        self.format_box = QComboBox(self)
        self.format_box.setGeometry(350, 70, 120, 25)
        self.format_box.addItems(["Hex", "Dec"])

        self.send_btn = QPushButton("Send", self)
        self.send_btn.setGeometry(350, 110, 120, 30)
        self.send_btn.clicked.connect(self.send_data)

        # ---- RX data ----
        QLabel("RX Data:", self).setGeometry(20, 160, 100, 25)
        self.rx_box = QTextEdit(self)
        self.rx_box.setGeometry(130, 160, 340, 160)
        self.rx_box.setReadOnly(True)

        self.ble_worker = None

        # ---- Loop Setup ----
        QLabel("Channel1 Start:", self).setGeometry(20, 350, 100, 25)
        self.start_edit_1 = QLineEdit(self)
        self.start_edit_1.setGeometry(130, 350, 100, 25)
        
        QLabel("Channel1 Stop:", self).setGeometry(20, 390, 100, 25)
        self.stop_edit_1 = QLineEdit(self)
        self.stop_edit_1.setGeometry(130, 390, 100, 25)
        
        QLabel("Channel1 Step:", self).setGeometry(20, 430, 100, 25)
        self.step_edit_1 = QLineEdit(self)
        self.step_edit_1.setGeometry(130, 430, 100, 25)

        QLabel("Channel2 Start:", self).setGeometry(250, 350, 100, 25)
        self.start_edit_2 = QLineEdit(self)
        self.start_edit_2.setGeometry(360, 350, 100, 25)
        
        QLabel("Channel2 Stop:", self).setGeometry(250, 390, 100, 25)
        self.stop_edit_2 = QLineEdit(self)
        self.stop_edit_2.setGeometry(360, 390, 100, 25)
        
        QLabel("Channel2 Step:", self).setGeometry(250, 430, 100, 25)
        self.step_edit_2 = QLineEdit(self)
        self.step_edit_2.setGeometry(360, 430, 100, 25)
        
        QLabel("Interval (ms):", self).setGeometry(20, 470, 100, 25)
        self.interval_edit = QLineEdit(self)
        self.interval_edit.setGeometry(130, 470, 100, 25)

        self.start_loop_btn = QPushButton("Start Loop", self)
        self.start_loop_btn.setGeometry(20, 550, 120, 25)
        self.start_loop_btn.clicked.connect(self.start_loop)

        self.start_loop_btn = QPushButton("Stop Loop", self)
        self.start_loop_btn.setGeometry(20, 590, 120, 25)
        self.start_loop_btn.clicked.connect(self.start_loop)

        QLabel("CH1 constant:", self).setGeometry(20, 510, 100, 25)
        self.ch1_enable = QCheckBox("Sweep CH1", self)
        self.ch1_enable.setGeometry(20, 290, 100, 100)
        self.ch1_value_edit = QLineEdit("0", self)               # Constant (default value is "0")
        self.ch1_value_edit.setGeometry(130, 510, 100, 25)

        QLabel("CH2 constant:", self).setGeometry(250, 510, 100, 25)
        self.ch2_enable = QCheckBox("Sweep CH2", self)
        self.ch2_enable.setGeometry(250, 290, 100, 100)
        self.ch2_value_edit = QLineEdit("0", self)          # Constant (default value is "0")
        self.ch2_value_edit.setGeometry(360, 510, 100, 25)

        self.ch1_enable.stateChanged.connect(self.on_ch1_enable_changed)
        self.ch2_enable.stateChanged.connect(self.on_ch2_enable_changed)

        # Initial state
        self.on_ch1_enable_changed(self.ch1_enable.checkState())
        self.on_ch2_enable_changed(self.ch2_enable.checkState())

        # ---- pyqtgraph ----
        self.max_points = 2000

        self.time_buffer = deque(maxlen=self.max_points)
        self.data_buffer_1 = deque(maxlen=self.max_points)
        self.data_buffer_2 = deque(maxlen=self.max_points)
        self.data_buffer_3 = deque(maxlen=self.max_points)

        self.t0 = time.perf_counter()

        # ---- Axis label style
        label_style_main_tab = {
                'color': "#FFFFFF",
                'font-size': '11pt',
                'font-weight': 'bold'
            }
        # ---- Channel 1 graph ----
        self.plot_widget_1 = pg.PlotWidget(self.tab_main)
        self.plot_widget_1.setGeometry(0, 0, 1400, 300)
        self.plot_widget_1.setLabel('left', 'Channel 1', **label_style_main_tab)
        self.plot_widget_1.setLabel('bottom', 'Time', units='s', **label_style_main_tab)
        self.plot_widget_1.showGrid(x=True, y=True)

        self.plot_curve_1 = self.plot_widget_1.plot(pen='y')

        # ---- Channel 2 graph ----
        self.plot_widget_2 = pg.PlotWidget(self.tab_main)
        self.plot_widget_2.setGeometry(0, 320, 1400, 300)
        self.plot_widget_2.setLabel('left', 'Channel 2 (DAC 2)', **label_style_main_tab)
        self.plot_widget_2.setLabel('bottom', 'Time', units='s', **label_style_main_tab)
        self.plot_widget_2.showGrid(x=True, y=True)

        self.plot_curve_2 = self.plot_widget_2.plot(pen='y')

        # ---- Channel 3 graph ----
        self.plot_widget_3 = pg.PlotWidget(self.tab_main)
        self.plot_widget_3.setGeometry(0, 640, 1400, 300)
        self.plot_widget_3.setLabel('left', 'Channel 3 (DAC 1)', **label_style_main_tab)
        self.plot_widget_3.setLabel('bottom', 'Time', units='s', **label_style_main_tab)
        self.plot_widget_3.showGrid(x=True, y=True)

        self.plot_curve_3 = self.plot_widget_3.plot(pen='y')

        # ---- Axis label style
        label_style_oect_tab = {
                'color': '#000000',
                'font-size': '12pt',
                'font-weight': 'bold'
            }
        # ---- ID vs VG graph ----
        self.plot_widget_4 = pg.PlotWidget(self.tab_oect)
        self.plot_widget_4.setGeometry(0, 0, 1400, 300)
        self.plot_widget_4.setLabel('left', 'ID', **label_style_oect_tab)
        self.plot_widget_4.setLabel('bottom', 'VG', units='mV', **label_style_oect_tab)
        self.plot_widget_4.showGrid(x=True, y=True)
        self.plot_widget_4.setBackground(background=(255, 255, 255))

        self.plot_curve_4 = self.plot_widget_4.plot(pen='r')

        # ---- ID vs VD graph ----
        self.plot_widget_5 = pg.PlotWidget(self.tab_oect)
        self.plot_widget_5.setGeometry(0, 320, 1400, 300)
        self.plot_widget_5.setLabel('left', 'ID', **label_style_oect_tab)
        self.plot_widget_5.setLabel('bottom', 'VD', units='mV', **label_style_oect_tab)
        self.plot_widget_5.showGrid(x=True, y=True)
        self.plot_widget_5.setBackground(background=(255, 255, 255))

        self.plot_curve_5 = self.plot_widget_5.plot(pen='r')

        # ---- Reset graph ----
        self.reset_graph_btn = QPushButton("Reset Graph", self)
        self.reset_graph_btn.setGeometry(20, 110, 120, 30)  # adjust freely
        self.reset_graph_btn.clicked.connect(self.reset_graph)

        # ---- Saving to .csv ----
        self.csv_time = []
        self.csv_ch1 = []
        self.csv_ch2 = []
        self.csv_ch3 = []

        QLabel("CSV filename:", self).setGeometry(20, 640, 100, 30)

        self.csv_name_edit = QLineEdit(self)
        self.csv_name_edit.setGeometry(130, 640, 200, 30)
        self.csv_name_edit.setPlaceholderText("enter filename here")

        self.save_csv_btn = QPushButton("Save CSV", self)
        self.save_csv_btn.setGeometry(350, 640, 120, 30)
        self.save_csv_btn.clicked.connect(self.save_csv)

    def reset_graph(self):
        # reset time reference
        self.t0 = time.perf_counter()

        # clear buffers
        self.time_buffer.clear()
        self.data_buffer_1.clear()
        self.data_buffer_2.clear()
        self.data_buffer_3.clear()

        # clear plot
        self.plot_curve_1.setData([], [])
        self.plot_curve_2.setData([], [])
        self.plot_curve_3.setData([], [])

        # reset .csv data
        self.csv_time.clear()
        self.csv_ch1.clear()
        self.csv_ch2.clear()
        self.csv_ch3.clear()

    def get_unique_filename(self, base_name):
        filename = f"{base_name}.csv"
        counter = 1

        while os.path.exists(filename):
            filename = f"{base_name}_{counter}.csv"
            counter += 1

        return filename
    
    def save_csv(self):
        if not self.csv_time:
            self.rx_box.append("No data to save.")
            return

        base_name = self.csv_name_edit.text().strip()
        if not base_name:
            base_name = "data"

        filename = self.get_unique_filename(base_name)
        path = os.path.abspath(filename)

        with open(filename, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Time (s)", "Channel 1 (mV)", "Channel 2 (mV)", "Channel 3 (mV)"])

            for t, c1, c2, c3 in zip(self.csv_time, self.csv_ch1, self.csv_ch2, self.csv_ch3):
                writer.writerow([t, c1, c2, c3])

        self.rx_box.append(f"Data saved to {path}")

    # ---- Set channel value from textbox
    def get_ch1_config(self) -> ChannelConfig:
        return ChannelConfig(
            start=int(self.start_edit_1.text()),
            stop=int(self.stop_edit_1.text()),
            step=int(self.step_edit_1.text()),
            fixed_value=int(self.ch1_value_edit.text()),
            enabled=self.ch1_enable.isChecked()
        )
    
    def get_ch2_config(self) -> ChannelConfig:
        return ChannelConfig(
            start=int(self.start_edit_2.text()),
            stop=int(self.stop_edit_2.text()),
            step=int(self.step_edit_2.text()),
            fixed_value=int(self.ch2_value_edit.text()),
            enabled=self.ch2_enable.isChecked()
        )

    # ---- Check enable chanel ----
    def on_ch1_enable_changed(self, state):
        enabled = state == Qt.Checked
        self.ch1_value_edit.setEnabled(not enabled)
        self.start_edit_1.setEnabled(enabled)
        self.stop_edit_1.setEnabled(enabled)
        self.step_edit_1.setEnabled(enabled)

    def on_ch2_enable_changed(self, state):
        enabled = state == Qt.Checked
        self.ch2_value_edit.setEnabled(not enabled)
        self.start_edit_2.setEnabled(enabled)
        self.stop_edit_2.setEnabled(enabled)
        self.step_edit_2.setEnabled(enabled)

    def get_ch1_value(self, loop_val):
        if self.ch1_enable.isChecked():
            return loop_val
        return int(self.ch1_value_edit.text())

    def get_ch2_value(self, loop_val):
        if self.ch2_enable.isChecked():
            return loop_val
        return int(self.ch2_value_edit.text())


    # ---------- Scan ----------
    def start_scan(self):
        name = self.device_edit.text().strip()
        if not name:
            return

        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Scanning...")

        self.ble_worker = BLEWorker(name)
        self.ble_worker.device_found.connect(self.on_connected)
        self.ble_worker.scan_failed.connect(self.on_scan_failed)
        self.ble_worker.rx_data.connect(self.on_rx_data)
        self.ble_worker.start()

    def on_connected(self, addr):
        self.scan_btn.setText("Connected")
        self.scan_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.reset_graph()

    def disconnect_device(self):
        if not self.ble_worker:
            return

        # ask BLE thread to disconnect safely
        asyncio.run_coroutine_threadsafe(
            self.ble_worker.disconnect(),
            self.ble_worker.loop
        )

        # ---- UI reset ----
        self.scan_btn.setText("Scan")
        self.scan_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)


    def on_scan_failed(self):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan")

    # ---------- Send ----------
    def send_data(self):
        if not self.ble_worker:
            return

        text = self.tx_edit.text().strip()
        fmt = self.format_box.currentText()

        try:
            if fmt == "Hex":
                data = bytes.fromhex(text)
            else:
                data = bytes([int(text)])
        except ValueError:
            return

        # asyncio.create_task(self.ble_worker.write_data(data))
        asyncio.run_coroutine_threadsafe(
            self.ble_worker.write_data(data),
            self.ble_worker.loop
        )


    # ---------- Receive ----------
    def on_rx_data(self, data: bytes):
        hex_str = " ".join(f"{b:02X}" for b in data)
        self.rx_box.append(hex_str)
        
        # ---- pyqtgraph Handler ----
        # ---- decode ----
        channel_1 = np.int32(int.from_bytes(data[0:2], byteorder='big', signed=True))
        channel_2 = np.int32(int.from_bytes(data[2:4], byteorder='big', signed=True))
        channel_3 = np.int32(int.from_bytes(data[4:6], byteorder='big', signed=True))

        # ---- time ----
        t = time.perf_counter() - self.t0

        # ---- push into deque ----
        self.time_buffer.append(t)
        self.data_buffer_1.append(channel_1)
        self.data_buffer_2.append(channel_2)
        self.data_buffer_3.append(channel_3)

        # ---- update plot ----
        # ---- main tab
        self.plot_curve_1.setData(list(self.time_buffer), list(self.data_buffer_1))     # time - ID
        self.plot_curve_2.setData(list(self.time_buffer), list(self.data_buffer_2))     # time - VD
        self.plot_curve_3.setData(list(self.time_buffer), list(self.data_buffer_3))     # time - VG

        # ---- oect tab
        self.plot_curve_4.setData(list(self.data_buffer_3), list(self.data_buffer_1))   # VG - ID
        self.plot_curve_5.setData(list(self.data_buffer_2), list(self.data_buffer_1))   # VD - ID

        # ---- optional text display ----
        self.rx_box.append(f"{t:.3f}s : {channel_1}")
        self.rx_box.append(f"{t:.3f}s : {channel_2}")
        self.rx_box.append(f"{t:.3f}s : {channel_3}")

        # ---- save to .csv array ----
        self.csv_time.append(t)
        self.csv_ch1.append(channel_1)
        self.csv_ch2.append(channel_2)
        self.csv_ch3.append(channel_3)

    # ---------- Set data in a loop ----------
    def start_loop(self):
        # start_1 = int(self.start_edit_1.text())
        # stop_1 = int(self.stop_edit_1.text())
        # step_1 = int(self.step_edit_1.text())

        # start_2 = int(self.start_edit_2.text())
        # stop_2 = int(self.stop_edit_2.text())
        # step_2 = int(self.step_edit_2.text())

        interval_s = int(self.interval_edit.text()) / 1000

        ch1_cfg = self.get_ch1_config()
        ch2_cfg = self.get_ch2_config()

        # self.loop_worker = LoopWorker(self.ble_worker, start, stop, step, interval)
        # # self.loop_worker.update_value.connect(self.show_loop_value)  # optional
        # self.loop_worker.run()
        asyncio.run_coroutine_threadsafe(
        # self.ble_worker.send_loop_data(start_1, stop_1, step_1, start_2, stop_2, step_2, interval),
        self.ble_worker.send_loop_data(ch1_cfg, ch2_cfg, interval_s),
        self.ble_worker.loop
    )

    def stop_loop(self):
        self.ble_worker.loop_running = False


# ================= MAIN =================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = BLEApp()
    win.show()
    sys.exit(app.exec_())
