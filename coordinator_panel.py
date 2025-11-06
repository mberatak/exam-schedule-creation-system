# coordinator_panel.py
import sys
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QSpinBox, QGraphicsScene, QGraphicsView,
    QFileDialog, QFrame, QDialog, QDateEdit, QTextEdit, QListWidget, QListWidgetItem,
    QCheckBox, QAbstractItemView, QInputDialog
)

from connection import Database
from excel_loader import ExcelLoader
from exam_scheduler import ExamScheduler


# Koordinatör Paneli
class CoordinatorPanel(QWidget):
    def __init__(self, db: Database, bolum_adi: str = "Bilgisayar Mühendisliği"):
        super().__init__()
        self.db = db
        self.bolum_adi = bolum_adi

        self.setWindowTitle(f"{self.bolum_adi} Koordinatör Paneli")
        self.setMinimumSize(1200, 800)

        self.loader = ExcelLoader(db)
        self._seat_widgets = []

        # --- Derslik formu ---
        self.kod_input = QLineEdit(placeholderText="Derslik Kodu")
        self.ad_input = QLineEdit(placeholderText="Derslik Adı")

        self.kapasite_input = QSpinBox(); self.kapasite_input.setRange(5, 1000); self.kapasite_input.setValue(40)
        self.enine_input = QSpinBox(); self.enine_input.setRange(1, 50); self.enine_input.setValue(7)
        self.boyuna_input = QSpinBox(); self.boyuna_input.setRange(1, 50); self.boyuna_input.setValue(9)
        self.sira_input = QSpinBox(); self.sira_input.setRange(1, 10); self.sira_input.setValue(3)

        self.add_btn = QPushButton("Derslik Ekle"); self.add_btn.clicked.connect(self.add_derslik)
        self.refresh_btn = QPushButton("Yenile"); self.refresh_btn.clicked.connect(self.load_derslikler)
        self.delete_btn = QPushButton("Seçili Sil"); self.delete_btn.clicked.connect(self.delete_selected)
        self.visual_btn = QPushButton("Görselleştir"); self.visual_btn.clicked.connect(self.show_visual)

        # --- Excel ve planlama butonları ---
        self.load_ders_excel_btn = QPushButton("Ders Listesi Yükle")
        self.load_ders_excel_btn.clicked.connect(self.load_ders_excel)

        self.load_ogr_excel_btn = QPushButton("Öğrenci Listesi Yükle")
        self.load_ogr_excel_btn.clicked.connect(self.load_ogr_excel)

        self.generate_exam_btn = QPushButton("Sınav Takvimi Oluştur")
        self.generate_exam_btn.clicked.connect(self.open_exam_settings)

        # --- Yeni butonlar (EKLENDİ) ---
        self.show_exams_btn = QPushButton("📋 Planlanan Sınavları Görüntüle")
        self.show_exams_btn.clicked.connect(self.show_exams)

        #self.create_seat_btn = QPushButton("🪑 Oturma Planı Oluştur (Seçili Sınav)")
        #self.create_seat_btn.clicked.connect(self.create_seating)

        self.export_pdf_btn = QPushButton("🖨️ Oturma Planını PDF Olarak İndir")
        self.export_pdf_btn.clicked.connect(self.export_seating_pdf)

        # --- Tablolar ve görsel alan ---
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Kod", "Ad", "Kapasite", "Enine", "Boyuna", "Sıra"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumHeight(260)

        # --- Layout ---
        form = QHBoxLayout()
        form.addWidget(self.kod_input)
        form.addWidget(self.ad_input)
        form.addWidget(self.kapasite_input)
        form.addWidget(self.enine_input)
        form.addWidget(self.boyuna_input)
        form.addWidget(self.sira_input)
        form.addWidget(self.add_btn)

        btns = QHBoxLayout()
        btns.addWidget(self.refresh_btn)
        btns.addWidget(self.delete_btn)
        btns.addWidget(self.visual_btn)

        excel_line = QHBoxLayout()
        excel_line.addWidget(self.load_ders_excel_btn)
        excel_line.addWidget(self.load_ogr_excel_btn)
        excel_line.addWidget(self.generate_exam_btn)

        excel_line2 = QHBoxLayout()
        excel_line2.addWidget(self.show_exams_btn)
        #excel_line2.addWidget(self.create_seat_btn)
        excel_line2.addWidget(self.export_pdf_btn)

        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken)

        main = QVBoxLayout()
        main.addLayout(form)
        main.addLayout(btns)
        main.addWidget(line)
        main.addLayout(excel_line)
        main.addLayout(excel_line2)
        main.addWidget(QLabel("Derslikler:"))
        main.addWidget(self.table)
        main.addWidget(QLabel("Derslik Görseli:"))
        main.addWidget(self.view)
        self.setLayout(main)

        # İlk yükleme
        self.load_derslikler()

    # Yardımcılar
    def show_message(self, title, text, icon=QMessageBox.Information):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.exec()
    def show_exams(self):
        """Veritabanındaki planlanan sınavları listeler."""
        try:
            rows = self.db.execute("""
                SELECT s.id, d.kod, d.ad, s.tarih, s.saat, l.ad
                FROM sinavlar s
                JOIN dersler d ON s.ders_id = d.id
                JOIN derslikler l ON s.derslik_id = l.id
                ORDER BY s.tarih, s.saat
            """, fetchall=True)

            if not rows:
                self.show_message("Boş", "Henüz sınav planı oluşturulmamış.")
                return

            table = QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(["ID", "Ders Kodu", "Ders Adı", "Tarih", "Saat", "Derslik"])
            table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                for j, val in enumerate(r):
                    table.setItem(i, j, QTableWidgetItem(str(val)))
            table.resizeColumnsToContents()

            dlg = QDialog(self)
            dlg.setWindowTitle("Planlanan Sınavlar")
            dlg.resize(700, 400)
            layout = QVBoxLayout()
            layout.addWidget(table)
            dlg.setLayout(layout)
            dlg.exec()
        except Exception as e:
            self.show_message("Hata", f"Sınav listesi yüklenemedi: {e}", QMessageBox.Critical)

    def create_seating(self):
        """Kullanıcıdan sınav ID alıp oturma planı oluşturur."""
        exam_id, ok = QInputDialog.getInt(self, "Sınav ID", "Sınav ID numarasını girin:")
        if not ok:
            return
        try:
            planner = SeatPlanner(self.db)
            assignments = planner.assign_seats(exam_id)
            self.show_message("Başarılı", f"Oturma planı oluşturuldu ({len(assignments)} öğrenci).")
        except Exception as e:
            self.show_message("Hata", f"Oturma planı oluşturulamadı: {e}", QMessageBox.Critical)

    def export_seating_pdf(self):
        """Seçili sınav için oturma planını PDF olarak dışa aktarır."""
        exam_id, ok = QInputDialog.getInt(self, "Sınav ID", "Sınav ID numarasını girin:")
        if not ok:
            return
        try:
            path, _ = QFileDialog.getSaveFileName(self, "PDF olarak kaydet", "oturma_plani.pdf", "PDF Files (*.pdf)")
            if not path:
                return
            planner = SeatPlanner(self.db)
            output = planner.export_pdf(exam_id, path)
            self.show_message("Kaydedildi", f"PDF oluşturuldu:\n{output}")
        except Exception as e:
            self.show_message("Hata", f"PDF oluşturulamadı: {e}", QMessageBox.Critical)
    def load_derslikler(self):
        q = """
        SELECT id, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi
        FROM derslikler
        WHERE bolum=%s
        ORDER BY id
        """
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

    # Oturma düzeni görselleştirme kuralları
    def _seat_occupied(self, group_size: int, idx_in_group: int, row_idx: int, total_rows: int) -> bool:
        """Kurallara göre bu koltukta öğrenci oturur mu?"""
        # Son sıra her zaman boş
        if row_idx == total_rows - 1:
            return False

        if group_size == 1:
            return True
        if group_size == 2:  # sadece sol
            return idx_in_group == 0
        if group_size == 3:  # ortası boş
            return idx_in_group in (0, 2)
        if group_size == 4:  # ortadaki ikisi boş
            return idx_in_group in (0, 3)

        # varsayılan: kenarlar dolu, içler boş
        return idx_in_group == 0 or idx_in_group == (group_size - 1)

    def _make_seat_button(self, occupied: bool) -> QPushButton:
        """Duruma göre renklendirilmiş küçük bir buton oluşturur."""
        btn = QPushButton()
        btn.setFixedSize(26, 26)
        btn.setEnabled(False)  # sadece görsel
        if occupied:  # yeşil
            btn.setStyleSheet(
                "QPushButton { background:#20BB6A; border-radius:6px; border:1px solid #1a8f52; }"
            )
            btn.setToolTip("Dolu (öğrenci)")
        else:  # gri
            btn.setStyleSheet(
                "QPushButton { background:#BDBDBD; border-radius:6px; border:1px solid #9a9a9a; }"
            )
            btn.setToolTip("Boş")
        return btn

    def add_derslik(self):
        kod = self.kod_input.text().strip()
        ad = self.ad_input.text().strip()
        kapasite = self.kapasite_input.value()
        enine = self.enine_input.value()
        boyuna = self.boyuna_input.value()
        sira = self.sira_input.value()

        if not (kod and ad):
            self.show_message("Eksik", "Kod ve ad gerekli", QMessageBox.Warning)
            return

        q = """
        INSERT INTO derslikler (bolum, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
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
            self.show_message("Seçim yok", "Seçim yap", QMessageBox.Warning)
            return

        row = sel[0].row()
        derslik_id = self.table.item(row, 0).text()
        ad = self.table.item(row, 2).text()

        if QMessageBox.question(self, "Onay", f"{ad} silinsin mi?") == QMessageBox.Yes:
            try:
                self.db.execute("DELETE FROM derslikler WHERE id=%s", (derslik_id,))
                self.show_message("Başarılı", "Silindi")
                self.load_derslikler()
            except Exception as e:
                self.show_message("Hata", f"Silme hatası: {e}", QMessageBox.Critical)

    def show_visual(self):
        sel = self.table.selectedItems()
        if not sel:
            self.show_message("Seçim yok", "Seçim yap", QMessageBox.Warning)
            return

        # Eski öğeleri temizle
        self._clear_seat_widgets()
        self.scene.clear()

        row = sel[0].row()

        def safe_int(item, default):
            try:
                return int(item.text().strip())
            except Exception:
                return default

        # Enine = grup sayısı, Boyuna = oturulabilir sıra sayısı, Sıra = grup genişliği
        group_count = max(1, safe_int(self.table.item(row, 4), 1))
        rows_occupiable = max(1, safe_int(self.table.item(row, 5), 1))
        group_size = max(1, safe_int(self.table.item(row, 6), 1))
        total_rows = rows_occupiable + 1  # en arka tamamen gri

        # Buton geometrisi
        box = 28
        gap = 6
        block_gap = 28

        # Sahne boyutu
        width = 0
        for b in range(group_count):
            width += group_size * (box + gap)
            if b < group_count - 1:
                width += (block_gap - gap)
        height = total_rows * (box + gap)
        self.scene.setSceneRect(0, 0, max(width, 1), max(height, 1))

        yoff = 0
        for r in range(total_rows):
            xoff = 0
            for b in range(group_count):
                for c_in_block in range(group_size):
                    occupied = self._seat_occupied(
                        group_size=group_size,
                        idx_in_group=c_in_block,
                        row_idx=r,
                        total_rows=total_rows
                    )
                    btn = self._make_seat_button(occupied)
                    proxy = self.scene.addWidget(btn)
                    proxy.setPos(xoff, yoff)
                    # yeni butonu listeye ekle ki bir sonraki çizimde güvenle yok edelim
                    self._seat_widgets.append(btn)
                    xoff += box + gap
                if b < group_count - 1:
                    xoff += (block_gap - gap)
            yoff += box + gap

    def _clear_seat_widgets(self):
        """Önceki görselleştirmeden kalan gerçek QPushButton nesnelerini yok et."""
        for w in self._seat_widgets:
            try:
                w.setParent(None)
                w.deleteLater()
            except Exception:
                pass
        self._seat_widgets = []

    # Excel yüklemeleri-
    def load_ders_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ders Excel Seç", "", "Excel Files (*.xlsx *.xls)")
        if not path:
            return

        if QMessageBox.question(self, "Onay", "Bu işlem mevcut dersleri silecek. Devam?") == QMessageBox.No:
            return

        try:
            # İlişkili sınav ve öğrenci-ders kayıtlarını temizle
            self.db.execute(
                "DELETE FROM sinavlar WHERE ders_id IN (SELECT id FROM dersler WHERE bolum=%s)",
                (self.bolum_adi,)
            )
            self.db.execute(
                "DELETE FROM ogrenci_ders WHERE ders_id IN (SELECT id FROM dersler WHERE bolum=%s)",
                (self.bolum_adi,)
            )
            self.db.execute("DELETE FROM dersler WHERE bolum=%s", (self.bolum_adi,))

            # Sequence reset (varsa)
            self.db.execute("ALTER SEQUENCE IF EXISTS dersler_id_seq RESTART WITH 1;")
            self.db.execute("ALTER SEQUENCE IF EXISTS sinavlar_id_seq RESTART WITH 1;")

            self.loader.load_dersler(path, self.bolum_adi)
            self.show_message("Başarılı", "Yeni ders listesi yüklendi.")
            self.load_derslikler()
        except Exception as e:
            self.show_message("Hata", f"Yükleme hatası: {e}", QMessageBox.Critical)

    def load_ogr_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Öğrenci Excel Seç", "", "Excel Files (*.xlsx *.xls)")
        if not path:
            return

        if QMessageBox.question(self, "Onay", "Bu işlem mevcut öğrenci kayıtlarını silecek. Devam?") == QMessageBox.No:
            return

        try:
            self.db.execute("DELETE FROM ogrenci_ders;")
            self.db.execute("DELETE FROM ogrenciler;")
            self.loader.load_ogrenciler(path)
            self.show_message("Başarılı", "Öğrenciler yüklendi")
        except Exception as e:
            self.show_message("Hata", f"Yükleme hatası: {e}", QMessageBox.Critical)

    # Sınav ayarları dialogu
    def open_exam_settings(self):
        dlg = ExamSettingsDialog(self.db, self.bolum_adi, parent=self)
        dlg.exec()


# Sınav Ayarları / Oluşturma Dialogu
class ExamSettingsDialog(QDialog):
    def __init__(self, db: Database, bolum: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.bolum = bolum

        self.setWindowTitle("Sınav Programı - Kısıtlar ve Oluşturma")
        self.setMinimumSize(800, 600)

        # State
        self.last_scheduled = None
        self.per_course_durations = {}

        # Sol: ders listesi (checkbox)
        self.course_list = QListWidget()
        self.load_courses()

        # Orta: ayarlar
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addDays(14))

        self.skip_weekends_cb = QCheckBox("Cumartesi/Pazar hariç tut (varsayılan)")
        self.skip_weekends_cb.setChecked(True)

        self.no_simult_cb = QCheckBox("Sınavların aynı anda olmamasını sağla")
        self.no_simult_cb.setChecked(False)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(30, 240)
        self.duration_spin.setValue(75)

        self.bekleme_spin = QSpinBox()
        self.bekleme_spin.setRange(0, 120)
        self.bekleme_spin.setValue(15)

        self.type_combo = QLineEdit("Final")  # Basit metin (istenirse ileride combobox yapılır)
        self.times_edit = QLineEdit("09:00, 10:00, 13:30, 15:30, 17:00")

        # Sağ: ders bazlı süre override
        self.override_label = QLabel("Seçili ders için süre (dk) ayarla:")
        self.override_spin = QSpinBox()
        self.override_spin.setRange(30, 240)
        self.override_spin.setValue(40)

        self.set_override_btn = QPushButton("Süreyi Uygula (Seçili Derslere)")
        self.set_override_btn.clicked.connect(self.apply_override)

        # çalıştır & çıktı
        self.run_btn = QPushButton("Programı Oluştur")
        # yeni planlamada temiz başlangıç için TRUNCATE uyguluyoruz:
        self.run_btn.clicked.connect(self.run_scheduler)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)

        self.save_excel_btn = QPushButton("Excel'e Kaydet (Son Oluşturulan)")
        self.save_excel_btn.clicked.connect(self.save_last_excel)
        self.save_excel_btn.setEnabled(False)

        # Yerleşim
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Ders Listesi (seçmek için tikleyin)"))
        left_layout.addWidget(self.course_list)

        center_layout = QVBoxLayout()
        center_layout.addWidget(QLabel("Tarih Aralığı:"))
        center_layout.addWidget(self.start_date)
        center_layout.addWidget(self.end_date)
        center_layout.addWidget(self.skip_weekends_cb)
        center_layout.addWidget(self.no_simult_cb)
        center_layout.addWidget(QLabel("Varsayılan sınav süresi (dk):"))
        center_layout.addWidget(self.duration_spin)
        center_layout.addWidget(QLabel("Bekleme süresi (dk):"))
        center_layout.addWidget(self.bekleme_spin)
        center_layout.addWidget(QLabel("Günlük saatler (virgül ile):"))
        center_layout.addWidget(self.times_edit)
        center_layout.addStretch()
        center_layout.addWidget(self.run_btn)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.override_label)
        right_layout.addWidget(self.override_spin)
        right_layout.addWidget(self.set_override_btn)
        right_layout.addStretch()
        right_layout.addWidget(self.save_excel_btn)

        bottom_layout = QHBoxLayout()
        bottom_layout.addLayout(left_layout)
        bottom_layout.addLayout(center_layout)
        bottom_layout.addLayout(right_layout)

        main = QVBoxLayout()
        main.addLayout(bottom_layout)
        main.addWidget(QLabel("Çıktı:"))
        main.addWidget(self.output_text)
        self.setLayout(main)

    # Yardımcılar
    def show_message(self, title, text, icon=QMessageBox.Information):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.exec()

    def load_courses(self):
        rows = self.db.execute(
            "SELECT id, kod, ad, sinif FROM dersler WHERE bolum=%s ORDER BY sinif, kod",
            (self.bolum,), fetchall=True
        )
        self.course_list.clear()
        for r in rows:
            item = QListWidgetItem(f"{r[1]} - {r[2]} (Sınıf {r[3]})")
            item.setData(Qt.UserRole, r[0])  # ders id
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.course_list.addItem(item)

    def selected_course_ids(self):
        ids = []
        for i in range(self.course_list.count()):
            it = self.course_list.item(i)
            if it.checkState() == Qt.Checked:
                ids.append(it.data(Qt.UserRole))
        return ids

    def apply_override(self):
        sel = self.selected_course_ids()
        if not sel:
            self.show_message("Seçim yok", "Önce dersleri seçin.", QMessageBox.Warning)
            return
        val = self.override_spin.value()
        for cid in sel:
            self.per_course_durations[cid] = val
        self.show_message("Uygulandı", f"Seçili derslere {val} dk olarak ayarlandı.")

    def run_scheduler(self):
        # her çalıştırmada temiz başlatma:
        try:
            self.db.execute("TRUNCATE TABLE sinavlar RESTART IDENTITY CASCADE;")
            self.db.execute("TRUNCATE TABLE ogrenci_sinav RESTART IDENTITY CASCADE;")
            self.db.execute("TRUNCATE TABLE oturma RESTART IDENTITY CASCADE;")
        except Exception as e:
            self.output_text.append(f"⚠ Tablolar sıfırlanamadı: {e}")

        try:
            start = self.start_date.date().toPython()
            end = self.end_date.date().toPython()
            times = [t.strip() for t in self.times_edit.text().split(",") if t.strip()]
            duration = self.duration_spin.value()
            bekleme = self.bekleme_spin.value()
            skip_weekends = self.skip_weekends_cb.isChecked()
            no_sim = self.no_simult_cb.isChecked()

            selected = self.selected_course_ids()
            if not selected:
                self.show_message("Seçim yok", "En az bir ders seçin.", QMessageBox.Warning)
                return

            scheduler = ExamScheduler(
                self.db,
                times_per_day=times,
                bekleme_suresi_minutes=bekleme,
                no_simultaneous_exams=no_sim
            )

            scheduled, failed = scheduler.schedule(
                start,
                end,
                selected_course_ids=selected,
                duration_default=duration,
                per_course_durations=self.per_course_durations,
                bolum=self.bolum,
                skip_weekends=skip_weekends,
                excluded_weekdays=None,
                excluded_dates=None,
                no_simultaneous_exams=no_sim
            )

            self.last_scheduled = scheduled

            # Çıktı
            self.output_text.clear()
            self.output_text.append(f"✅ Planlanan sınav: {len(scheduled)}")
            self.output_text.append(f"✅ Oturma planları otomatik oluşturuldu")
            for se in scheduled:
                self.output_text.append(
                    f"{se['ders_kod']} - {se['ders_ad']} | "
                    f"{se['tarih']} {se['saat'].strftime('%H:%M')} | {se['derslik_ad']}"
                )

            if failed:
                self.output_text.append(f"\n⚠ Planlanamayan: {len(failed)}")
                for f in failed:
                    c = f.get("course")
                    k = c.get("kod") if isinstance(c, dict) else (
                        c[1] if isinstance(c, (list, tuple)) and len(c) > 1 else str(c)
                    )
                    self.output_text.append(f"{k} -> {f.get('reason')}")

            # Excel export
            if scheduled:
                fname = scheduler.export_to_excel(scheduled, filename="sinav_takvimi.xlsx")
                self.output_text.append(f"\nExcel kaydedildi: {fname}")
                self.save_excel_btn.setEnabled(True)

            # Kapasiteye göre ogrenci_sinav tablosunu yenile
            ok, msg = self.rebuild_ogrenci_sinav()
            self.output_text.append(("✅ " if ok else "❌ ") + msg)

        except Exception as e:
            self.output_text.setText(f"❌ Hata: {e}")

    def save_last_excel(self):
        if not self.last_scheduled:
            self.show_message("Yok", "Önce plan oluşturun", QMessageBox.Warning)
            return

        path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "sinav_takvimi.xlsx", "Excel Files (*.xlsx)")
        if not path:
            return

        df_rows = []
        for se in self.last_scheduled:
            df_rows.append({
                "Ders Kodu": se['ders_kod'],
                "Ders Adı": se['ders_ad'],
                "Tarih": se['tarih'],
                "Saat": se['saat'].strftime("%H:%M"),
                "Derslik": se['derslik_ad'],
                "Süre": se['sure'],
                "Öğrenci Sayısı": se.get('n_students', 0)
            })

        pd.DataFrame(df_rows).to_excel(path, index=False)
        self.show_message("Kaydedildi", f"Excel kaydedildi: {path}")

    
    def rebuild_ogrenci_sinav(self):
        """
        ogrenci_sinav tablosunu (no, ad, soyad, ders_id) kapasiteyi dikkate alarak baştan kurar.
        - Her ders için (sinavlar'daki ilk sınav esas) dersliğin kapasitesi kadar öğrenci eklenir.
        - Öğrenciler ogrenci_no'ya göre sıralanır.
        """
        q_drop = "DROP TABLE IF EXISTS ogrenci_sinav;"

        q_create = """
        CREATE TABLE ogrenci_sinav (
            no VARCHAR(20) NOT NULL,
            ad VARCHAR(100),
            soyad VARCHAR(100),
            ders_id INT NOT NULL REFERENCES dersler(id) ON DELETE CASCADE,
            PRIMARY KEY (no, ders_id)
        );
        """

        # ad/soyad: son kelime soyad, geri kalanı ad
        q_insert = """
        WITH first_exam AS (
            SELECT
                s.ders_id,
                l.kapasite,
                ROW_NUMBER() OVER (PARTITION BY s.ders_id ORDER BY s.tarih, s.saat, s.id) AS rn
            FROM sinavlar s
            JOIN derslikler l ON l.id = s.derslik_id
        ),
        src AS (
            SELECT
                od.ogrenci_no,
                od.ders_id,
                ROW_NUMBER() OVER (PARTITION BY od.ders_id ORDER BY od.ogrenci_no) AS rnk
            FROM ogrenci_ders od
        )
        INSERT INTO ogrenci_sinav (no, ad, soyad, ders_id)
        SELECT
            og.no,
            TRIM(REGEXP_REPLACE(og.adsoyad, '\\s+\\S+$', '')) AS ad,
            REGEXP_REPLACE(og.adsoyad, '.*\\s+', '') AS soyad,
            s.ders_id
        FROM src s
        JOIN first_exam fe ON fe.ders_id = s.ders_id AND fe.rn = 1
        JOIN ogrenciler og ON og.no = s.ogrenci_no
        WHERE s.rnk <= fe.kapasite;
        """

        try:
            self.db.execute(q_drop)
            self.db.execute(q_create)
            self.db.execute(q_insert)
            return True, "ogrenci_sinav tablosu kapasiteye göre oluşturuldu."
        except Exception as e:
            return False, f"ogrenci_sinav oluşturma hatası: {e}"


# Basit Oturma Planlayıcı
class SeatPlanner:
    def __init__(self, db: Database):
        self.db = db

    def get_students_for_exam(self, sinav_id: int):
        row = self.db.execute(
            "SELECT ders_id, derslik_id, tarih, saat FROM sinavlar WHERE id=%s",
            (sinav_id,), fetchone=True
        )
        if not row:
            return []
        ders_id = row[0]
        studs = self.db.execute(
            "SELECT ogrenci_no FROM ogrenci_ders WHERE ders_id=%s ORDER BY ogrenci_no",
            (ders_id,), fetchall=True
        )
        return [s[0] for s in studs]

    def get_room_info(self, derslik_id: int):
        return self.db.execute(
            "SELECT ad, enine_sira, boyuna_sira, sira_yapisi FROM derslikler WHERE id=%s",
            (derslik_id,), fetchone=True
        )

    def assign_seats(self, sinav_id: int):
        row = self.db.execute(
            "SELECT ders_id, derslik_id FROM sinavlar WHERE id=%s",
            (sinav_id,), fetchone=True
        )
        if not row:
            raise RuntimeError("Sınav bulunamadı")
        derslik_id = row[1]

        students = self.get_students_for_exam(sinav_id)
        room = self.get_room_info(derslik_id)
        if not room:
            raise RuntimeError("Derslik bilgisi yok")

        _, enine, boyuna, _ = room
        capacity = int(enine) * int(boyuna)
        if len(students) > capacity:
            raise RuntimeError(f"Kapasite yetersiz: {len(students)} öğrenci, kapasite {capacity}")

        assignments = []
        idx = 0
        for r in range(int(boyuna)):
            for c in range(int(enine)):
                if idx >= len(students):
                    break
                assignments.append({
                    "ogrenci_no": students[idx][0] if isinstance(students[idx], tuple) else students[idx],
                    "row": r + 1,
                    "col": c + 1
                })
                idx += 1
            if idx >= len(students):
                break

        # DB'ye yaz (mevcutları temizle)
        self.db.execute("DELETE FROM oturma WHERE sinav_id=%s", (sinav_id,))
        for a in assignments:
            self.db.execute(
                "INSERT INTO oturma (sinav_id, ogrenci_no, sira, sutun) VALUES (%s, %s, %s, %s)",
                (sinav_id, a['ogrenci_no'], a['row'], a['col'])
            )
        return assignments

    def export_pdf(self, sinav_id: int, output_path: str):
        info = self.db.execute(
            """
            SELECT s.id, d.kod, d.ad, s.tarih, s.saat, l.ad, l.enine_sira, l.boyuna_sira
            FROM sinavlar s
            JOIN dersler d ON s.ders_id = d.id
            JOIN derslikler l ON s.derslik_id = l.id
            WHERE s.id = %s
            """,
            (sinav_id,), fetchone=True
        )
        if not info:
            raise RuntimeError("Sınav bulunamadı")

        _, ders_kod, ders_ad, tarih, saat, room_ad, _, _ = info

        assigns = self.db.execute(
            """
            SELECT o.ogrenci_no, ogr.adsoyad, o.sira, o.sutun
            FROM oturma o
            JOIN ogrenciler ogr ON o.ogrenci_no = ogr.no
            WHERE o.sinav_id=%s
            ORDER BY o.sira, o.sutun
            """,
            (sinav_id,), fetchall=True
        )

        c = canvas.Canvas(output_path, pagesize=A4)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, 800, f"{ders_kod} - {ders_ad} Oturma Planı")

        c.setFont("Helvetica", 10)
        c.drawString(40, 785, f"Tarih: {tarih} Saat: {saat.strftime('%H:%M')} Derslik: {room_ad}")

        y = 760
        c.setFont("Helvetica", 9)
        c.drawString(40, y, "No")
        c.drawString(120, y, "Ad Soyad")
        c.drawString(360, y, "Sıra")
        c.drawString(420, y, "Sütun")
        y -= 14

        for a in assigns:
            c.drawString(40, y, str(a[0]))
            c.drawString(120, y, str(a[1]))
            c.drawString(360, y, str(a[2]))
            c.drawString(420, y, str(a[3]))
            y -= 12
            if y < 60:
                c.showPage()
                y = 800

        c.save()
        return output_path


# Çalıştırma
if __name__ == "__main__":
    db = Database()
    db.connect()

    app = QApplication(sys.argv)
    win = CoordinatorPanel(db, bolum_adi="Bilgisayar Mühendisliği")
    win.show()
    sys.exit(app.exec())
