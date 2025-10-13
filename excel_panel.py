# excel_panel.py
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout, QMessageBox
)
from connection import Database
from excel_loader import ExcelLoader

class ExcelPanel(QWidget):
    def __init__(self, db: Database, bolum_adi="Bilinmeyen Bölüm"):
        super().__init__()
        self.db = db
        self.loader = ExcelLoader(db)
        self.bolum_adi = bolum_adi

        self.setWindowTitle(f"{bolum_adi} - Excel Yükleme Paneli")
        self.setMinimumSize(500, 300)

        self.label = QLabel("Excel Dosyası Yükleme")
        self.label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")

        self.btn_ders = QPushButton("Ders Listesi Yükle")
        self.btn_ders.clicked.connect(self.load_dersler)

        self.btn_ogrenci = QPushButton("Öğrenci Listesi Yükle")
        self.btn_ogrenci.clicked.connect(self.load_ogrenciler)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.btn_ders)
        layout.addWidget(self.btn_ogrenci)
        layout.addStretch()
        self.setLayout(layout)

    def load_dersler(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ders Listesi Seç", "", "Excel Files (*.xlsx *.xls)")
        if not path:
            return
        try:
            self.loader.load_dersler(path, self.bolum_adi)
            QMessageBox.information(self, "Başarılı", "Ders listesi başarıyla yüklendi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yükleme hatası: {e}")

    def load_ogrenciler(self):
        path, _ = QFileDialog.getOpenFileName(self, "Öğrenci Listesi Seç", "", "Excel Files (*.xlsx *.xls)")
        if not path:
            return
        try:
            self.loader.load_ogrenciler(path)
            QMessageBox.information(self, "Başarılı", "Öğrenci listesi başarıyla yüklendi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yükleme hatası: {e}")


if __name__ == "__main__":
    db = Database()
    db.connect()
    app = QApplication(sys.argv)
    win = ExcelPanel(db, bolum_adi="Bilgisayar Mühendisliği")
    win.show()
    sys.exit(app.exec())
