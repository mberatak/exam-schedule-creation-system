# coordinator_panel.py
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QSpinBox, QGraphicsScene,QAbstractItemView, QGraphicsView, QGraphicsRectItem
)
from PySide6.QtGui import QColor, QBrush
from PySide6.QtCore import Qt
from connection import Database
from PySide6.QtGui import QPen, QColor


class CoordinatorPanel(QWidget):
    def __init__(self, db: Database, bolum_adi="Bilinmeyen Bölüm"):
        super().__init__()
        self.db = db
        self.bolum_adi = bolum_adi
        self.setWindowTitle(f"{self.bolum_adi} Koordinatör Paneli - Derslik Yönetimi")
        self.setMinimumSize(1000, 600)

        # === Form alanları ===
        self.kod_input = QLineEdit()
        self.kod_input.setPlaceholderText("Derslik Kodu (örn: 3001)")

        self.ad_input = QLineEdit()
        self.ad_input.setPlaceholderText("Derslik Adı (örn: Amfi-1)")

        self.kapasite_input = QSpinBox()
        self.kapasite_input.setRange(10, 500)
        self.kapasite_input.setValue(40)

        self.enine_input = QSpinBox()
        self.enine_input.setRange(1, 20)
        self.enine_input.setValue(7)

        self.boyuna_input = QSpinBox()
        self.boyuna_input.setRange(1, 20)
        self.boyuna_input.setValue(9)

        self.sira_input = QSpinBox()
        self.sira_input.setRange(1, 5)
        self.sira_input.setValue(3)

        self.add_btn = QPushButton("Derslik Ekle")
        self.add_btn.clicked.connect(self.add_derslik)

        self.delete_btn = QPushButton("Seçili Dersliği Sil")
        self.delete_btn.clicked.connect(self.delete_selected)

        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.clicked.connect(self.load_derslikler)

        self.visual_btn = QPushButton("Seçili Dersliği Görselleştir")
        self.visual_btn.clicked.connect(self.show_visual)

        # === Tablo ===
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Kod", "Ad", "Kapasite", "Enine", "Boyuna", "Sıra Yapısı"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        # === Görsel alan ===
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumHeight(250)

        # === Layout ===
        form1 = QHBoxLayout()
        form1.addWidget(self.kod_input)
        form1.addWidget(self.ad_input)
        form1.addWidget(self.kapasite_input)
        form1.addWidget(self.enine_input)
        form1.addWidget(self.boyuna_input)
        form1.addWidget(self.sira_input)
        form1.addWidget(self.add_btn)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.visual_btn)

        main = QVBoxLayout()
        main.addLayout(form1)
        main.addLayout(btn_layout)
        main.addWidget(self.table)
        main.addWidget(QLabel("Derslik Oturma Görseli:"))
        main.addWidget(self.view)
        self.setLayout(main)

        self.load_derslikler()

    # === Yardımcı fonksiyonlar ===
    def show_message(self, title, text, icon=QMessageBox.Information):
        msg = QMessageBox()
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.exec()

    def load_derslikler(self):
        q = "SELECT id, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi FROM derslikler WHERE bolum=%s ORDER BY id"
        try:
            rows = self.db.execute(q, (self.bolum_adi,), fetchall=True)
            self.table.setRowCount(0)
            for r in rows:
                row_pos = self.table.rowCount()
                self.table.insertRow(row_pos)
                for c, val in enumerate(r):
                    self.table.setItem(row_pos, c, QTableWidgetItem(str(val)))
            self.table.resizeColumnsToContents()
        except Exception as e:
            self.show_message("Hata", f"Derslikler yüklenemedi: {e}", QMessageBox.Critical)

    def add_derslik(self):
        kod = self.kod_input.text().strip()
        ad = self.ad_input.text().strip()
        kapasite = self.kapasite_input.value()
        enine = self.enine_input.value()
        boyuna = self.boyuna_input.value()
        sira = self.sira_input.value()

        if not (kod and ad):
            self.show_message("Eksik Bilgi", "Kod ve ad alanları boş olamaz.", QMessageBox.Warning)
            return

        q = """INSERT INTO derslikler (bolum, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi)
               VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        try:
            self.db.execute(q, (self.bolum_adi, kod, ad, kapasite, enine, boyuna, sira))
            self.show_message("Başarılı", "Derslik eklendi.")
            self.kod_input.clear()
            self.ad_input.clear()
            self.load_derslikler()
        except Exception as e:
            self.show_message("Hata", f"Ekleme başarısız: {e}", QMessageBox.Critical)

    def get_selected_row_data(self):
        sel = self.table.selectedItems()
        if not sel:
            return None
        row = sel[0].row()
        return {
            "id": self.table.item(row, 0).text(),
            "kod": self.table.item(row, 1).text(),
            "ad": self.table.item(row, 2).text(),
            "kapasite": int(self.table.item(row, 3).text()),
            "enine": int(self.table.item(row, 4).text()),
            "boyuna": int(self.table.item(row, 5).text()),
            "sira": int(self.table.item(row, 6).text())
        }

    def delete_selected(self):
        data = self.get_selected_row_data()
        if not data:
            self.show_message("Seçim Yok", "Lütfen silmek için bir derslik seçin.", QMessageBox.Warning)
            return
        if QMessageBox.question(self, "Onay", f"{data['ad']} silinsin mi?") == QMessageBox.StandardButton.Yes:
            try:
                self.db.execute("DELETE FROM derslikler WHERE id=%s", (data['id'],))
                self.show_message("Başarılı", "Derslik silindi.")
                self.load_derslikler()
            except Exception as e:
                self.show_message("Hata", f"Silme hatası: {e}", QMessageBox.Critical)

    def show_visual(self):
        data = self.get_selected_row_data()
        if not data:
            self.show_message("Seçim Yok", "Görselleştirmek için bir derslik seçin.", QMessageBox.Warning)
            return

        self.scene.clear()
        cols = data['enine']
        rows = data['boyuna']
        group = data['sira']
        box_size = 25
        gap = 5

        y_offset = 0
        for y in range(rows):
            x_offset = 0
            for x in range(cols):
                color = QColor(100, 200, 255) if (x // group) % 2 == 0 else QColor(180, 255, 180)
                rect = QGraphicsRectItem(x_offset, y_offset, box_size, box_size)
                rect.setBrush(QBrush(color))
                rect.setPen(QPen(QColor("black")))
                self.scene.addItem(rect)
                x_offset += box_size + gap
            y_offset += box_size + gap


if __name__ == "__main__":
    db = Database()
    db.connect()
    app = QApplication(sys.argv)
    win = CoordinatorPanel(db, bolum_adi="Bilgisayar Mühendisliği")
    win.show()
    sys.exit(app.exec())
