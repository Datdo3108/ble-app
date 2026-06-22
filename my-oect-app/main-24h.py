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
    QTabWidget, QStackedWidget,
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from bleak import BleakScanner, BleakClient
from dataclasses import dataclass

@dataclass
class ChannelConfig:
    loop: int
    start: int
    stop: int
    step: int
    fixed_value: int
    enabled: bool
    direction: bool
    period: int
    # sine_high: int
    # sine_low: int
    # sine_period: int
    # pulse_high: int
    # pulse_low: int
    # pulse_period: int


# SERVICE_UUID = "00001234-0000-1000-8000-00805f9b34fb"
# CHAR_UUID    = "00009876-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "1234"
CHAR_UUID    = "9876"
CMD_CHAR_UUID = "9000"

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

    loop_running = False

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

    async def write_cmd_data(self, data: bytes):
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(CMD_CHAR_UUID, data)

    async def disconnect(self):
        if self.client and self.client.is_connected:
            try:
                await self.client.stop_notify(CHAR_UUID)
                await self.client.disconnect()
            except Exception:
                pass

    async def send_loop_data(self, ch1: ChannelConfig, ch2: ChannelConfig, waveform_index: int, interval_s: float, num_cycles: int):
        try:
            for cycle in range(num_cycles):
                print(f"Cycle {cycle+1}/{num_cycles}")

                if waveform_index == 0:
                    ch1.loop = ch1.start
                    ch2.loop = ch2.start

                if waveform_index == 1:
                    ch1.loop = int((ch1.start + ch1.stop)/2)
                    ch2.loop = int((ch2.start + ch2.stop)/2)

                backward_sweep = 0

                ch1_period_counter = 0
                ch1_period_steps = int((ch1.period/1000) / interval_s)
                ch2_period_counter = 0
                ch2_period_steps = int((ch2.period/1000) / interval_s)

                while True:
                    # Decide values
                    ch1_loop_send_value = ch1.loop if ch1.loop >= 0 else ch1.loop + 65536
                    ch2_loop_send_value = ch2.loop if ch2.loop >= 0 else ch2.loop + 65536
                    ch1_send_fixed_value = ch1.fixed_value if ch1.fixed_value >= 0 else ch1.fixed_value + 65536
                    ch2_send_fixed_value = ch2.fixed_value if ch2.fixed_value >= 0 else ch2.fixed_value + 65536
                    
                    v1 = ch1_loop_send_value if ch1.enabled else ch1_send_fixed_value
                    v2 = ch2_loop_send_value if ch2.enabled else ch2_send_fixed_value

                    # Merge packet
                    packet = (
                        v1.to_bytes(2, 'big', signed=False) +
                        v2.to_bytes(2, 'big', signed=False)
                    )

                    await self.write_data(packet)
                    await asyncio.sleep(interval_s)

                    if ch1.enabled:
                        '''
                        Triangle waveform
                        '''
                        if waveform_index == 0:    
                            if ch1.start <= ch1.stop:
                                if backward_sweep == 0:
                                    ch1.loop += ch1.step
                                    if ch1.loop > ch1.stop:     # Should not let equality (=)
                                        if ch1.direction:
                                            backward_sweep = 1
                                        else:
                                            break
                                if backward_sweep == 1:
                                    ch1.loop -= ch1.step
                                    if ch1.loop < ch1.start:
                                        break

                            elif ch1.start >= ch1.stop:
                                if backward_sweep == 0:
                                    ch1.loop -= ch1.step
                                    if ch1.loop < ch1.stop:
                                        if ch1.direction:
                                            backward_sweep = 1
                                        else:
                                            break
                                if backward_sweep == 1:
                                    ch1.loop += ch1.step
                                    if ch1.loop > ch1.start:
                                        break
                        '''
                        Sine waveform
                        '''
                        if waveform_index == 1:
                            if ch1_period_counter <= ch1_period_steps:
                                ch1.loop = int((ch1.start + ch1.stop)/2 + (ch1.start - ch1.stop) * np.sin(ch1_period_counter*2*np.pi/ch1_period_steps)/2)
                                ch1_period_counter += 1
                            else: 
                                break

                        '''
                        Pulse waveform
                        '''
                        if waveform_index == 2:
                            if ch1_period_counter <= ch1_period_steps:
                                if ch1_period_counter < ch1_period_steps*ch1.step/100:
                                    ch1.loop = ch1.stop
                                else:
                                    ch1.loop = ch1.start
                                ch1_period_counter += 1
                            else: 
                                break

                    if ch2.enabled:
                        '''
                        Triangle waveform
                        '''
                        if waveform_index == 0:  
                            if ch2.start <= ch2.stop:
                                if backward_sweep == 0:
                                    ch2.loop += ch2.step
                                    if ch2.loop > ch2.stop:
                                        if ch2.direction:
                                            backward_sweep = 1
                                        else:
                                            break
                                if backward_sweep == 1:
                                    ch2.loop -= ch2.step
                                    if ch2.loop < ch2.start:
                                        break

                            elif ch2.start >= ch2.stop:
                                if backward_sweep == 0:
                                    ch2.loop -= ch2.step
                                    if ch2.loop < ch2.stop:     # Should not let equality (=)
                                        if ch2.direction:
                                            backward_sweep = 1
                                        else:
                                            break
                                if backward_sweep == 1:
                                    ch2.loop += ch2.step
                                    if ch2.loop > ch2.start:
                                        break
                        '''
                        Sine waveform
                        '''
                        if waveform_index == 1:
                            if ch2_period_counter <= ch2_period_steps:
                                ch2.loop = int((ch2.start + ch2.stop)/2 + (ch2.start - ch2.stop) * np.sin(ch2_period_counter*2*np.pi/ch2_period_steps)/2)
                                ch2_period_counter += 1
                            else: 
                                break
                        '''
                        Pulse waveform
                        '''
                        if waveform_index == 2:
                            if ch2_period_counter <= ch2_period_steps:
                                if ch2_period_counter < ch2_period_steps*ch2.step/100:
                                    ch2.loop = ch2.stop
                                else:
                                    ch2.loop = ch2.start
                                ch2_period_counter += 1
                            else: 
                                break

        except asyncio.CancelledError:
            print("Loop task cancelled")
            raise

        # ---- End ----

    # async def send_triangle_data(self, ch1: ChannelConfig, ch2: ChannelConfig, interval_s: float):
    #     try:
    #         ch1.loop = ch1.start
    #         ch2.loop = ch2.start

    #         backward_sweep = 0

    #         # t0_loop = time.perf_counter()

    #         while True:
    #             # Decide values
    #             ch1_loop_send_value = ch1.loop if ch1.loop >= 0 else ch1.loop + 65536
    #             ch2_loop_send_value = ch2.loop if ch2.loop >= 0 else ch2.loop + 65536
    #             v1 = ch1_loop_send_value if ch1.enabled else ch1.fixed_value
    #             v2 = ch2_loop_send_value if ch2.enabled else ch2.fixed_value

    #             # Merge packet
    #             packet = (
    #                 v1.to_bytes(2, 'big', signed=False) +
    #                 v2.to_bytes(2, 'big', signed=False)
    #             )

    #             await self.write_data(packet)
    #             await asyncio.sleep(interval_s)

    #             # Advance enabled channels only
    #             if ch1.enabled:
    #                 if ch1.start <= ch1.stop:
    #                     if backward_sweep == 0:
    #                         ch1.loop += ch1.step
    #                         if ch1.loop > ch1.stop:     # Should not let equality (=)
    #                             if ch1.direction:
    #                                 backward_sweep = 1
    #                             else:
    #                                 break
    #                     if backward_sweep == 1:
    #                         ch1.loop -= ch1.step
    #                         if ch1.loop < ch1.start:
    #                             break

    #                 elif ch1.start >= ch1.stop:
    #                     if backward_sweep == 0:
    #                         ch1.loop -= ch1.step
    #                         if ch1.loop < ch1.stop:
    #                             if ch1.direction:
    #                                 backward_sweep = 1
    #                             else:
    #                                 break
    #                     if backward_sweep == 1:
    #                         ch1.loop += ch1.step
    #                         if ch1.loop > ch1.start:
    #                             break

    #             if ch2.enabled:
    #                 if ch2.start <= ch2.stop:
    #                     if backward_sweep == 0:
    #                         ch2.loop += ch2.step
    #                         if ch2.loop > ch2.stop:
    #                             if ch2.direction:
    #                                 backward_sweep = 1
    #                             else:
    #                                 break
    #                     if backward_sweep == 1:
    #                         ch2.loop -= ch2.step
    #                         if ch2.loop < ch2.start:
    #                             break

    #                 elif ch2.start >= ch2.stop:
    #                     if backward_sweep == 0:
    #                         ch2.loop -= ch2.step
    #                         if ch2.loop < ch2.stop:     # Should not let equality (=)
    #                             if ch2.direction:
    #                                 backward_sweep = 1
    #                             else:
    #                                 break
    #                     if backward_sweep == 1:
    #                         ch2.loop += ch2.step
    #                         if ch2.loop > ch2.start:
    #                             break
    #     except asyncio.CancelledError:
    #         print("Loop task cancelled")
    #         raise

    # async def send_sine_data(self, ch1: ChannelConfig, ch2: ChannelConfig, interval_s: float):
    #     try: 
    #         ch1_loop = ch1.sine_low
    #         ch2_loop = ch2.sine_low

    #         ch1_period_counter = 0
    #         ch1_period_steps = int((ch1.sine_period/1000) / interval_s)
    #         ch2_period_counter = 0
    #         ch2_period_steps = int((ch2.sine_period/1000) / interval_s)

    #         while True:
    #             # Decide values
    #             ch1_loop_send_value = ch1_loop if ch1_loop >= 0 else ch1_loop + 65536
    #             ch2_loop_send_value = ch2_loop if ch2_loop >= 0 else ch2_loop + 65536
    #             v1 = ch1_loop_send_value if ch1.enabled else ch1.fixed_value
    #             v2 = ch2_loop_send_value if ch2.enabled else ch2.fixed_value

    #             # Merge packet
    #             packet = (
    #                 v1.to_bytes(2, 'big', signed=False) +
    #                 v2.to_bytes(2, 'big', signed=False)
    #             )

    #             await self.write_data(packet)
    #             await asyncio.sleep(interval_s)

    #             # Advance enabled channels only
    #             if ch1.enabled:
    #                 if ch1_period_counter <= ch1_period_steps:
    #                     ch1_loop = int((ch1.sine_low + ch1.sine_high)/2 + (ch1.sine_high - ch1.sine_low) * np.sin(ch1_period_counter*2*np.pi/ch1_period_steps)/2)
    #                     ch1_period_counter += 1
    #                     # print(ch1_loop, "\t", ch1_period_counter, "\t", ch1_loop_send_value, "\t Low: ", ch1.sine_low, "\t High: ", ch1.sine_high, "\t Period: ", ch1.sine_period)
    #                 else: 
    #                     break

    #             if ch2.enabled:
    #                 if ch2_period_counter <= ch2_period_steps:
    #                     ch2_loop = int((ch2.sine_low + ch2.sine_high)/2 + (ch2.sine_high - ch2.sine_low) * np.sin(ch2_period_counter*2*np.pi/ch2_period_steps)/2)
    #                     ch2_period_counter += 1
    #                 else: 
    #                     break
    #     except asyncio.CancelledError:
    #         print("Loop task cancelled")
    #         raise

    # async def send_pulse_data(self, ch1: ChannelConfig, ch2: ChannelConfig, interval_s: float):
    #     try: 
    #         ch1_loop = ch1.pulse_low
    #         ch2_loop = ch2.pulse_low

    #         ch1_period_counter = 0
    #         ch1_period_steps = int((ch1.pulse_period/1000) / interval_s)
    #         ch2_period_counter = 0
    #         ch2_period_steps = int((ch2.pulse_period/1000) / interval_s)

    #         while True:
    #             # Decide values
    #             ch1_loop_send_value = ch1_loop if ch1_loop >= 0 else ch1_loop + 65536
    #             ch2_loop_send_value = ch2_loop if ch2_loop >= 0 else ch2_loop + 65536
    #             v1 = ch1_loop_send_value if ch1.enabled else ch1.fixed_value
    #             v2 = ch2_loop_send_value if ch2.enabled else ch2.fixed_value

    #             # Merge packet
    #             packet = (
    #                 v1.to_bytes(2, 'big', signed=False) +
    #                 v2.to_bytes(2, 'big', signed=False)
    #             )

    #             await self.write_data(packet)
    #             await asyncio.sleep(interval_s)

    #             # Advance enabled channels only
    #             if ch1.enabled:
    #                 if ch1_period_counter <= ch1_period_steps:
    #                     if ch1_period_counter < ch1_period_steps/2:
    #                         ch1_loop = int(ch1.pulse_high)
    #                     else:
    #                         ch1_loop = int(ch1.pulse_low)
    #                     ch1_period_counter += 1
    #                 else: 
    #                     break

    #             if ch2.enabled:
    #                 if ch2_period_counter <= ch2_period_steps:
    #                     if ch2_period_counter < ch2_period_steps/2:
    #                         ch2_loop = int(ch2.pulse_high)
    #                     else:
    #                         ch2_loop = int(ch2.pulse_low)
    #                     ch2_period_counter += 1
    #                 else: 
    #                     break
    #     except asyncio.CancelledError:
    #         print("Loop task cancelled")
    #         raise

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
        self.tabs.setGeometry(490, 5, 1400, 970)  # adjust freely    500, 670, 1400, 300

        self.tab_time = QWidget()
        self.tabs.addTab(self.tab_time, "Time")

        self.tab_oect = QWidget()
        self.tabs.addTab(self.tab_oect, "OECT")

        # ---- Side Tab window, for waveform setup
        self.tabs_waveform = QTabWidget(self)
        self.tabs_waveform.setGeometry(10, 320, 470, 265)
        self.tabs_waveform.tabBar().hide()

        self.tab_triangle = QWidget()
        self.tabs_waveform.addTab(self.tab_triangle, "Triangle")
        self.tab_sine = QWidget()
        self.tabs_waveform.addTab(self.tab_sine, "Sine")
        self.tab_pulse = QWidget()
        self.tabs_waveform.addTab(self.tab_pulse, "Pulse")

        # ---- Main Tab window ----
        # ---- Device name ----
        QLabel("Device Name:", self).setGeometry(20, 20, 100, 25)
        self.device_edit = QLineEdit("NML", self)
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
            # ---- Waveform selection ----
        QLabel("Waveform:", self).setGeometry(150, 110, 100, 25)
        self.waveform_sel_box = QComboBox(self)
        self.waveform_sel_box.setGeometry(220, 110, 120, 25)
        self.waveform_sel_box.addItems(["Triangle", "Sine", "Pulse"])
        self.waveform_sel_box.currentIndexChanged.connect(self.tabs_waveform.setCurrentIndex)

            # ---- Triangle tab ----
        QLabel("Channel 1 Start:", self.tab_triangle).setGeometry(10, 20, 100, 25)
        self.start_edit_1 = QLineEdit("0", self.tabs_waveform)
        self.start_edit_1.setGeometry(120, 20, 100, 25)
        
        QLabel("Channel 1 Stop:", self.tab_triangle).setGeometry(10, 60, 100, 25)
        self.stop_edit_1 = QLineEdit("0", self.tabs_waveform)
        self.stop_edit_1.setGeometry(120, 60, 100, 25)
        
        QLabel("Channel 1 Step:", self.tab_triangle).setGeometry(10, 100, 100, 25)
        self.step_edit_1 = QLineEdit("0", self.tabs_waveform)
        self.step_edit_1.setGeometry(120, 100, 100, 25)

        QLabel("Channel 2 Start:", self.tab_triangle).setGeometry(235, 20, 100, 25)
        self.start_edit_2 = QLineEdit("0", self.tabs_waveform)
        self.start_edit_2.setGeometry(350, 20, 100, 25)
        
        QLabel("Channel 2 Stop:", self.tab_triangle).setGeometry(235, 60, 100, 25)
        self.stop_edit_2 = QLineEdit("0", self.tabs_waveform)
        self.stop_edit_2.setGeometry(350, 60, 100, 25)
        
        QLabel("Channel 2 Step:", self.tab_triangle).setGeometry(235, 100, 100, 25)
        self.step_edit_2 = QLineEdit("0", self.tabs_waveform)
        self.step_edit_2.setGeometry(350, 100, 100, 25)
        
        QLabel("Interval (ms):", self.tabs_waveform).setGeometry(10, 140, 100, 25)
        self.interval_edit = QLineEdit("20", self.tabs_waveform)
        self.interval_edit.setGeometry(120, 140, 100, 25)

        QLabel("Dual direction:", self.tab_triangle).setGeometry(240, 140, 100, 25)
        self.direction_enable = QCheckBox(self.tab_triangle)
        self.direction_enable.setGeometry(350, 140, 100, 25)

        self.start_loop_btn = QPushButton("Start Loop", self)
        self.start_loop_btn.setGeometry(20, 590, 120, 25)
        self.start_loop_btn.clicked.connect(self.start_loop)

        self.start_loop_btn = QPushButton("Stop Loop", self)
        self.start_loop_btn.setGeometry(20, 630, 120, 25)
        self.start_loop_btn.clicked.connect(self.stop_loop)

        QLabel("Number of cycles: ", self).setGeometry(250, 590, 120, 25)
        self.num_cycles_edit = QLineEdit("2", self)
        self.num_cycles_edit.setGeometry(360, 590, 100, 25)

            # ---- Enable & constant
        QLabel("CH1 constant:", self.tabs_waveform).setGeometry(10, 220, 100, 25)
        self.ch1_enable = QCheckBox("Enable CH1", self.tabs_waveform)
        self.ch1_enable.setGeometry(10, 0, 100, 25)
        self.ch1_value_edit = QLineEdit("0", self.tabs_waveform)               # Constant (default value is "0")
        self.ch1_value_edit.setGeometry(120, 220, 100, 25)

        QLabel("CH2 constant:", self.tabs_waveform).setGeometry(240, 220, 100, 25)
        self.ch2_enable = QCheckBox("Enable CH2", self.tabs_waveform)
        self.ch2_enable.setGeometry(230, 0, 100, 25)
        self.ch2_value_edit = QLineEdit("0", self.tabs_waveform)          # Constant (default value is "0")
        self.ch2_value_edit.setGeometry(350, 220, 100, 25)

            # ---- Sine tab ----
        QLabel("Sine Low Vpp:", self.tab_sine).setGeometry(10, 20, 100, 25)
        QLabel("Sine High Vpp:", self.tab_sine).setGeometry(10, 60, 100, 25)
        QLabel("Sine period:", self.tab_sine).setGeometry(10, 180, 100, 25)
        QLabel("Sine Low Vpp:", self.tab_sine).setGeometry(235, 20, 100, 25)
        QLabel("Sine High Vpp:", self.tab_sine).setGeometry(235, 60, 100, 25)
        QLabel("Sine period:", self.tab_sine).setGeometry(235, 180, 100, 25)

        QLabel("Period:", self.tab_triangle).setGeometry(10, 180, 100, 25)
        self.ch1_period_edit = QLineEdit("500", self.tabs_waveform)
        self.ch1_period_edit.setGeometry(120, 180, 100, 25)

        QLabel("Period:", self.tab_triangle).setGeometry(235, 180, 100, 25)
        self.ch2_period_edit = QLineEdit("500", self.tabs_waveform)
        self.ch2_period_edit.setGeometry(350, 180, 100, 25)

            # ---- Pulse tab ----
        QLabel("Low Vpp:", self.tab_pulse).setGeometry(10, 20, 100, 25)
        QLabel("High Vpp:", self.tab_pulse).setGeometry(10, 60, 100, 25)
        QLabel("Duty cycle:", self.tab_pulse).setGeometry(10, 100, 100, 25)
        QLabel("Pulse period:", self.tab_pulse).setGeometry(10, 180, 100, 25)
        QLabel("Low Vpp:", self.tab_pulse).setGeometry(235, 20, 100, 25)
        QLabel("High Vpp:", self.tab_pulse).setGeometry(235, 60, 100, 25)
        QLabel("Duty cycle:", self.tab_pulse).setGeometry(235, 100, 100, 25)
        QLabel("Pulse period:", self.tab_pulse).setGeometry(235, 180, 100, 25)

        self.ch1_enable.stateChanged.connect(self.on_ch1_enable_changed)
        self.ch2_enable.stateChanged.connect(self.on_ch2_enable_changed)

        # Command (CMD) setup
        QLabel("Send command:", self).setGeometry(20, 720, 100, 30)
        self.cmd_edit = QLineEdit("01", self)          # Constant (default value is "0")
        # 01: voltage measure
        # 02: inject current
        # 00: reset
        self.cmd_edit.setGeometry(130, 720, 100, 30)

        self.send_cmd_btn = QPushButton("Send", self)
        self.send_cmd_btn.setGeometry(250, 720, 100, 30)
        self.send_cmd_btn.clicked.connect(self.send_cmd_data)

        # Initial state
        self.on_ch1_enable_changed(self.ch1_enable.checkState())
        self.on_ch2_enable_changed(self.ch2_enable.checkState())

        # ---- pyqtgraph ----
        self.max_points = 10000

        self.time_buffer = deque(maxlen=self.max_points)
        self.time_ble_buffer = deque(maxlen=self.max_points)
        self.data_buffer_1 = deque(maxlen=self.max_points)
        self.data_buffer_2 = deque(maxlen=self.max_points)
        self.data_buffer_3 = deque(maxlen=self.max_points)

        # self.t0 = time.perf_counter()
        self.reset_time_request = 1

        # ---- Axis label style
        label_style_main_tab = {
                'color': "#FFFFFF",
                'font-size': '11pt',
                'font-weight': 'bold'
            }
        # ---- Channel 1 graph ----
        self.plot_widget_1 = pg.PlotWidget(self.tab_time)
        self.plot_widget_1.setGeometry(0, 0, 1380, 300)
        self.plot_widget_1.setLabel('left', 'Channel 1 (uA)', **label_style_main_tab)
        self.plot_widget_1.setLabel('bottom', 'Time', units='s', **label_style_main_tab)
        self.plot_widget_1.showGrid(x=True, y=True)

        self.plot_curve_1 = self.plot_widget_1.plot(pen='y')

        # ---- Channel 2 graph ----
        self.plot_widget_2 = pg.PlotWidget(self.tab_time)
        self.plot_widget_2.setGeometry(0, 320, 1380, 300)
        self.plot_widget_2.setLabel('left', 'Channel 2 (Drain) (mV)', **label_style_main_tab)
        self.plot_widget_2.setLabel('bottom', 'Time', units='s', **label_style_main_tab)
        self.plot_widget_2.showGrid(x=True, y=True)

        self.plot_curve_2 = self.plot_widget_2.plot(pen='y')

        # ---- Channel 3 graph ----
        self.plot_widget_3 = pg.PlotWidget(self.tab_time)
        self.plot_widget_3.setGeometry(0, 640, 1380, 300)
        self.plot_widget_3.setLabel('left', 'Channel 3 (Gate) (mV)', **label_style_main_tab)
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
        self.plot_widget_4.setGeometry(0, 0, 1380, 300)
        self.plot_widget_4.setLabel('left', 'ID', **label_style_oect_tab)
        self.plot_widget_4.setLabel('bottom', 'VG', units='mV', **label_style_oect_tab)
        self.plot_widget_4.showGrid(x=True, y=True)
        self.plot_widget_4.setBackground(background=(255, 255, 255))

        self.plot_curve_4 = self.plot_widget_4.plot(pen='r')
        self.plot_marker_4 = self.plot_widget_4.plot(pen='g', symbol='o', symbolSize=15, symbolBrush='b', symbolPen='b')

        # ---- ID vs VD graph ----
        self.plot_widget_5 = pg.PlotWidget(self.tab_oect)
        self.plot_widget_5.setGeometry(0, 320, 1380, 300)
        self.plot_widget_5.setLabel('left', 'ID', **label_style_oect_tab)
        self.plot_widget_5.setLabel('bottom', 'VD', units='mV', **label_style_oect_tab)
        self.plot_widget_5.showGrid(x=True, y=True)
        self.plot_widget_5.setBackground(background=(255, 255, 255))

        self.plot_curve_5 = self.plot_widget_5.plot(pen='r')
        self.plot_marker_5 = self.plot_widget_5.plot(pen='g', symbol='o', symbolSize=15, symbolBrush='b', symbolPen='b')

        # ---- Reset graph ----
        self.reset_graph_btn = QPushButton("Reset Graph", self)
        self.reset_graph_btn.setGeometry(20, 110, 120, 30)  # adjust freely
        self.reset_graph_btn.clicked.connect(self.reset_graph)

        # ---- Saving to .csv ----
        self.csv_time = []
        self.csv_ch1 = []
        self.csv_ch2 = []
        self.csv_ch3 = []

        QLabel("CSV filename:", self).setGeometry(20, 680, 100, 30)
        self.csv_name_edit = QLineEdit(self)
        self.csv_name_edit.setGeometry(130, 680, 200, 30)
        self.csv_name_edit.setPlaceholderText("enter filename here")

        self.save_csv_btn = QPushButton("Save CSV", self)
        self.save_csv_btn.setGeometry(350, 680, 120, 30)
        self.save_csv_btn.clicked.connect(self.save_csv)

    def reset_graph(self):
        # reset time reference
        # self.t0 = time.perf_counter()
        # self.t0 = self.t_ble       # Change time ble
        self.reset_time_request = 1

        # clear buffers
        self.time_buffer.clear()
        self.data_buffer_1.clear()
        self.data_buffer_2.clear()
        self.data_buffer_3.clear()

        # clear plot
        self.plot_curve_1.setData([], [])
        self.plot_curve_2.setData([], [])
        self.plot_curve_3.setData([], [])
        self.plot_curve_4.setData([], [])
        self.plot_curve_5.setData([], [])

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
            writer.writerow(["Time (s)", "Channel 1 (mA)", "Channel 2 (mV)", "Channel 3 (mV)"])

            for t, c1, c2, c3 in zip(self.csv_time, self.csv_ch1, self.csv_ch2, self.csv_ch3):
                writer.writerow([t, c1, c2, c3])

        self.rx_box.append(f"Data saved to {path}")

    # ---- Set channel value from textbox
    def get_ch1_config(self) -> ChannelConfig:
        return ChannelConfig(
            loop=0,
            start=int(self.start_edit_1.text()),
            stop=int(self.stop_edit_1.text()),
            step=int(self.step_edit_1.text()),
            fixed_value=int(self.ch1_value_edit.text()),
            enabled=self.ch1_enable.isChecked(),
            direction=self.direction_enable.isChecked(),
            period=int(self.ch1_period_edit.text()),
        )
    
    def get_ch2_config(self) -> ChannelConfig:
        return ChannelConfig(
            loop=0,
            start=int(self.start_edit_2.text()),
            stop=int(self.stop_edit_2.text()),
            step=int(self.step_edit_2.text()),
            fixed_value=int(self.ch2_value_edit.text()),
            enabled=self.ch2_enable.isChecked(),
            direction=self.direction_enable.isChecked(),
            period=int(self.ch2_period_edit.text()),
        )

    # ---- Check enable chanel ----
    def on_ch1_enable_changed(self, state):
        enabled = state == Qt.Checked
        self.ch1_value_edit.setEnabled(not enabled)
        self.start_edit_1.setEnabled(enabled)
        self.stop_edit_1.setEnabled(enabled)
        self.step_edit_1.setEnabled(enabled)
        self.ch1_period_edit.setEnabled(enabled)

    def on_ch2_enable_changed(self, state):
        enabled = state == Qt.Checked
        self.ch2_value_edit.setEnabled(not enabled)
        self.start_edit_2.setEnabled(enabled)
        self.stop_edit_2.setEnabled(enabled)
        self.step_edit_2.setEnabled(enabled)
        self.ch2_period_edit.setEnabled(enabled)

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

    def send_cmd_data(self):
        if not self.ble_worker:
            return

        text = self.cmd_edit.text().strip()
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
            self.ble_worker.write_cmd_data(data),
            self.ble_worker.loop
        )

        if (data == b'\x00'):
            reset_packet = b'\x00\x00\x00\x00\x00\x00\x00\x00'
            print(data)
            asyncio.run_coroutine_threadsafe(
                self.ble_worker.write_data(reset_packet),
                self.ble_worker.loop
            )

    # ---------- Receive ----------
    def on_rx_data(self, data: bytes):
        hex_str = " ".join(f"{b:02X}" for b in data)
        self.rx_box.append(hex_str)
        
        # ---- pyqtgraph Handler ----
        # ---- decode ----
        channel_1 = np.int32(int.from_bytes(data[0:2], byteorder='big', signed=True))
        # adc_0_value = float(int(match_2.group(1)) - 1280)/-326        # Formula for ID, PEDOT
        channel_1 = (channel_1 - 650) / -10000.0
        channel_1_coef_a = 1.77786
        channel_1_coef_b = 0.11202
        channel_1 = channel_1 * channel_1_coef_a + channel_1_coef_b

        channel_2 = np.int32(int.from_bytes(data[2:4], byteorder='big', signed=True))
        # Calibrate with coefficient a, b
        channel_2_coef_a = 0.9936
        channel_2_coef_b = 3.4410
        channel_2 = channel_2 * channel_2_coef_a + channel_2_coef_b

        channel_3 = np.int32(int.from_bytes(data[4:6], byteorder='big', signed=True))
        # Calibrate with coefficient a, b
        channel_3_coef_a = 0.9920
        channel_3_coef_b = 11.8900
        channel_3 = channel_3 * channel_3_coef_a + channel_3_coef_b
        if channel_3 < 1150:
            channel_3_coef_a2 = 2.0049
            channel_3_coef_b2 = -1326
        else: 
            channel_3_coef_a2 = 1.9317
            channel_3_coef_b2 = -1230.9
        channel_3 = channel_3 * channel_3_coef_a2 + channel_3_coef_b2

        # ---- time ----
        # t = time.perf_counter() - self.t0       # Python time
        self.t_ble = np.int32(int.from_bytes(data[10:18], byteorder='big', signed=True))/1000

        if self.reset_time_request:
            self.t0 = self.t_ble
            self.reset_time_request = 0

        self.t_ble = self.t_ble - self.t0

        # ---- push into deque ----
        # self.time_buffer.append(t)
        self.time_buffer.append(self.t_ble)              # Change time ble
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
        self.plot_marker_4.setData(list([channel_3]), list([channel_1]))
        self.plot_marker_5.setData(list([channel_2]), list([channel_1]))

        # # ---- optional text display ----
        # self.rx_box.append(f"{t:.3f}s : {channel_1}")
        # self.rx_box.append(f"{t:.3f}s : {channel_2}")
        # self.rx_box.append(f"{t:.3f}s : {channel_3}")

        # ---- save to .csv array ----
        # self.csv_time.append(t)             
        self.csv_time.append(self.t_ble)                 # Change time ble
        self.csv_ch1.append(channel_1)
        self.csv_ch2.append(channel_2)
        self.csv_ch3.append(channel_3)

    # ---------- Set data in a loop ----------
    def start_loop(self):
        self.ble_worker.loop_running = True

        interval_s = int(self.interval_edit.text()) / 1000
        self.ch1_cfg = self.get_ch1_config()
        self.ch2_cfg = self.get_ch2_config()

        num_cycles = int(self.num_cycles_edit.text())

        # Cancel existing task if running
        if hasattr(self, "loop_task") and self.loop_task:
            self.loop_task.cancel()

        waveform_index = self.waveform_sel_box.currentIndex()

        self.loop_task = asyncio.run_coroutine_threadsafe(
            self.ble_worker.send_loop_data(self.ch1_cfg, self.ch2_cfg, waveform_index, interval_s, num_cycles),
            self.ble_worker.loop
        )

        # current = self.waveform_sel_box.currentText()

        # if current == "Sine":
        #     # print("Waveform index: ", self.waveform_sel_box.currentIndex())
        #     self.loop_task = asyncio.run_coroutine_threadsafe(
        #         self.ble_worker.send_sine_data(self.ch1_cfg, self.ch2_cfg, interval_s),
        #         self.ble_worker.loop
        #     )

        # if current == "Triangle":
        #     # Create and store task
        #     self.loop_task = asyncio.run_coroutine_threadsafe(
        #         self.ble_worker.send_triangle_data(self.ch1_cfg, self.ch2_cfg, interval_s),
        #         self.ble_worker.loop
        #     )

        # if current == "Pulse":
        #     self.loop_task = asyncio.run_coroutine_threadsafe(
        #         self.ble_worker.send_pulse_data(self.ch1_cfg, self.ch2_cfg, interval_s),
        #         self.ble_worker.loop
        #     )

    def stop_loop(self):
        self.ble_worker.loop_running = False        

        if hasattr(self, "loop_task") and self.loop_task:
            self.loop_task.cancel()
            self.loop_task = None

# ================= MAIN =================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = BLEApp()
    win.show()
    sys.exit(app.exec_())
