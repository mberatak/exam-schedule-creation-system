from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout
import sys

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Başlangıç")

        self.label = QLabel("Merhaba PySide6 👋")
        self.button = QPushButton("Tıkla!")

        self.button.clicked.connect(self.degistir)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.setLayout(layout)

    def degistir(self):
        self.label.setText("Butona tıkladın!")

app = QApplication(sys.argv)
pencere = MainWindow()
pencere.show()
sys.exit(app.exec())