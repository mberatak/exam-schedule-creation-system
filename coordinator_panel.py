# coordinator_panel.py (güncellenmiş)
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QSpinBox, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QFileDialog, QFrame, QDialog, QDateEdit, QTextEdit, QAbstractItemView
)
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtCore import Qt, QDate
from connection import Database
from excel_loader import ExcelLoader
from exam_scheduler import ExamScheduler
from datetime import date


class CoordinatorPanel(QWidget):
    def __init__(self, db: Database, bolum_adi="Bilinmeyen Bölüm"):
        super().__init__()
        self.db = db
        self.bolum_adi = bolum_adi
        self.setWindowTitle(f"{self.bolum_adi} Koordinatör Paneli - Derslik ve Sınav Yönetimi")
        self.setMinimumSize(1100, 750)

        self.loader = ExcelLoader(db)

        # === Derslik form alanları ===
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

        self.add_btn = QPushButton(" Derslik Ekle")
        self.add_btn.clicked.connect(self.add_derslik)

        self.delete_btn = QPushButton(" Seçili Dersliği Sil")
        self.delete_btn.clicked.connect(self.delete_selected)

        self.refresh_btn = QPushButton(" Yenile")
        self.refresh_btn.clicked.connect(self.load_derslikler)

        self.visual_btn = QPushButton(" Görselleştir")
        self.visual_btn.clicked.connect(self.show_visual)

        self.load_ders_excel_btn = QPushButton("Ders Listesi Yükle (Excel)")
        self.load_ders_excel_btn.clicked.connect(self.load_ders_excel)

        self.load_ogr_excel_btn = QPushButton(" Öğrenci Listesi Yükle (Excel)")
        self.load_ogr_excel_btn.clicked.connect(self.load_ogr_excel)

        self.generate_exam_btn = QPushButton(" Sınav Takvimi Oluştur")
        self.generate_exam_btn.clicked.connect(self.open_exam_window)

        # === Tablo ===
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Kod", "Ad", "Kapasite", "Enine", "Boyuna", "Sıra Yapısı"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumHeight(250)

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

        excel_layout = QHBoxLayout()
        excel_layout.addWidget(self.load_ders_excel_btn)
        excel_layout.addWidget(self.load_ogr_excel_btn)
        excel_layout.addWidget(self.generate_exam_btn)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)

        main = QVBoxLayout()
        main.addLayout(form1)
        main.addLayout(btn_layout)
        main.addWidget(line)
        main.addLayout(excel_layout)
        main.addWidget(QLabel(" Derslik Listesi"))
        main.addWidget(self.table)
        main.addWidget(QLabel("Derslik Oturma Görseli:"))
        main.addWidget(self.view)
        self.setLayout(main)

        self.load_derslikler()

    # === Yardımcılar ===
    def show_message(self, title, text, icon=QMessageBox.Information):
        msg = QMessageBox(self)
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

    def delete_selected(self):
        sel = self.table.selectedItems()
        if not sel:
            self.show_message("Seçim Yok", "Lütfen silmek için bir derslik seçin.", QMessageBox.Warning)
            return
        row = sel[0].row()
        derslik_id = self.table.item(row, 0).text()
        ad = self.table.item(row, 2).text()
        if QMessageBox.question(self, "Onay", f"{ad} silinsin mi?") == QMessageBox.Yes:
            try:
                self.db.execute("DELETE FROM derslikler WHERE id=%s", (derslik_id,))
                self.show_message("Başarılı", "Derslik silindi.")
                self.load_derslikler()
            except Exception as e:
                self.show_message("Hata", f"Silme hatası: {e}", QMessageBox.Critical)

    def show_visual(self):
        sel = self.table.selectedItems()
        if not sel:
            self.show_message("Seçim Yok", "Görselleştirmek için bir derslik seçin.", QMessageBox.Warning)
            return

        row = sel[0].row()
        cols = int(self.table.item(row, 4).text())
        rows = int(self.table.item(row, 5).text())
        group = int(self.table.item(row, 6).text())

        self.scene.clear()
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

    # === Excel Yükleme ===
    def load_ders_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ders Listesi Seç", "", "Excel Files (*.xlsx *.xls)")
        if not path:
            return
        if QMessageBox.question(self, "Onay", "Mevcut ders kayıtları silinsin mi?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
            return
        try:
            self.db.execute("DELETE FROM sinavlar WHERE ders_id IN (SELECT id FROM dersler WHERE bolum=%s)", (self.bolum_adi,))
            self.db.execute("DELETE FROM ogrenci_ders WHERE ders_id IN (SELECT id FROM dersler WHERE bolum=%s)", (self.bolum_adi,))
            self.db.execute("DELETE FROM dersler WHERE bolum=%s", (self.bolum_adi,))
            self.db.execute("ALTER SEQUENCE dersler_id_seq RESTART WITH 1;")
            self.loader.load_dersler(path, self.bolum_adi)
            self.show_message("Başarılı", "Yeni ders listesi yüklendi.")
        except Exception as e:
            self.show_message("Hata", f"Yükleme hatası: {e}", QMessageBox.Critical)

    def load_ogr_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Öğrenci Listesi Seç", "", "Excel Files (*.xlsx *.xls)")
        if not path:
            return
        if QMessageBox.question(self, "Onay", "Tüm öğrenci kayıtları silinsin mi?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
            return
        try:
            self.db.execute("DELETE FROM ogrenci_ders;")
            self.db.execute("DELETE FROM ogrenciler;")
            self.loader.load_ogrenciler(path)
            self.show_message("Başarılı", "Yeni öğrenci listesi yüklendi.")
        except Exception as e:
            self.show_message("Hata", f"Yükleme hatası: {e}", QMessageBox.Critical)

    # === Sınav planlama ===
    def open_exam_window(self):
        dlg = ExamSchedulerDialog(self.db, self.bolum_adi, self)
        dlg.exec()


class ExamSchedulerDialog(QDialog):
    def __init__(self, db, bolum, parent=None):
        super().__init__(parent)
        self.db = db
        self.bolum = bolum
        self.setWindowTitle("Sınav Takvimi Oluştur")
        self.setMinimumSize(400, 300)

        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setCalendarPopup(True)

        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate().addDays(7))
        self.end_date.setCalendarPopup(True)

        self.duration_input = QSpinBox()
        self.duration_input.setRange(30, 180)
        self.duration_input.setValue(75)

        self.times_input = QLineEdit("09:00, 13:30, 17:00")

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)

        self.run_btn = QPushButton("Oluştur ve Kaydet")
        self.run_btn.clicked.connect(self.run_scheduler)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Başlangıç Tarihi:"))
        layout.addWidget(self.start_date)
        layout.addWidget(QLabel("Bitiş Tarihi:"))
        layout.addWidget(self.end_date)
        layout.addWidget(QLabel("Sınav Süresi (dakika):"))
        layout.addWidget(self.duration_input)
        layout.addWidget(QLabel("Günlük Saatler (virgülle):"))
        layout.addWidget(self.times_input)
        layout.addWidget(self.run_btn)
        layout.addWidget(QLabel("Çıktı:"))
        layout.addWidget(self.output_text)
        self.setLayout(layout)

    def run_scheduler(self):
        try:
            start = self.start_date.date().toPython()
            end = self.end_date.date().toPython()
            times = [t.strip() for t in self.times_input.text().split(",") if t.strip()]
            duration = self.duration_input.value()

            scheduler = ExamScheduler(self.db, times_per_day=times, bekleme_suresi_minutes=15)
            scheduled, failed = scheduler.schedule(start, end, duration_minutes=duration, bolum=self.bolum)

            if scheduled:
                file = scheduler.export_to_excel(scheduled, filename="sinav_takvimi.xlsx")
                self.output_text.setText(f"✅ {len(scheduled)} sınav planlandı.\nExcel kaydedildi: {file}")
            if failed:
                self.output_text.append(f"Planlanamayan ders sayısı: {len(failed)}")
        except Exception as e:
            self.output_text.setText(f" Hata: {e}")


if __name__ == "__main__":
    db = Database()
    db.connect()
    app = QApplication(sys.argv)
    win = CoordinatorPanel(db, bolum_adi="Bilgisayar Mühendisliği")
    win.show()
    sys.exit(app.exec())
