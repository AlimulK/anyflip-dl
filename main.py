import sys

from PySide6.QtCore import QSize, QRunnable, Slot, QThreadPool, QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QProgressBar,
    QLabel,
    QLineEdit,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

import pyflip
from errors import PyflipError


class WorkerSignals(QObject):
    """Signals available from the running worker thread."""

    error = Signal(str)
    finished = Signal()

class Worker(QRunnable):

    def __init__(self, url_line, keepfolder_check, prog_bar):
        super(Worker, self).__init__()
        self.url_line = url_line
        self.keepfolder_check = keepfolder_check
        self.prog_bar = prog_bar
        self.signals = WorkerSignals()

    @Slot()  # QtCore.Slot
    def run(self):
        try:
            # Make the bar run
            self.prog_bar.setMinimum(0)
            self.prog_bar.setMaximum(0)
            # Make the Flipbook object the user wants to download
            flipbook: pyflip.Flipbook = pyflip.Pyflip.prepare_download(self.url_line.text())
            # Download the images to a folder with the name of the flipbook
            pyflip.Pyflip.download_images(flipbook.title, flipbook)
            pyflip.Pyflip.create_pdf(
                flipbook.title, flipbook.title, self.keepfolder_check.isChecked()
            )
            # Delete the Flipbook object to free memory
            del flipbook
            # Make the bar stop (success)
            self.prog_bar.setMaximum(100)
            self.signals.finished.emit()
        except PyflipError as exc:
            # Stop the bar and signal the error to the GUI thread
            self.prog_bar.setMaximum(100)
            self.signals.error.emit(str(exc))
        except Exception as exc:  # Fallback for unexpected exceptions
            self.prog_bar.setMaximum(100)
            self.signals.error.emit(f"Unexpected error: {exc}")


class MainWindow(QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()

        # UI
        self.setWindowTitle("anyflip-dl")
        self.setFixedSize(QSize(400, 120))
        icon = QIcon("pyflip.ico")
        self.setWindowIcon(icon)

        self.label = QLabel("Anyflip URL:")

        self.url_line = QLineEdit()
        self.url_line.setPlaceholderText("https://anyflip.com/sdxkb/wmdh")

        self.dl_button = QPushButton("Download")
        self.dl_button.clicked.connect(self.dl_button_clicked)

        self.keepfolder_check = QCheckBox("Keep Temporary Folder")

        self.prog_bar = QProgressBar(self)
        self.prog_bar.setTextVisible(False)

        self.threadpool = QThreadPool()

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.label)
        h_layout.addWidget(self.url_line)

        v_layout = QVBoxLayout()
        v_layout.addLayout(h_layout)
        v_layout.addWidget(self.keepfolder_check)
        v_layout.addWidget(self.dl_button)
        v_layout.addWidget(self.prog_bar)

        central_widget = QWidget()
        central_widget.setLayout(v_layout)

        self.setCentralWidget(central_widget)

    # Logic
    def dl_button_clicked(self):
        worker = Worker(self.url_line, self.keepfolder_check, self.prog_bar)
        worker.signals.error.connect(self.on_worker_error)
        self.threadpool.start(worker)

    def on_worker_error(self, message: str):
        # Ensure progress bar is stopped and show error dialog
        self.prog_bar.setMaximum(100)
        QMessageBox.critical(self, "Download Error", message)


# Running the app
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
