from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QComboBox,
    QStackedWidget, QVBoxLayout, QHBoxLayout
)
import sys

class MyUI(QWidget):
    def __init__(self):
        super().__init__()

        # --- Combobox ---
        self.label = QLabel("Waveform:", self)
        self.waveform_sel_box = QComboBox(self)
        self.waveform_sel_box.addItems(["Triangle", "Sine", "Pulse"])

        # --- Stacked widget (your mini tabs) ---
        self.stack = QStackedWidget(self)

        # Create pages
        self.page_triangle = QLabel("Triangle Settings")
        self.page_sine = QLabel("Sine Settings")
        self.page_pulse = QLabel("Pulse Settings")

        # Add pages to stack
        self.stack.addWidget(self.page_triangle)  # index 0
        self.stack.addWidget(self.page_sine)      # index 1
        self.stack.addWidget(self.page_pulse)     # index 2

        # --- Layout ---
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.label)
        top_layout.addWidget(self.waveform_sel_box)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.stack)

        # --- Signal connection ---
        self.waveform_sel_box.currentIndexChanged.connect(self.switch_page)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyUI()
    window.show()
    sys.exit(app.exec_())