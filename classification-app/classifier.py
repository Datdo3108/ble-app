"""Inference for snn_model/model.pt (trained with 13-train_bacteria_snn.py).

Only what is needed to classify a recorded trace; nothing here trains anything. The preprocessing is
a line-for-line copy of the training script (detect_cycles -> make_segments -> encode_segment), so a
trace that is fed in here is cut and encoded exactly as the training traces were. Every setting that
the checkpoint stores (steps, thresholds, bias bins, edge fraction, ...) is read from model.pt.

    clf = SNNClassifier("snn_model/model.pt")
    result = clf.classify([(0.4, t, vd_volts), (0.5, t, vd_volts), (0.6, t, vd_volts)])
    result.best, result.probabilities
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from scipy.signal import find_peaks, medfilt
from torch import nn

MIN_SAMPLES = 50                    # same as read_trace() in training


class NoUsableData(Exception):
    """No step of the acquisition produced a segment the model can classify."""


# ---------------------------------------------------------------------------------------- network
class TemporalConvLIF(nn.Module):
    """events[B, T, 48] --Conv1d x2--> synaptic current[B, T, hidden]
       context[B, 14]   --Linear----> constant bias drive[B, hidden]
       LIF: V <- beta*V + drive + current ; spike if V >= 1 ; soft reset V -= spike
       readout: Linear(spike_count / T) -> logits.   (Layer names must match the checkpoint.)"""

    def __init__(self, n_classes, context_dim, hidden, beta, channels):
        super().__init__()
        self.beta = beta
        self.temporal = nn.Sequential(nn.Conv1d(channels, 64, 5, padding=2, bias=False), nn.ReLU(),
                                      nn.Conv1d(64, hidden, 5, padding=2, bias=False))
        self.context = nn.Linear(context_dim, hidden)
        self.readout = nn.Linear(hidden, n_classes)

    def forward(self, context, events):
        current = self.temporal(events.transpose(1, 2)).transpose(1, 2)
        drive = self.context(context)
        membrane = torch.zeros_like(drive)
        counts = torch.zeros_like(drive)
        for step in range(events.shape[1]):
            membrane = self.beta * membrane + drive + current[:, step]
            spikes = (membrane - 1.0 >= 0).to(membrane.dtype)           # threshold = 1.0
            membrane = membrane - spikes                                 # soft reset
            counts = counts + spikes
        return self.readout(counts / events.shape[1])


# ---------------------------------------------------------------------------------------- results
@dataclass
class StepResult:
    bias_V: float
    duration_s: float = 0.0
    n_cycles: int = 0
    n_segments: int = 0
    note: str = ""                                       # why the step gave no segment, if it did not
    cycles: list = field(default_factory=list)           # [{"start_s", "end_s"}] seconds from the first sample
    t_first: float = 0.0                                 # time of the first sample used (same clock as the input)


@dataclass
class Prediction:
    probabilities: dict          # label -> mean softmax probability over all segments of all steps
    best: str
    n_segments: int
    steps: list                  # one StepResult per input trace


# ---------------------------------------------------------------------------------------- classifier
class SNNClassifier:
    def __init__(self, path):
        ck = torch.load(Path(path), map_location="cpu", weights_only=True)
        self.labels = list(ck["labels"])
        m, enc, pre = ck["model"], ck["encoder"], ck["preprocessing"]
        self.steps = int(enc["steps"])
        self.thresholds = np.asarray(enc["thresholds"], dtype=float)
        self.bias_bins = int(enc["bias_bins"])
        self.log_ref = float(enc["log_duration_ref_s"])
        self.min_prom = float(pre["min_prominence_V"])
        self.min_cycles = int(pre["min_cycles"])
        self.edge = float(pre["edge_fraction"])
        self.nonfiring_s = float(pre["nonfiring_window_s"])
        self.context_dim, self.channels = int(m["context_dim"]), int(m["channels"])
        self.net = TemporalConvLIF(len(self.labels), self.context_dim, m["hidden"], m["beta"], self.channels)
        self.net.load_state_dict(ck["state_dict"])
        self.net.eval()
        if self.channels != 3 * len(self.thresholds) or self.context_dim != self.bias_bins + 1:
            raise ValueError("model.pt: channels / context size do not match the encoder settings")

    # ---- 1. trace hygiene (read_trace without the CSV part)
    @staticmethod
    def clean_trace(t, v):
        """Longest uninterrupted block with increasing time; NaNs dropped. Returns (t, v) or raises ValueError."""
        t, v = np.asarray(t, float), np.asarray(v, float)
        ok = np.isfinite(t) & np.isfinite(v)
        t, v = t[ok], v[ok]
        if len(t) < MIN_SAMPLES:
            raise ValueError(f"only {len(t)} valid samples")
        cuts = np.r_[0, np.flatnonzero(np.diff(t) <= 0) + 1, len(t)]
        lo, hi = max(zip(cuts[:-1], cuts[1:]), key=lambda p: p[1] - p[0])
        if hi - lo < MIN_SAMPLES:
            raise ValueError("the time stamps never run continuously for long enough")
        return t[lo:hi], v[lo:hi]

    # ---- 2. cycle detection (copy of detect_cycles)
    def detect_cycles(self, t, y):
        dt = float(np.median(np.diff(t)))
        smooth = medfilt(y, kernel_size=max(3, 2 * int(round(0.03 / dt)) + 1))
        min_gap = max(2, int(round(0.12 / dt)))
        peaks, _ = find_peaks(smooth, prominence=self.min_prom, distance=min_gap)
        valleys, _ = find_peaks(-smooth, prominence=self.min_prom, distance=min_gap)
        span = t[-1] - t[0]
        cycles = []
        for left, right in zip(valleys[:-1], valleys[1:]):
            inside = peaks[(peaks > left) & (peaks < right)]
            if len(inside) == 0:
                continue
            peak = inside[np.argmax(smooth[inside])]
            if smooth[peak] - max(smooth[left], smooth[right]) < self.min_prom:
                continue
            if t[left] < t[0] + self.edge * span or t[right] > t[0] + (1 - self.edge) * span:
                continue
            period = t[right] - t[left]
            amplitude = smooth[peak] - (smooth[left] + smooth[right]) / 2
            if amplitude >= self.min_prom and 0.15 <= period <= 30:
                cycles.append({"start_s": float(t[left] - t[0]), "end_s": float(t[right] - t[0])})
        kept, run = [], []
        for cy in cycles:
            if run and abs(cy["start_s"] - run[-1]["end_s"]) > 2 * dt:
                if len(run) >= self.min_cycles:
                    kept += run
                run = []
            run.append(cy)
        if len(run) >= self.min_cycles:
            kept += run
        return kept

    # ---- 3. segmentation (copy of make_segments)
    def make_segments(self, t, cycles):
        segs = []
        if len(cycles) >= 6:
            size = 5 if len(cycles) >= 10 else 3
            for i in range(len(cycles) // size):
                group = cycles[i * size:(i + 1) * size]
                segs.append({"start_s": min(c["start_s"] for c in group), "end_s": max(c["end_s"] for c in group)})
            return segs, ""
        if cycles:
            return [], "firing, but fewer than 6 cycles"
        duration = t[-1] - t[0]
        starts = np.arange(t[0] + self.edge * duration,
                           t[0] + (1 - self.edge) * duration - self.nonfiring_s + 1e-9, self.nonfiring_s)
        for s in starts:
            if ((t >= s) & (t < s + self.nonfiring_s)).sum() >= 10:
                segs.append({"start_s": float(s - t[0]), "end_s": float(s + self.nonfiring_s - t[0])})
        return segs, "" if segs else "no spikes and too short for a 10 s window"

    # ---- 4. level-crossing encoding (copy of encode_segment)
    def encode_segment(self, t, v, start, end, bias_V):
        n = len(self.thresholds)
        wave = np.interp(np.linspace(start, end, self.steps), t, v)
        before, after = wave[:-1, None], wave[1:, None]
        raster = np.zeros((self.steps, self.channels), dtype=np.float32)
        raster[1:, :n] = (before < self.thresholds) & (after >= self.thresholds)
        raster[1:, n:2 * n] = (before > self.thresholds) & (after <= self.thresholds)
        initial_bin = min(n - 1, max(0, int(np.searchsorted(self.thresholds, wave[0]))))
        raster[0, 2 * n + initial_bin] = 1
        context = np.zeros(self.context_dim, dtype=np.float32)
        context[int(round(bias_V * 10))] = 1
        context[-1] = np.log1p(end - start) / np.log1p(self.log_ref)
        return raster, context

    # ---- 5. classify one acquisition
    def classify(self, traces) -> Prediction:
        """traces: [(bias_V, time_s, vd_volts), ...], one per gate-voltage step.
        Every segment of every step is classified; the answer is the mean of the softmax outputs."""
        rasters, contexts, steps = [], [], []
        for bias, t, v in traces:
            st = StepResult(bias_V=float(bias))
            steps.append(st)
            if not 0 <= round(bias * 10) < self.bias_bins:
                st.note = f"bias {bias} V is outside the 0-1.2 V range of the model"
                continue
            try:
                t, v = self.clean_trace(t, v)
            except ValueError as err:
                st.note = str(err)
                continue
            st.duration_s, st.t_first = float(t[-1] - t[0]), float(t[0])
            st.cycles = self.detect_cycles(t, v)
            st.n_cycles = len(st.cycles)
            segs, st.note = self.make_segments(t, st.cycles)
            st.n_segments = len(segs)
            for s in segs:
                r, c = self.encode_segment(t, v, t[0] + s["start_s"], t[0] + s["end_s"], bias)
                rasters.append(r); contexts.append(c)
        if not rasters:
            raise NoUsableData("; ".join(f"{s.bias_V:.1f} V: {s.note or 'no data'}" for s in steps))
        with torch.no_grad():
            prob = torch.softmax(self.net(torch.tensor(np.stack(contexts)), torch.tensor(np.stack(rasters))), 1)
        mean = prob.mean(0).numpy()
        probs = {name: float(mean[i]) for i, name in enumerate(self.labels)}
        return Prediction(probs, max(probs, key=probs.get), len(rasters), steps)
