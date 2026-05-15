import sys
import asyncio

import httpx
from PySide6.QtCore import QSize, QRunnable, Slot, QThreadPool, QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QProgressBar,
    QLabel,
    QLineEdit,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

import pyflip


class WorkerSignals(QObject):
    """Signals available from the running worker thread"""

    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, url_line, prog_bar):
        super(Worker, self).__init__()
        self.url_line = url_line
        self.prog_bar = prog_bar
        self.signals = WorkerSignals()

        # Create HTTP client
        self.client = httpx.AsyncClient(http2=True)

    @Slot()
    def run(self):
        try:
            # Make the bar run
            self.prog_bar.setMinimum(0)
            self.prog_bar.setMaximum(0)

            asyncio.run(self._download())

            # Make the bar stop (success)
            self.prog_bar.setMaximum(100)
            self.signals.finished.emit()
        except Exception as exc:
            # Stop the bar and signal the error to the GUI thread
            self.prog_bar.setMaximum(100)
            self.signals.error.emit(str(exc))

    async def _download(self) -> None:
        url: str = self.url_line.text().strip()
        if not url:
            raise ValueError("Please enter a valid Anyflip URL")

        async with self.client as client:
            config_js = await pyflip.fetch_configjs(url, client)
            flipbook = pyflip.Pyflip(url, config_js)
            await flipbook.download_pdf(client)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("anyflip-dl")
        self.setFixedSize(QSize(400, 120))
        icon = QIcon("pyflip.ico")
        self.setWindowIcon(icon)

        self.label = QLabel("Anyflip URL:")

        self.url_line = QLineEdit()
        self.url_line.setPlaceholderText("https://anyflip.com/sdxkb/wmdh")

        self.dl_button = QPushButton("Download")
        self.dl_button.clicked.connect(self.dl_button_clicked)

        self.prog_bar = QProgressBar(self)
        self.prog_bar.setTextVisible(False)

        self.threadpool = QThreadPool()

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.label)
        h_layout.addWidget(self.url_line)

        v_layout = QVBoxLayout()
        v_layout.addLayout(h_layout)
        v_layout.addWidget(self.dl_button)
        v_layout.addWidget(self.prog_bar)

        central_widget = QWidget()
        central_widget.setLayout(v_layout)

        self.setCentralWidget(central_widget)

    # Logic
    def dl_button_clicked(self):
        worker = Worker(self.url_line, self.prog_bar)
        worker.signals.error.connect(self.on_worker_error)
        worker.signals.finished.connect(self.on_worker_finished)
        # Keep a reference for completion messaging
        self.current_worker = worker
        self.threadpool.start(worker)

    def on_worker_error(self, message: str):
        # Ensure progress bar is stopped and show error dialog
        self.prog_bar.setMaximum(100)
        QMessageBox.critical(self, "Download Error", message)

    def on_worker_finished(self):
        self.prog_bar.setMaximum(100)
        QMessageBox.information(
            self,
            "Download Complete",
            "PDF downloaded successfully",
            QMessageBox.StandardButton.Ok,
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
