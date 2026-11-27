"""Prediction tab for main-24h.py: acquire at several gate voltages, then classify with snn_model/model.pt.

Flow (design taken from oect_app_predict.py, rebuilt without its config/features modules):
  1. "Auto acquire": for every step the drain-current and gate DAC codes you typed are written to the
     board (same 2 x uint16 packet as the CH1/CH2 constant boxes), VD (CH2) is recorded for the step
     length and saved to data/auto/<time>/auto <Vg>V.csv (same columns as the training files).
  2. "Start classification": the SNN classifies every segment of every step; the cards show the mean
     probability and a frame runs over them and stops on the winner.
The DAC codes are raw numbers, never converted: nothing is sent until you have typed them in.
"""
from __future__ import annotations

import torch  # noqa: F401  (must be imported before PyQt5 on Windows, otherwise c10.dll fails: WinError 1114)

import asyncio
import csv
import datetime as dt
import time
from collections import deque
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QEvent, QObject, Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence, QPixmap
from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                             QProgressBar, QPushButton, QShortcut, QVBoxLayout, QWidget)

from classifier import NoUsableData, SNNClassifier

HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE / "snn_model" / "model.pt"
ASSETS = HERE / "assets"
SAVE_DIR = HERE / "data" / "auto"

# ---- board protocol (as in the reference app's config.py; marked "confirm" there)  <-- confirm
AUTO_START_CMD = b"\x02"        # command characteristic: "02: inject current" (main-24h.py)
CURRENT_CHANNEL = 1             # which constant box / packet half sets the drain current (1 or 2)
GATE_CHANNEL = 2                # which one sets the gate voltage (1 or 2)

DEFAULT_VGS = ("0.4", "0.5", "0.6")   # bias of each step: this is the label the model gets, not a DAC value
DEFAULT_DURATION_S = "15"
DISPLAY_S = 60.0                      # seconds of VD shown while idle
TILE_W, TILE_H = 200, 189

# model label (lower case, no "-") -> (picture stem in assets/, display text, bar colour)
CLASS_INFO = {
    "mr1":     ("MR-1",    "<i>Shewanella oneidensis</i> MR-1",         "#E57373"),
    "mutant":  ("Mutant",  "<i>Shewanella oneidensis</i> MR-1 mutant",  "#A98BD3"),
    "ec":      ("EC",      "<i>Escherichia coli</i>",                   "#7FB2DC"),
    "sa":      ("SA",      "<i>Staphylococcus aureus</i>",              "#F2B35E"),
    "pa":      ("PA",      "<i>Pseudomonas aeruginosa</i>",             "#8BC48A"),
    "abiotic": ("Abiotic", "Abiotic",                                   "#BDBDBD"),
}
CARD_ORDER = ["mr1", "mutant", "ec", "sa", "pa", "abiotic"]
VGS_HTML = "<i>V</i><sub>gs</sub>"
BLUE, RED, PURPLE = "#6FA8DC", "#F2849E", "#B39DDB"


def _key(label: str) -> str:
    return label.lower().replace("-", "").replace("_", "")


def _info(label: str):
    return CLASS_INFO.get(_key(label), (label, label, "#9E9E9E"))


class PredictionTab(QWidget):
    def __init__(self, host):
        """host: the BLEApp window (gives access to the BLE worker, the CH1/CH2 boxes and the log)."""
        super().__init__(host)
        self.host = host
        self.clf = None
        self.disp_t, self.disp_v = deque(maxlen=6000), deque(maxlen=6000)
        self.vg_hist = deque(maxlen=5)
        self.view, self.t_origin, self.y_range = "live", None, None   # "live" | "acq" | "frozen"
        self.steps, self.rec = [], []          # planned steps [(vg, gate_code)], recorded data per step
        self.step_i, self.cur_code, self.duration = None, 0, 15.0
        self.acq_done, self.markers = False, []
        self.presenting, self._hidden = False, []
        self._build()
        self.load_model()
        self.step_timer = QTimer(self)
        self.step_timer.setSingleShot(True)
        self.step_timer.timeout.connect(self._next_step)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(100)
        QShortcut(QKeySequence("F11"), host, self.toggle_present)
        QShortcut(QKeySequence("Esc"), host, lambda: self.presenting and self.toggle_present())
        host.installEventFilter(self)          # keep the tab widget full size in full-screen mode

    # ------------------------------------------------------------------------------ layout
    def _build(self):
        big, mid = QFont(), QFont()
        big.setPointSize(16); big.setBold(True)
        mid.setPointSize(11)
        root = QVBoxLayout(self)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        heading = QLabel("Bacteria identification")
        heading.setFont(big)
        self.title = QLabel("")
        self.title.setFont(mid)
        titles.addWidget(heading); titles.addWidget(self.title)
        head.addLayout(titles); head.addStretch(1)
        for name in ("logo_idmxs.png", "logo_ntu.png"):
            lab = QLabel()
            lab.setFixedSize(240, 90)
            lab.setAlignment(Qt.AlignCenter)
            pm = QPixmap(str(ASSETS / name))
            if pm.isNull():
                lab.setText(name); lab.setStyleSheet("color: #999; border: 1px dashed #bbb;")
            else:
                lab.setPixmap(pm.scaled(240, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            head.addWidget(lab)
        root.addLayout(head)

        self.status = QLabel("Waiting for data…")
        self.status.setFont(mid)
        root.addWidget(self.status)

        # white plot, soft-blue trace
        self.p_trace = pg.PlotWidget()
        self.p_trace.setBackground("w")
        for ax in ("left", "bottom"):
            self.p_trace.getAxis(ax).setPen(pg.mkPen("#9E9E9E"))
            self.p_trace.getAxis(ax).setTextPen(pg.mkPen("#424242"))
        style = {"color": "#424242", "font-size": "12pt"}
        self.p_trace.setLabel("left", "<i>V</i><sub>ds</sub> (CH2)", units="V", **style)
        self.p_trace.setLabel("bottom", "Time", units="s", **style)
        self.p_trace.showGrid(x=True, y=True, alpha=0.15)
        self.p_trace.disableAutoRange()
        self.c_trace = self.p_trace.plot(pen=pg.mkPen(BLUE, width=2.2), antialias=False)
        self.c_cycles = self.p_trace.plot(pen=None, symbol="o", symbolSize=9, symbolBrush=RED,
                                          symbolPen=pg.mkPen("w", width=1))
        self.banner = pg.TextItem("", color="#2E9E6A", anchor=(0.5, 0.5), fill=pg.mkBrush(255, 255, 255, 225),
                                  border=pg.mkPen("#4CAF84", width=2))
        self.banner.setFont(QFont("Arial", 26, QFont.Bold))
        self.p_trace.addItem(self.banner, ignoreBounds=True)
        root.addWidget(self.p_trace, 5)

        # acquisition settings: raw DAC codes, typed by the user (nothing is converted or assumed)
        grid = QGridLayout()
        self.vg_edits, self.code_edits = [], []
        grid.addWidget(QLabel("Step"), 0, 0)
        grid.addWidget(QLabel(f"{VGS_HTML} (V) - bias given to the model"), 1, 0)
        grid.addWidget(QLabel("Gate DAC code (empty = skip step)"), 2, 0)
        for i, vg in enumerate(DEFAULT_VGS):
            grid.addWidget(QLabel(str(i + 1)), 0, i + 1, Qt.AlignCenter)
            e1, e2 = QLineEdit(vg), QLineEdit()
            e2.setPlaceholderText("code")
            self.vg_edits.append(e1); self.code_edits.append(e2)
            grid.addWidget(e1, 1, i + 1); grid.addWidget(e2, 2, i + 1)
        grid.addWidget(QLabel("Drain-current DAC code"), 0, 4)
        self.current_edit = QLineEdit()
        self.current_edit.setPlaceholderText("code")
        grid.addWidget(self.current_edit, 1, 4)
        grid.addWidget(QLabel("Seconds per step"), 2, 4)
        self.duration_edit = QLineEdit(DEFAULT_DURATION_S)
        grid.addWidget(self.duration_edit, 2, 5)
        for lab in self.findChildren(QLabel):
            lab.setTextFormat(Qt.RichText)
        root.addLayout(grid)

        ctl = QHBoxLayout()
        self.acq_btn = QPushButton("Auto acquire")
        self.start_btn = QPushButton("Start classification")
        self.present_btn = QPushButton("Full screen")
        for b in (self.acq_btn, self.start_btn, self.present_btn):
            b.setMinimumHeight(36); b.setFont(mid)
        self.acq_btn.clicked.connect(self.toggle_acquisition)
        self.start_btn.clicked.connect(self.start_classification)
        self.present_btn.clicked.connect(self.toggle_present)
        ctl.addWidget(self.acq_btn); ctl.addStretch(1); ctl.addWidget(self.present_btn); ctl.addWidget(self.start_btn)
        root.addLayout(ctl)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setMinimumHeight(26)
        root.addWidget(self.progress)
        self.progress_text = QLabel("Type the DAC codes, press “Auto acquire”; when the data are complete "
                                    "press “Start classification”.")
        self.progress_text.setFont(mid)
        root.addWidget(self.progress_text)
        self.result = QLabel("")
        self.result.setFont(big)
        self.result.setAlignment(Qt.AlignCenter)
        root.addWidget(self.result)
        for lab in (self.title, self.status, self.progress_text, self.result):
            lab.setTextFormat(Qt.RichText)

        self.cards_row = QHBoxLayout()
        root.addLayout(self.cards_row)
        self.tiles, self.bars, self.pics = {}, {}, {}

    def _build_cards(self):
        """One card per class of the loaded model (picture, name, probability bar)."""
        mid = QFont(); mid.setPointSize(11)
        labels = sorted(self.clf.labels, key=lambda l: CARD_ORDER.index(_key(l)) if _key(l) in CARD_ORDER else 99)
        self.order = labels
        for c in labels:
            stem, text, colour = _info(c)
            card = QFrame(); card.setObjectName("tile")
            lay = QVBoxLayout(card); lay.setContentsMargins(6, 6, 6, 6)
            pic = QLabel(); pic.setAlignment(Qt.AlignCenter)
            name = QLabel(text); name.setTextFormat(Qt.RichText); name.setAlignment(Qt.AlignCenter)
            name.setWordWrap(True); name.setFont(mid)
            bar = QProgressBar(); bar.setRange(0, 1000); bar.setFormat("–"); bar.setMaximumHeight(18)
            bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {colour}; }} QProgressBar {{ text-align: center; }}")
            lay.addWidget(pic); lay.addWidget(name); lay.addWidget(bar)
            self.cards_row.addWidget(card)
            self.tiles[c], self.bars[c], self.pics[c] = card, bar, pic
        self.set_tile_size(TILE_W, TILE_H)
        self.highlight(None)

    def set_tile_size(self, w, h):
        for c, pic in self.pics.items():
            pm = QPixmap(str(ASSETS / f"{_info(c)[0]}_pic.png"))
            if pm.isNull():
                pic.setText(f"{_info(c)[0]}_pic.png"); pic.setStyleSheet("color: #999;"); pic.setMinimumSize(w, h)
            else:
                pic.setPixmap(pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def highlight(self, cls, final=False):
        for c, card in self.tiles.items():
            if c == cls:
                colour, width = ("#4CAF84", 5) if final else (RED, 4)
            else:
                colour, width = "#E0E0E0", 1
            card.setStyleSheet(f"QFrame#tile {{ border: {width}px solid {colour}; border-radius: 12px; "
                               f"background: white; padding: {5 - width}px; }}")

    # ------------------------------------------------------------------------------ model
    def load_model(self):
        try:
            self.clf = SNNClassifier(MODEL_PATH)
        except Exception as err:                                  # noqa: BLE001
            self.progress_text.setText(f"Could not load the model {MODEL_PATH.name} ({err})")
            self.acq_btn.setEnabled(False); self.start_btn.setEnabled(False)
            return
        self._build_cards()
        self.title.setText("Spiking neural network (LIF), classes: " + ", ".join(_info(c)[0] for c in self.order))

    # ------------------------------------------------------------------------------ data in (called for every BLE packet)
    def add_sample(self, t: float, vd: float, vg: float, i_d: float = np.nan):
        """t: board clock (s); vd, vg in V (CH2, CH3); i_d as shown in the Channel-1 plot."""
        self.vg_hist.append(vg)
        if self.view != "frozen":
            if self.view == "acq":
                if self.t_origin is None:
                    self.t_origin = t
                self.disp_t.append(t - self.t_origin)
            else:
                self.disp_t.append(t)
            self.disp_v.append(vd)
        if self.step_i is not None:
            r = self.rec[self.step_i]
            r["t"].append(t); r["vd_mV"].append(vd * 1000.0); r["vg_mV"].append(vg * 1000.0); r["id"].append(i_d)

    # ------------------------------------------------------------------------------ BLE helpers
    def connected(self) -> bool:
        w = self.host.ble_worker
        return bool(w and w.client and w.client.is_connected)

    def _send(self, coro):
        asyncio.run_coroutine_threadsafe(coro, self.host.ble_worker.loop)

    # ------------------------------------------------------------------------------ acquisition
    def _read_settings(self):
        """Return (steps, current_code, duration) or raise ValueError with a message for the user."""
        def code(text, what):
            try:
                c = int(text.strip())
            except ValueError:
                raise ValueError(f"{what}: type an integer DAC code")
            if not -32768 <= c <= 65535:
                raise ValueError(f"{what}: code {c} does not fit in 16 bits")
            return c
        cur = code(self.current_edit.text(), "Drain-current DAC code")
        try:
            duration = float(self.duration_edit.text())
        except ValueError:
            raise ValueError("Seconds per step must be a number")
        if duration <= 0:
            raise ValueError("Seconds per step must be positive")
        steps = []
        for i, (ev, ec) in enumerate(zip(self.vg_edits, self.code_edits)):
            if not ec.text().strip():
                continue
            try:
                vg = float(ev.text())
            except ValueError:
                raise ValueError(f"Step {i + 1}: Vg must be a number")
            if not 0 <= round(vg * 10) <= 12:
                raise ValueError(f"Step {i + 1}: Vg must be between 0 and 1.2 V (range of the model's bias encoding)")
            steps.append((vg, code(ec.text(), f"Step {i + 1} gate DAC code")))
        if not steps:
            raise ValueError("Type at least one gate DAC code")
        return steps, cur, duration

    def toggle_acquisition(self):
        if self.step_i is not None:                               # running -> stop
            self.step_timer.stop()
            self._finish(False, "Stopped by the user.")
            return
        if not self.connected():
            self.progress_text.setText("Not connected – press Scan first.")
            return
        try:
            steps, cur, duration = self._read_settings()
        except ValueError as err:
            self.progress_text.setText(str(err))
            return
        if getattr(self.host, "loop_task", None):                 # a running waveform loop would fight the constants
            self.host.stop_loop()
        self.steps, self.cur_code, self.duration = steps, cur, duration
        self.rec = [{"t": [], "vd_mV": [], "vg_mV": [], "id": []} for _ in steps]
        self.acq_done, self.t_origin, self.y_range, self.view = False, None, None, "acq"
        self.disp_t.clear(); self.disp_v.clear()
        self.c_trace.setData([], []); self.c_cycles.setData([], [])
        self.banner.setText(""); self.clear_result()
        for m in self.markers:
            self.p_trace.removeItem(m)
        self.markers = []
        self.p_trace.setXRange(0, duration * len(steps), padding=0)
        self.acq_btn.setText("Stop acquisition"); self.start_btn.setEnabled(False)
        self.host.tabs.setCurrentWidget(self)
        # same fields a user would type: constant mode on both channels
        self.host.ch1_enable.setChecked(False)
        self.host.ch2_enable.setChecked(False)
        self._send(self.host.ble_worker.write_cmd_data(AUTO_START_CMD))
        self.step_i = -1
        self._next_step()

    def _next_step(self):
        self.step_i += 1
        if self.step_i >= len(self.steps):
            self._finish(True)
            return
        vg, gate = self.steps[self.step_i]
        codes = {CURRENT_CHANNEL: self.cur_code, GATE_CHANNEL: gate}
        self.host.ch1_value_edit.setText(str(codes[1]))
        self.host.ch2_value_edit.setText(str(codes[2]))
        v1, v2 = (c if c >= 0 else c + 65536 for c in (codes[1], codes[2]))
        self._send(self.host.ble_worker.write_data(v1.to_bytes(2, "big") + v2.to_bytes(2, "big")))
        line = pg.InfiniteLine(pos=self.disp_t[-1] if self.disp_t else 0.0, angle=90,
                               pen=pg.mkPen(PURPLE, width=1.5, style=Qt.DashLine),
                               label=f"{vg:.1f} V", labelOpts={"position": 0.95, "color": "#7E57C2"})
        self.p_trace.addItem(line); self.markers.append(line)
        self.host.rx_box.append(f"Auto acquire: step {self.step_i + 1}/{len(self.steps)}, bias {vg:.1f} V, "
                                f"current code {self.cur_code}, gate code {gate}, {self.duration:g} s")
        self.step_timer.start(int(self.duration * 1000))

    def _seconds(self, i):
        t = self.rec[i]["t"]
        return t[-1] - t[0] if len(t) > 1 else 0.0

    def _finish(self, ok: bool, note: str = ""):
        self.step_i = None
        self._draw()                                              # last samples, even if the tab was hidden meanwhile
        self.view = "frozen"
        self.acq_btn.setText("Auto acquire"); self.start_btn.setEnabled(True)
        if not ok:
            self.progress_text.setText(f"Acquisition stopped. {note}")
            return
        short = [self.steps[i][0] for i in range(len(self.steps)) if self._seconds(i) < self.duration - 1.0]
        if short:
            self.progress_text.setText(f"Too little data at {VGS_HTML} = " + ", ".join(f"{v:.1f} V" for v in short)
                                       + " – check the Bluetooth connection and acquire again.")
            return
        folder = self.save_acquisition()
        self.acq_done = True
        self.banner.setText("  Data acquisition complete  ")
        self._place_banner()
        self.progress_text.setText(f"Data acquisition complete (saved to {folder}). Press “Start classification”.")

    def save_acquisition(self) -> Path:
        """CSV per step with the training-file columns; the bias is in the file name like the training files."""
        folder = SAVE_DIR / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder.mkdir(parents=True, exist_ok=True)
        for (vg, _), r in zip(self.steps, self.rec):
            with open(folder / f"auto {vg:.1f}V.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Time (s)", "Channel 1 (mA)", "Channel 2 (mV)", "Channel 3 (mV)"])
                t0 = r["t"][0] if r["t"] else 0.0
                w.writerows((t - t0, i, vd, vg_) for t, i, vd, vg_ in zip(r["t"], r["id"], r["vd_mV"], r["vg_mV"]))
        return folder

    # ------------------------------------------------------------------------------ classification
    def clear_result(self):
        self.progress.setValue(0)
        self.result.setText("")
        self.highlight(None)
        for bar in self.bars.values():
            bar.setValue(0); bar.setFormat("–")

    def start_classification(self):
        if self.clf is None:
            self.progress_text.setText("No model loaded.")
            return
        if self.step_i is not None:
            self.progress_text.setText("Acquisition still running – wait for “Data acquisition complete”.")
            return
        if not self.acq_done:
            self.progress_text.setText("No complete acquisition yet – press “Auto acquire” first.")
            return
        traces = [(vg, np.array(r["t"]), np.array(r["vd_mV"]) / 1000.0)      # the model works in volts
                  for (vg, _), r in zip(self.steps, self.rec)]
        try:
            pred = self.clf.classify(traces)
        except NoUsableData as err:
            self.progress_text.setText(f"No usable data ({err}) – acquire again.")
            return
        self._mark_cycles(pred)
        self.clear_result()
        self.spin(pred.best, lambda: self.reveal(pred))

    def _mark_cycles(self, pred):
        """Red dots at the start of every spike cycle the model saw (on the frozen trace)."""
        xs, ys = [], []
        for st, r in zip(pred.steps, self.rec):
            if not st.cycles:
                continue
            t, v = np.array(r["t"]), np.array(r["vd_mV"]) / 1000.0
            for c in st.cycles:
                tc = st.t_first + c["start_s"]
                xs.append(tc - self.t_origin); ys.append(float(np.interp(tc, t, v)))
        self.c_cycles.setData(xs, ys)

    def spin(self, best, done):
        """Frame runs over the cards, fast then slowing, and stops on `best`; fills the progress bar."""
        n = len(self.order)
        path = [self.order[i % n] for i in range(2 * n + self.order.index(best) + 1)]
        delays = [int(60 + 340 * (k / (len(path) - 1)) ** 2.5) for k in range(len(path))]
        self.start_btn.setEnabled(False); self.acq_btn.setEnabled(False)
        self.progress_text.setText("Classifying…")
        state = {"k": 0}

        def step():
            k = state["k"]
            self.highlight(path[k])
            self.progress.setValue(int(100 * (k + 1) / len(path)))
            state["k"] += 1
            if state["k"] < len(path):
                QTimer.singleShot(delays[k], step)
            else:
                QTimer.singleShot(250, done)
        step()

    def reveal(self, pred):
        best = pred.best
        self.highlight(best, final=True)
        for c in self.order:
            p = pred.probabilities.get(c, 0.0)
            self.bars[c].setValue(int(round(p * 1000))); self.bars[c].setFormat(f"{p:.0%}")
        self.result.setText(f"{_info(best)[1]}&nbsp;&nbsp;&nbsp;{pred.probabilities[best]:.0%}")
        self.progress.setValue(100)
        sp = "&nbsp;&nbsp;·&nbsp;&nbsp;"
        per = sp.join(f"{VGS_HTML} = {s.bias_V:.1f} V: {s.n_cycles} cycles → {s.n_segments} seg." if s.n_segments
                      else f"{VGS_HTML} = {s.bias_V:.1f} V: unused ({s.note})" for s in pred.steps)
        self.progress_text.setText(f"Done – mean over {pred.n_segments} segments.&nbsp;&nbsp;&nbsp;{per}")
        self.start_btn.setEnabled(True); self.acq_btn.setEnabled(True)

    # ------------------------------------------------------------------------------ periodic update
    def refresh(self):
        if self.isVisible():                                      # hidden tab: nothing to draw yet
            self._draw()

    def _draw(self):
        if len(self.disp_t) < 2 or self.view == "frozen":
            return
        t, v = np.fromiter(self.disp_t, float), np.fromiter(self.disp_v, float)
        if self.view == "live":
            keep = t >= t[-1] - DISPLAY_S
            t, v = t[keep], v[keep]
            self.p_trace.setXRange(t[-1] - DISPLAY_S, t[-1], padding=0)
        self.c_trace.setData(t, v)
        if self.y_range is None or len(t) % 20 == 0:
            self._update_y(v)
        msg = f"{VGS_HTML} (CH3): {float(np.median(self.vg_hist)):.3f} V"
        if self.step_i is not None and self.step_i < len(self.steps):
            msg += (f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Acquiring step {self.step_i + 1}/{len(self.steps)} at "
                    f"{VGS_HTML} = {self.steps[self.step_i][0]:.1f} V: {self._seconds(self.step_i):.1f}/{self.duration:g} s")
            self.progress.setValue(int(100 * min(1.0, self.disp_t[-1] / (self.duration * len(self.steps)))))
        self.status.setText(msg)

    def _update_y(self, v):
        """Move the voltage axis only when data leave it or fill much less of it (no jitter)."""
        lo, hi = float(np.nanmin(v)), float(np.nanmax(v))
        pad = max(0.05 * (hi - lo), 0.02)
        want = (lo - pad, hi + pad)
        cur = self.y_range
        if cur is None or want[0] < cur[0] or want[1] > cur[1] or (want[1] - want[0]) < 0.6 * (cur[1] - cur[0]):
            self.y_range = want
            self.p_trace.setYRange(*want, padding=0)

    def _place_banner(self):
        if self.y_range:
            x_lo, x_hi = self.p_trace.viewRange()[0]
            self.banner.setPos((x_lo + x_hi) / 2, (self.y_range[0] + self.y_range[1]) / 2)

    # ------------------------------------------------------------------------------ full-screen (presentation) mode
    def toggle_present(self):
        h = self.host
        if not self.presenting:
            self._hidden = [w for w in h.children() if isinstance(w, QWidget) and w is not h.tabs and w.isVisible()]
            for w in self._hidden:
                w.hide()
            self._tabs_geom = h.tabs.geometry()
            h.tabs.tabBar().hide()
            h.tabs.setCurrentWidget(self)
            self.presenting = True
            self.present_btn.setText("Exit full screen")
            h.showFullScreen()
            scr = QApplication.primaryScreen().size()
            w = int(min(0.2 * scr.width(), 0.24 * scr.height()))
            self.set_tile_size(w, int(w * TILE_H / TILE_W))
        else:
            for w in self._hidden:
                w.show()
            h.tabs.tabBar().show()
            h.tabs.setGeometry(self._tabs_geom)
            self.presenting = False
            self.present_btn.setText("Full screen")
            self.set_tile_size(TILE_W, TILE_H)
            h.showNormal(); h.showMaximized()
        self._fit()

    def _fit(self):
        if self.presenting:
            self.host.tabs.setGeometry(self.host.rect().adjusted(10, 6, -10, -6))

    def eventFilter(self, obj, event):
        if obj is self.host and event.type() == QEvent.Resize:
            self._fit()
        return False
