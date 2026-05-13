import sys
import os
import numpy as np
import asyncio
import csv
import pyqtgraph as pg
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLineEdit,
    QTextEdit, QLabel, QComboBox, QCheckBox,
    QTabWidget, QGroupBox, QHBoxLayout, QVBoxLayout,
    QSizePolicy, QFrame, QSplitter,
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont
from bleak import BleakScanner, BleakClient
from dataclasses import dataclass


# ───────────────────────────── Config ─────────────────────────────

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


SERVICE_UUID  = "1234"
CHAR_UUID     = "9876"
CMD_CHAR_UUID = "9000"


# ─────────────────────────── BLE Thread ───────────────────────────

class BLEWorker(QThread):
    device_found = pyqtSignal(str)
    scan_failed  = pyqtSignal()
    rx_data      = pyqtSignal(bytes)

    loop_running = False

    def __init__(self, device_name: str):
        super().__init__()
        self.device_name = device_name
        self.client = None

    async def scan_and_connect(self):
        devices = await BleakScanner.discover(timeout=4.0)
        for d in devices:
            if d.name == self.device_name:
                self.client = BleakClient(d.address)
                await self.client.connect()
                await self.client.start_notify(CHAR_UUID, self.notification_handler)
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

    async def send_loop_data(
        self,
        ch1: ChannelConfig,
        ch2: ChannelConfig,
        waveform_index: int,
        interval_s: float,
        num_cycles: int,
    ):
        try:
            for cycle in range(num_cycles):
                print(f"Cycle {cycle + 1}/{num_cycles}")

                if waveform_index == 0:
                    ch1.loop = ch1.start
                    ch2.loop = ch2.start
                elif waveform_index == 1:
                    ch1.loop = int((ch1.start + ch1.stop) / 2)
                    ch2.loop = int((ch2.start + ch2.stop) / 2)

                backward_sweep = 0

                ch1_period_counter = 0
                ch1_period_steps   = int((ch1.period / 1000) / interval_s)
                ch2_period_counter = 0
                ch2_period_steps   = int((ch2.period / 1000) / interval_s)

                while True:
                    ch1_send = ch1.loop if ch1.loop >= 0 else ch1.loop + 65536
                    ch2_send = ch2.loop if ch2.loop >= 0 else ch2.loop + 65536
                    v1 = ch1_send if ch1.enabled else ch1.fixed_value
                    v2 = ch2_send if ch2.enabled else ch2.fixed_value

                    packet = (
                        v1.to_bytes(2, "big", signed=False) +
                        v2.to_bytes(2, "big", signed=False)
                    )
                    await self.write_data(packet)
                    await asyncio.sleep(interval_s)

                    if ch1.enabled:
                        if waveform_index == 0:     # Triangle
                            if ch1.start <= ch1.stop:
                                if backward_sweep == 0:
                                    ch1.loop += ch1.step
                                    if ch1.loop > ch1.stop:
                                        if ch1.direction:
                                            backward_sweep = 1
                                        else:
                                            break
                                if backward_sweep == 1:
                                    ch1.loop -= ch1.step
                                    if ch1.loop < ch1.start:
                                        break
                            else:
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

                        elif waveform_index == 1:   # Sine
                            if ch1_period_counter <= ch1_period_steps:
                                ch1.loop = int(
                                    (ch1.start + ch1.stop) / 2
                                    + (ch1.start - ch1.stop)
                                    * np.sin(ch1_period_counter * 2 * np.pi / ch1_period_steps)
                                    / 2
                                )
                                ch1_period_counter += 1
                            else:
                                break

                        elif waveform_index == 2:   # Pulse
                            if ch1_period_counter <= ch1_period_steps:
                                if ch1_period_counter < ch1_period_steps * ch1.step / 100:
                                    ch1.loop = ch1.stop
                                else:
                                    ch1.loop = ch1.start
                                ch1_period_counter += 1
                            else:
                                break

                    if ch2.enabled:
                        if waveform_index == 0:     # Triangle
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
                            else:
                                if backward_sweep == 0:
                                    ch2.loop -= ch2.step
                                    if ch2.loop < ch2.stop:
                                        if ch2.direction:
                                            backward_sweep = 1
                                        else:
                                            break
                                if backward_sweep == 1:
                                    ch2.loop += ch2.step
                                    if ch2.loop > ch2.start:
                                        break

                        elif waveform_index == 1:   # Sine
                            if ch2_period_counter <= ch2_period_steps:
                                ch2.loop = int(
                                    (ch2.start + ch2.stop) / 2
                                    + (ch2.start - ch2.stop)
                                    * np.sin(ch2_period_counter * 2 * np.pi / ch2_period_steps)
                                    / 2
                                )
                                ch2_period_counter += 1
                            else:
                                break

                        elif waveform_index == 2:   # Pulse
                            if ch2_period_counter <= ch2_period_steps:
                                if ch2_period_counter < ch2_period_steps * ch2.step / 100:
                                    ch2.loop = ch2.stop
                                else:
                                    ch2.loop = ch2.start
                                ch2_period_counter += 1
                            else:
                                break

        except asyncio.CancelledError:
            print("Loop task cancelled")
            raise


# ──────────────────────────── Helpers ─────────────────────────────

def _label(text: str, parent=None) -> QLabel:
    lbl = QLabel(text, parent)
    return lbl


def _line(default: str = "", parent=None, placeholder: str = "") -> QLineEdit:
    w = QLineEdit(default, parent)
    if placeholder:
        w.setPlaceholderText(placeholder)
    return w


def _btn(text: str, parent=None) -> QPushButton:
    return QPushButton(text, parent)


def _group(title: str) -> QGroupBox:
    g = QGroupBox(title)
    return g


def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


# ──────────────────────────── Main UI ─────────────────────────────

APP_STYLE = """
/* ── Global ── */
QWidget {
    background-color: #0f1117;
    color: #d4d8e2;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}

/* ── Group boxes ── */
QGroupBox {
    border: 1px solid #2a2e3e;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    color: #7b8cad;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
}

/* ── Labels ── */
QLabel {
    color: #8a93aa;
    font-size: 11px;
}

/* ── Line edits ── */
QLineEdit {
    background-color: #1a1e2d;
    border: 1px solid #2a2e3e;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e0e4f0;
    selection-background-color: #3a5bcc;
}
QLineEdit:focus {
    border-color: #3a5bcc;
}
QLineEdit:disabled {
    background-color: #141720;
    color: #3a3e50;
    border-color: #1e2230;
}

/* ── Buttons ── */
QPushButton {
    background-color: #1e2335;
    border: 1px solid #2e3450;
    border-radius: 4px;
    padding: 5px 12px;
    color: #c8cedf;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.04em;
}
QPushButton:hover {
    background-color: #252c45;
    border-color: #3a5bcc;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: #1a2240;
}
QPushButton:disabled {
    background-color: #141720;
    color: #3a3e50;
    border-color: #1e2230;
}

/* ── Accent buttons ── */
QPushButton#accent {
    background-color: #1e3a70;
    border-color: #2a4fa0;
    color: #aac4ff;
}
QPushButton#accent:hover {
    background-color: #254894;
    color: #ffffff;
}
QPushButton#danger {
    background-color: #3a1a1a;
    border-color: #7a2a2a;
    color: #ff9090;
}
QPushButton#danger:hover {
    background-color: #501a1a;
    color: #ffbbbb;
}
QPushButton#success {
    background-color: #0e3020;
    border-color: #1a6040;
    color: #70e0a0;
}
QPushButton#success:hover {
    background-color: #154030;
    color: #a0ffcc;
}

/* ── ComboBox ── */
QComboBox {
    background-color: #1a1e2d;
    border: 1px solid #2a2e3e;
    border-radius: 4px;
    padding: 4px 8px;
    color: #d4d8e2;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #1a1e2d;
    border: 1px solid #3a5bcc;
    selection-background-color: #2a3a70;
    color: #d4d8e2;
}

/* ── CheckBox ── */
QCheckBox {
    color: #8a93aa;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3a3e50;
    border-radius: 3px;
    background: #1a1e2d;
}
QCheckBox::indicator:checked {
    background-color: #3a5bcc;
    border-color: #5a7bec;
}

/* ── TextEdit (RX log) ── */
QTextEdit {
    background-color: #090b10;
    border: 1px solid #1e2230;
    border-radius: 4px;
    color: #60e890;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 4px;
}

/* ── Tabs ── */
QTabWidget::pane {
    border: 1px solid #2a2e3e;
    border-radius: 4px;
    background: #0f1117;
}
QTabBar::tab {
    background: #141720;
    border: 1px solid #2a2e3e;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    padding: 6px 18px;
    color: #5a6080;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.06em;
}
QTabBar::tab:selected {
    background: #0f1117;
    color: #a0b4ff;
    border-color: #3a5bcc;
}
QTabBar::tab:hover {
    color: #c0d0ff;
}

/* ── Splitter ── */
QSplitter::handle {
    background: #2a2e3e;
    width: 3px;
}

/* ── Separator line ── */
QFrame[frameShape="4"] {   /* HLine */
    border: none;
    border-top: 1px solid #1e2230;
    margin: 4px 0;
}
"""


class BLEApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SoftElectronicsGroup — OECT Controller")
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(screen.width(), screen.height())

        self.ble_worker = None
        self.loop_task  = None

        # ── data buffers ──
        self.max_points    = 10_000
        self.time_buffer   = deque(maxlen=self.max_points)
        self.data_buffer_1 = deque(maxlen=self.max_points)
        self.data_buffer_2 = deque(maxlen=self.max_points)
        self.data_buffer_3 = deque(maxlen=self.max_points)

        self.reset_time_request = 1
        self.t0    = 0.0
        self.t_ble = 0.0

        self.csv_time = []
        self.csv_ch1  = []
        self.csv_ch2  = []
        self.csv_ch3  = []

        self._build_ui()
        self._initial_enable_state()

    # ──────────────────── UI construction ────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # left panel + right graphs side-by-side
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        left = self._build_left_panel()
        splitter.addWidget(left)

        right = self._build_right_panel()
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([480, 9999])

    # ── Left panel ──

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setMaximumWidth(490)
        w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        vbox.addWidget(self._group_connection())
        vbox.addWidget(self._group_manual_tx())
        vbox.addWidget(self._group_waveform())
        vbox.addWidget(self._group_loop_control())
        vbox.addWidget(self._group_command())
        vbox.addWidget(self._group_csv())
        vbox.addWidget(self._group_rx_log())
        vbox.addStretch()

        return w

    def _group_connection(self) -> QGroupBox:
        g = _group("BLE Connection")
        grid = QVBoxLayout(g)
        grid.setSpacing(6)

        row1 = QHBoxLayout()
        row1.addWidget(_label("Device name"))
        self.device_edit = _line("NML", placeholder="BLE device name")
        row1.addWidget(self.device_edit)
        grid.addLayout(row1)

        row2 = QHBoxLayout()
        self.scan_btn = _btn("⬤  Scan")
        self.scan_btn.setObjectName("accent")
        self.scan_btn.clicked.connect(self.start_scan)
        self.disconnect_btn = _btn("Disconnect")
        self.disconnect_btn.setObjectName("danger")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        row2.addWidget(self.scan_btn)
        row2.addWidget(self.disconnect_btn)
        grid.addLayout(row2)

        return g

    def _group_manual_tx(self) -> QGroupBox:
        g = _group("Manual TX")
        vbox = QVBoxLayout(g)
        vbox.setSpacing(6)

        row1 = QHBoxLayout()
        row1.addWidget(_label("Data"))
        self.tx_edit = _line(placeholder="value to send")
        row1.addWidget(self.tx_edit)
        self.format_box = QComboBox()
        self.format_box.addItems(["Hex", "Dec"])
        self.format_box.setFixedWidth(70)
        row1.addWidget(self.format_box)
        vbox.addLayout(row1)

        self.send_btn = _btn("Send TX")
        self.send_btn.clicked.connect(self.send_data)
        vbox.addWidget(self.send_btn)

        return g

    def _group_waveform(self) -> QGroupBox:
        g = _group("Waveform Generator")
        vbox = QVBoxLayout(g)
        vbox.setSpacing(8)

        # waveform selector
        sel_row = QHBoxLayout()
        sel_row.addWidget(_label("Waveform"))
        self.waveform_sel_box = QComboBox()
        self.waveform_sel_box.addItems(["Triangle", "Sine", "Pulse"])
        sel_row.addWidget(self.waveform_sel_box)

        self.tabs_waveform = QTabWidget()
        self.tabs_waveform.tabBar().hide()
        self.waveform_sel_box.currentIndexChanged.connect(self.tabs_waveform.setCurrentIndex)

        self.tab_triangle = self._build_tab_triangle()
        self.tab_sine     = self._build_tab_sine()
        self.tab_pulse    = self._build_tab_pulse()
        self.tabs_waveform.addTab(self.tab_triangle, "Triangle")
        self.tabs_waveform.addTab(self.tab_sine,     "Sine")
        self.tabs_waveform.addTab(self.tab_pulse,    "Pulse")

        vbox.addLayout(sel_row)
        vbox.addWidget(_hline())

        # enable / constant row (shared across tabs)
        en_row = QHBoxLayout()
        self.ch1_enable = QCheckBox("Enable CH1")
        self.ch2_enable = QCheckBox("Enable CH2")
        en_row.addWidget(self.ch1_enable)
        en_row.addWidget(self.ch2_enable)
        vbox.addLayout(en_row)

        const_row = QHBoxLayout()
        const_row.addWidget(_label("CH1 const"))
        self.ch1_value_edit = _line("0")
        const_row.addWidget(self.ch1_value_edit)
        const_row.addSpacing(10)
        const_row.addWidget(_label("CH2 const"))
        self.ch2_value_edit = _line("0")
        const_row.addWidget(self.ch2_value_edit)
        vbox.addLayout(const_row)

        vbox.addWidget(self.tabs_waveform)

        # connect enable toggles
        self.ch1_enable.stateChanged.connect(self.on_ch1_enable_changed)
        self.ch2_enable.stateChanged.connect(self.on_ch2_enable_changed)

        return g

    def _build_tab_triangle(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setSpacing(6)

        # CH1 row
        r1 = QHBoxLayout()
        r1.addWidget(_label("CH1  Start"))
        self.start_edit_1 = _line("0"); r1.addWidget(self.start_edit_1)
        r1.addWidget(_label("Stop"))
        self.stop_edit_1  = _line("0"); r1.addWidget(self.stop_edit_1)
        r1.addWidget(_label("Step"))
        self.step_edit_1  = _line("0"); r1.addWidget(self.step_edit_1)
        vbox.addLayout(r1)

        # CH2 row
        r2 = QHBoxLayout()
        r2.addWidget(_label("CH2  Start"))
        self.start_edit_2 = _line("0"); r2.addWidget(self.start_edit_2)
        r2.addWidget(_label("Stop"))
        self.stop_edit_2  = _line("0"); r2.addWidget(self.stop_edit_2)
        r2.addWidget(_label("Step"))
        self.step_edit_2  = _line("0"); r2.addWidget(self.step_edit_2)
        vbox.addLayout(r2)

        # Period + direction
        r3 = QHBoxLayout()
        r3.addWidget(_label("CH1 period (ms)"))
        self.ch1_period_edit = _line("500"); r3.addWidget(self.ch1_period_edit)
        r3.addWidget(_label("CH2 period (ms)"))
        self.ch2_period_edit = _line("500"); r3.addWidget(self.ch2_period_edit)
        vbox.addLayout(r3)

        r4 = QHBoxLayout()
        r4.addWidget(_label("Dual direction"))
        self.direction_enable = QCheckBox()
        r4.addWidget(self.direction_enable)
        r4.addStretch()
        vbox.addLayout(r4)

        return w

    def _build_tab_sine(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.addWidget(_label(
            "Sine waveform uses the same Start / Stop / Period\n"
            "parameters as the Triangle tab.",
        ))
        vbox.addStretch()
        return w

    def _build_tab_pulse(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.addWidget(_label(
            "Pulse waveform uses Start (low), Stop (high),\n"
            "Step (duty-cycle %) and Period from the Triangle tab.",
        ))
        vbox.addStretch()
        return w

    def _group_loop_control(self) -> QGroupBox:
        g = _group("Loop Control")
        vbox = QVBoxLayout(g)
        vbox.setSpacing(6)

        row = QHBoxLayout()
        row.addWidget(_label("Interval (ms)"))
        self.interval_edit = _line("20")
        self.interval_edit.setFixedWidth(70)
        row.addWidget(self.interval_edit)
        row.addSpacing(12)
        row.addWidget(_label("Cycles"))
        self.num_cycles_edit = _line("2")
        self.num_cycles_edit.setFixedWidth(70)
        row.addWidget(self.num_cycles_edit)
        vbox.addLayout(row)

        btn_row = QHBoxLayout()
        self.start_loop_btn = _btn("▶  Start Loop")
        self.start_loop_btn.setObjectName("success")
        self.start_loop_btn.clicked.connect(self.start_loop)
        self.stop_loop_btn = _btn("■  Stop Loop")
        self.stop_loop_btn.setObjectName("danger")
        self.stop_loop_btn.clicked.connect(self.stop_loop)
        btn_row.addWidget(self.start_loop_btn)
        btn_row.addWidget(self.stop_loop_btn)
        vbox.addLayout(btn_row)

        return g

    def _group_command(self) -> QGroupBox:
        g = _group("Command (CMD)")
        row = QHBoxLayout(g)
        row.addWidget(_label("Payload"))
        self.cmd_edit = _line("01", placeholder="01=measure 02=inject 00=reset")
        row.addWidget(self.cmd_edit)
        self.send_cmd_btn = _btn("Send CMD")
        self.send_cmd_btn.clicked.connect(self.send_cmd_data)
        row.addWidget(self.send_cmd_btn)
        return g

    def _group_csv(self) -> QGroupBox:
        g = _group("Data Export")
        row = QHBoxLayout(g)
        row.addWidget(_label("Filename"))
        self.csv_name_edit = _line(placeholder="data")
        row.addWidget(self.csv_name_edit)
        self.save_csv_btn = _btn("Save CSV")
        self.save_csv_btn.clicked.connect(self.save_csv)
        row.addWidget(self.save_csv_btn)
        return g

    def _group_rx_log(self) -> QGroupBox:
        g = _group("RX Log")
        vbox = QVBoxLayout(g)
        self.rx_box = QTextEdit()
        self.rx_box.setReadOnly(True)
        self.rx_box.setMinimumHeight(120)
        vbox.addWidget(self.rx_box)
        return g

    # ── Right panel (graphs) ──

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        # reset graph button (top-right)
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.reset_graph_btn = _btn("↺  Reset Graph")
        self.reset_graph_btn.clicked.connect(self.reset_graph)
        top_bar.addWidget(self.reset_graph_btn)
        vbox.addLayout(top_bar)

        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)

        self.tab_time = QWidget()
        self.tabs.addTab(self.tab_time, "Time Domain")
        self.tab_oect = QWidget()
        self.tabs.addTab(self.tab_oect, "OECT Curves")

        self._build_time_tab()
        self._build_oect_tab()

        return w

    def _build_time_tab(self):
        vbox = QVBoxLayout(self.tab_time)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)

        label_style = {"color": "#aab4d4", "font-size": "10pt", "font-weight": "bold"}

        self.plot_widget_1 = pg.PlotWidget()
        self.plot_widget_1.setLabel("left",   "Channel 1 — ID (µA)",  **label_style)
        self.plot_widget_1.setLabel("bottom", "Time (s)",              **label_style)
        self.plot_widget_1.showGrid(x=True, y=True, alpha=0.2)
        self.plot_curve_1 = self.plot_widget_1.plot(pen=pg.mkPen("#ffd04e", width=1.5))
        vbox.addWidget(self.plot_widget_1)

        self.plot_widget_2 = pg.PlotWidget()
        self.plot_widget_2.setLabel("left",   "Channel 2 — VD (mV)",  **label_style)
        self.plot_widget_2.setLabel("bottom", "Time (s)",              **label_style)
        self.plot_widget_2.showGrid(x=True, y=True, alpha=0.2)
        self.plot_curve_2 = self.plot_widget_2.plot(pen=pg.mkPen("#4ecaff", width=1.5))
        vbox.addWidget(self.plot_widget_2)

        self.plot_widget_3 = pg.PlotWidget()
        self.plot_widget_3.setLabel("left",   "Channel 3 — VG (mV)",  **label_style)
        self.plot_widget_3.setLabel("bottom", "Time (s)",              **label_style)
        self.plot_widget_3.showGrid(x=True, y=True, alpha=0.2)
        self.plot_curve_3 = self.plot_widget_3.plot(pen=pg.mkPen("#a0ff80", width=1.5))
        vbox.addWidget(self.plot_widget_3)

    def _build_oect_tab(self):
        vbox = QVBoxLayout(self.tab_oect)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)

        label_style = {"color": "#000000", "font-size": "10pt", "font-weight": "bold"}

        self.plot_widget_4 = pg.PlotWidget()
        self.plot_widget_4.setBackground((255, 255, 255))
        self.plot_widget_4.setLabel("left",   "ID",      **label_style)
        self.plot_widget_4.setLabel("bottom", "VG (mV)", **label_style)
        self.plot_widget_4.showGrid(x=True, y=True, alpha=0.3)
        self.plot_curve_4  = self.plot_widget_4.plot(pen=pg.mkPen("#cc2222", width=1.5))
        self.plot_marker_4 = self.plot_widget_4.plot(
            pen=None, symbol="o", symbolSize=12,
            symbolBrush="#2255cc", symbolPen="#2255cc",
        )
        vbox.addWidget(self.plot_widget_4)

        self.plot_widget_5 = pg.PlotWidget()
        self.plot_widget_5.setBackground((255, 255, 255))
        self.plot_widget_5.setLabel("left",   "ID",      **label_style)
        self.plot_widget_5.setLabel("bottom", "VD (mV)", **label_style)
        self.plot_widget_5.showGrid(x=True, y=True, alpha=0.3)
        self.plot_curve_5  = self.plot_widget_5.plot(pen=pg.mkPen("#cc2222", width=1.5))
        self.plot_marker_5 = self.plot_widget_5.plot(
            pen=None, symbol="o", symbolSize=12,
            symbolBrush="#2255cc", symbolPen="#2255cc",
        )
        vbox.addWidget(self.plot_widget_5)

    # ──────────────────── BLE actions ────────────────────

    def start_scan(self):
        name = self.device_edit.text().strip()
        if not name:
            return
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Scanning…")

        self.ble_worker = BLEWorker(name)
        self.ble_worker.device_found.connect(self.on_connected)
        self.ble_worker.scan_failed.connect(self.on_scan_failed)
        self.ble_worker.rx_data.connect(self.on_rx_data)
        self.ble_worker.start()

    def on_connected(self, addr: str):
        self.scan_btn.setText("⬤  Connected")
        self.scan_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.reset_graph()

    def on_scan_failed(self):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("⬤  Scan")

    def disconnect_device(self):
        if not self.ble_worker:
            return
        asyncio.run_coroutine_threadsafe(
            self.ble_worker.disconnect(), self.ble_worker.loop
        )
        self.scan_btn.setText("⬤  Scan")
        self.scan_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

    # ──────────────────── TX / CMD ────────────────────

    def send_data(self):
        if not self.ble_worker:
            return
        text = self.tx_edit.text().strip()
        fmt  = self.format_box.currentText()
        try:
            data = bytes.fromhex(text) if fmt == "Hex" else bytes([int(text)])
        except ValueError:
            return
        asyncio.run_coroutine_threadsafe(
            self.ble_worker.write_data(data), self.ble_worker.loop
        )

    def send_cmd_data(self):
        if not self.ble_worker:
            return
        text = self.cmd_edit.text().strip()
        fmt  = self.format_box.currentText()
        try:
            data = bytes.fromhex(text) if fmt == "Hex" else bytes([int(text)])
        except ValueError:
            return
        asyncio.run_coroutine_threadsafe(
            self.ble_worker.write_cmd_data(data), self.ble_worker.loop
        )
        if data == b"\x00":
            asyncio.run_coroutine_threadsafe(
                self.ble_worker.write_data(b"\x00\x00\x00\x00\x00\x00\x00\x00"),
                self.ble_worker.loop,
            )

    # ──────────────────── RX / decode ────────────────────

    def on_rx_data(self, data: bytes):
        hex_str = " ".join(f"{b:02X}" for b in data)
        self.rx_box.append(hex_str)

        # Decode channel 1 (ID µA)
        ch1 = np.int32(int.from_bytes(data[0:2], "big", signed=True))
        ch1 = (ch1 - 650) / -10_000.0
        ch1 = ch1 * 1.77786 + 0.11202

        # Decode channel 2 (VD mV)
        ch2 = float(np.int32(int.from_bytes(data[2:4], "big", signed=True)))
        ch2 = ch2 * 0.9936 + 3.4410

        # Decode channel 3 (VG mV) — piecewise calibration
        ch3 = float(np.int32(int.from_bytes(data[4:6], "big", signed=True)))
        ch3 = ch3 * 0.9920 + 11.8900
        if ch3 < 1150:
            ch3 = ch3 * 2.0049 - 1326.0
        else:
            ch3 = ch3 * 1.9317 - 1230.9

        # BLE timestamp
        self.t_ble = np.int32(int.from_bytes(data[10:18], "big", signed=True)) / 1000.0
        if self.reset_time_request:
            self.t0 = self.t_ble
            self.reset_time_request = 0
        t = self.t_ble - self.t0

        # push buffers
        self.time_buffer.append(t)
        self.data_buffer_1.append(ch1)
        self.data_buffer_2.append(ch2)
        self.data_buffer_3.append(ch3)

        # update time-domain plots
        tl = list(self.time_buffer)
        self.plot_curve_1.setData(tl, list(self.data_buffer_1))
        self.plot_curve_2.setData(tl, list(self.data_buffer_2))
        self.plot_curve_3.setData(tl, list(self.data_buffer_3))

        # update OECT plots
        vg_l = list(self.data_buffer_3)
        vd_l = list(self.data_buffer_2)
        id_l = list(self.data_buffer_1)
        self.plot_curve_4.setData(vg_l, id_l)
        self.plot_curve_5.setData(vd_l, id_l)
        self.plot_marker_4.setData([ch3], [ch1])
        self.plot_marker_5.setData([ch2], [ch1])

        # accumulate CSV data
        self.csv_time.append(t)
        self.csv_ch1.append(ch1)
        self.csv_ch2.append(ch2)
        self.csv_ch3.append(ch3)

    # ──────────────────── Graph reset ────────────────────

    def reset_graph(self):
        self.reset_time_request = 1
        self.time_buffer.clear()
        self.data_buffer_1.clear()
        self.data_buffer_2.clear()
        self.data_buffer_3.clear()
        for curve in (
            self.plot_curve_1, self.plot_curve_2, self.plot_curve_3,
            self.plot_curve_4, self.plot_curve_5,
        ):
            curve.setData([], [])
        self.csv_time.clear()
        self.csv_ch1.clear()
        self.csv_ch2.clear()
        self.csv_ch3.clear()

    # ──────────────────── CSV export ────────────────────

    def get_unique_filename(self, base: str) -> str:
        filename = f"{base}.csv"
        counter  = 1
        while os.path.exists(filename):
            filename = f"{base}_{counter}.csv"
            counter += 1
        return filename

    def save_csv(self):
        if not self.csv_time:
            self.rx_box.append("[warn] No data to save.")
            return
        base     = self.csv_name_edit.text().strip() or "data"
        filename = self.get_unique_filename(base)
        with open(filename, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Time (s)", "CH1 — ID (µA)", "CH2 — VD (mV)", "CH3 — VG (mV)"])
            for row in zip(self.csv_time, self.csv_ch1, self.csv_ch2, self.csv_ch3):
                writer.writerow(row)
        self.rx_box.append(f"[ok] Saved → {os.path.abspath(filename)}")

    # ──────────────────── Channel config ────────────────────

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

    def _initial_enable_state(self):
        self.on_ch1_enable_changed(self.ch1_enable.checkState())
        self.on_ch2_enable_changed(self.ch2_enable.checkState())

    # ──────────────────── Loop control ────────────────────

    def start_loop(self):
        if not self.ble_worker:
            return
        self.ble_worker.loop_running = True
        interval_s  = int(self.interval_edit.text()) / 1000.0
        num_cycles  = int(self.num_cycles_edit.text())
        ch1         = self.get_ch1_config()
        ch2         = self.get_ch2_config()
        waveform    = self.waveform_sel_box.currentIndex()

        if hasattr(self, "loop_task") and self.loop_task:
            self.loop_task.cancel()

        self.loop_task = asyncio.run_coroutine_threadsafe(
            self.ble_worker.send_loop_data(ch1, ch2, waveform, interval_s, num_cycles),
            self.ble_worker.loop,
        )

    def stop_loop(self):
        if not self.ble_worker:
            return
        self.ble_worker.loop_running = False
        if hasattr(self, "loop_task") and self.loop_task:
            self.loop_task.cancel()
            self.loop_task = None


# ──────────────────────────── Entry point ────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    win = BLEApp()
    win.show()
    sys.exit(app.exec_())