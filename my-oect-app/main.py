import sys
import asyncio
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLineEdit,
    QTextEdit, QLabel, QComboBox
)
from PyQt5.QtCore import QThread, pyqtSignal
from bleak import BleakScanner, BleakClient

# SERVICE_UUID = "00001234-0000-1000-8000-00805f9b34fb"
# CHAR_UUID    = "00009876-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "1234"
CHAR_UUID    = "9876"

# ================ SET DATA SEND IN A LOOP ================
class LoopWorker(QThread):
    update_value = pyqtSignal(int)  # optional, for GUI display

    def __init__(self, ble_worker, start, stop, step, interval_ms):
        super().__init__()
        self.ble_worker = ble_worker
        self.start = start
        self.stop = stop
        self.step = step
        self.interval = interval_ms / 1000
        self._running = True

    def run(self):
        val = self.start
        while self._running and val <= self.stop:
            # emit signal if you want to display
            self.update_value.emit(val)
            
            # send via BLE
            asyncio.run_coroutine_threadsafe(
                self.ble_worker.write_data(bytes([val])),
                self.ble_worker.loop
            )

            val += self.step
            time.sleep(self.interval)  # simple delay

    def stop_run(self):
        self._running = False


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


# ================= MAIN UI =================
class BLEApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLE PyQt5 App")
        self.setGeometry(200, 200, 520, 800)

        # ---- Device name ----
        QLabel("Device Name:", self).setGeometry(20, 20, 100, 25)
        self.device_edit = QLineEdit(self)
        self.device_edit.setGeometry(130, 20, 200, 25)

        self.scan_btn = QPushButton("Scan", self)
        self.scan_btn.setGeometry(350, 20, 120, 25)
        self.scan_btn.clicked.connect(self.start_scan)

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
        QLabel("Start value:", self).setGeometry(20, 350, 100, 25)
        self.start_edit = QLineEdit(self)
        self.start_edit.setGeometry(130, 350, 200, 25)
        
        QLabel("Stop value:", self).setGeometry(20, 390, 100, 25)
        self.stop_edit = QLineEdit(self)
        self.stop_edit.setGeometry(130, 390, 200, 25)
        
        QLabel("Step:", self).setGeometry(20, 430, 100, 25)
        self.step_edit = QLineEdit(self)
        self.step_edit.setGeometry(130, 430, 200, 25)
        
        QLabel("Interval (ms):", self).setGeometry(20, 470, 100, 25)
        self.interval_edit = QLineEdit(self)
        self.interval_edit.setGeometry(130, 470, 200, 25)

        self.start_loop_btn = QPushButton("Start Loop", self)
        self.start_loop_btn.setGeometry(20, 550, 120, 25)
        self.start_loop_btn.clicked.connect(self.start_loop)

        self.start_loop_btn = QPushButton("Stop Loop", self)
        self.start_loop_btn.setGeometry(20, 590, 120, 25)
        self.start_loop_btn.clicked.connect(self.start_loop)

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

    # ---------- Set data in a loop ----------
    def start_loop(self):
        start = int(self.start_edit.text())
        stop = int(self.stop_edit.text())
        step = int(self.step_edit.text())
        interval = int(self.interval_edit.text())

        self.loop_worker = LoopWorker(self.ble_worker, start, stop, step, interval)
        # self.loop_worker.update_value.connect(self.show_loop_value)  # optional
        self.loop_worker.run()

    def stop_loop(self):
        if hasattr(self, "loop_worker"):
            self.loop_worker.stop_run()
            self.loop_worker.wait()


# ================= MAIN =================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = BLEApp()
    win.show()
    sys.exit(app.exec_())
