# coordinator_panel.py
import sys, os
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QSpinBox, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QFileDialog, QFrame, QDialog, QDateEdit, QTextEdit, QListWidget, QListWidgetItem, QCheckBox, QAbstractItemView
)
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtCore import Qt, QDate
from connection import Database
from excel_loader import ExcelLoader
from exam_scheduler import ExamScheduler
from datetime import date
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

class CoordinatorPanel(QWidget):
    def __init__(self, db: Database, bolum_adi="Bilgisayar Mühendisliği"):
        super().__init__()
        self.db = db
        self.bolum_adi = bolum_adi
        self.setWindowTitle(f"{self.bolum_adi} Koordinatör Paneli")
        self.setMinimumSize(1200, 800)
        self.loader = ExcelLoader(db)

        # derslik form
        self.kod_input = QLineEdit(); self.kod_input.setPlaceholderText("Derslik Kodu")
        self.ad_input = QLineEdit(); self.ad_input.setPlaceholderText("Derslik Adı")
        self.kapasite_input = QSpinBox(); self.kapasite_input.setRange(5,1000); self.kapasite_input.setValue(40)
        self.enine_input = QSpinBox(); self.enine_input.setRange(1,50); self.enine_input.setValue(7)
        self.boyuna_input = QSpinBox(); self.boyuna_input.setRange(1,50); self.boyuna_input.setValue(9)
        self.sira_input = QSpinBox(); self.sira_input.setRange(1,10); self.sira_input.setValue(3)
        self.add_btn = QPushButton("Derslik Ekle"); self.add_btn.clicked.connect(self.add_derslik)
        self.refresh_btn = QPushButton("Yenile"); self.refresh_btn.clicked.connect(self.load_derslikler)
        self.delete_btn = QPushButton("Seçili Sil"); self.delete_btn.clicked.connect(self.delete_selected)
        self.visual_btn = QPushButton("Görselleştir"); self.visual_btn.clicked.connect(self.show_visual)

        # excel buttons
        self.load_ders_excel_btn = QPushButton("Ders Listesi Yükle"); self.load_ders_excel_btn.clicked.connect(self.load_ders_excel)
        self.load_ogr_excel_btn = QPushButton("Öğrenci Listesi Yükle"); self.load_ogr_excel_btn.clicked.connect(self.load_ogr_excel)
        self.generate_exam_btn = QPushButton("Sınav Takvimi Oluştur"); self.generate_exam_btn.clicked.connect(self.open_exam_settings)

        # table and view
        self.table = QTableWidget(); self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID","Kod","Ad","Kapasite","Enine","Boyuna","Sıra"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.scene = QGraphicsScene(); self.view = QGraphicsView(self.scene); self.view.setMinimumHeight(260)
        


        # layout assembly
        form = QHBoxLayout(); form.addWidget(self.kod_input); form.addWidget(self.ad_input); form.addWidget(self.kapasite_input)
        form.addWidget(self.enine_input); form.addWidget(self.boyuna_input); form.addWidget(self.sira_input); form.addWidget(self.add_btn)

        btns = QHBoxLayout(); btns.addWidget(self.refresh_btn); btns.addWidget(self.delete_btn); btns.addWidget(self.visual_btn)

        excel_line = QHBoxLayout(); excel_line.addWidget(self.load_ders_excel_btn); excel_line.addWidget(self.load_ogr_excel_btn); excel_line.addWidget(self.generate_exam_btn)

        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken)

        main = QVBoxLayout()
        main.addLayout(form); main.addLayout(btns); main.addWidget(line); main.addLayout(excel_line)
        main.addWidget(QLabel("Derslikler:")); main.addWidget(self.table)
        main.addWidget(QLabel("Derslik Görseli:")); main.addWidget(self.view)
        self.setLayout(main)

        self.load_derslikler()

    def show_message(self,title,text,icon=QMessageBox.Information):
        msg=QMessageBox(self); msg.setWindowTitle(title); msg.setText(text); msg.setIcon(icon); msg.exec()

    def load_derslikler(self):
        q="SELECT id,kod,ad,kapasite,enine_sira,boyuna_sira,sira_yapisi FROM derslikler WHERE bolum=%s ORDER BY id"
        try:
            rows = self.db.execute(q, (self.bolum_adi,), fetchall=True)
            self.table.setRowCount(0)
            for r in rows:
                row_pos=self.table.rowCount(); self.table.insertRow(row_pos)
                for c,val in enumerate(r): self.table.setItem(row_pos,c,QTableWidgetItem(str(val)))
            self.table.resizeColumnsToContents()
        except Exception as e:
            self.show_message("Hata", f"Derslikler yüklenemedi: {e}", QMessageBox.Critical)

    def add_derslik(self):
        kod = self.kod_input.text().strip(); ad=self.ad_input.text().strip()
        kapasite=self.kapasite_input.value(); enine=self.enine_input.value(); boyuna=self.boyuna_input.value(); sira=self.sira_input.value()
        if not (kod and ad): self.show_message("Eksik","Kod ve ad gerekli",QMessageBox.Warning); return
        q="INSERT INTO derslikler (bolum,kod,ad,kapasite,enine_sira,boyuna_sira,sira_yapisi) VALUES (%s,%s,%s,%s,%s,%s,%s)"
        try:
            self.db.execute(q,(self.bolum_adi,kod,ad,kapasite,enine,boyuna,sira))
            self.show_message("Başarılı","Derslik eklendi.")
            self.kod_input.clear(); self.ad_input.clear(); self.load_derslikler()
        except Exception as e:
            self.show_message("Hata",f"Ekleme başarısız: {e}",QMessageBox.Critical)

    def delete_selected(self):
        sel=self.table.selectedItems()
        if not sel: self.show_message("Seçim yok","Seçim yap",QMessageBox.Warning); return
        row=sel[0].row(); derslik_id=self.table.item(row,0).text(); ad=self.table.item(row,2).text()
        if QMessageBox.question(self,"Onay",f"{ad} silinsin mi?")==QMessageBox.Yes:
            try: self.db.execute("DELETE FROM derslikler WHERE id=%s",(derslik_id,)); self.show_message("Başarılı","Silindi"); self.load_derslikler()
            except Exception as e: self.show_message("Hata",f"Silme hatası: {e}",QMessageBox.Critical)

    def show_visual(self):
        sel=self.table.selectedItems()
        if not sel: self.show_message("Seçim yok","Seçim yap",QMessageBox.Warning); return
        row=sel[0].row()
        cols=int(self.table.item(row,4).text()); rows=int(self.table.item(row,5).text()); group=int(self.table.item(row,6).text())
        self.scene.clear(); box=30; gap=6; yoff=0
        for y in range(rows):
            xoff=0
            for x in range(cols):
                color = QColor(200,220,255) if (x//group)%2==0 else QColor(200,255,200)
                rect = QGraphicsRectItem(xoff,yoff,box,box)
                rect.setBrush(QBrush(color)); rect.setPen(QPen(QColor("black")))
                self.scene.addItem(rect)
                xoff += box+gap
            yoff += box+gap

    # Excel load with replace semantics
    def load_ders_excel(self):
        path,_ = QFileDialog.getOpenFileName(self,"Ders Excel Seç","","Excel Files (*.xlsx *.xls)")
        if not path: return
        if QMessageBox.question(self,"Onay","Bu işlem mevcut dersleri silecek. Devam?")==QMessageBox.No: return
        try:
            self.db.execute("DELETE FROM sinavlar WHERE ders_id IN (SELECT id FROM dersler WHERE bolum=%s)", (self.bolum_adi,))
            self.db.execute("DELETE FROM ogrenci_ders WHERE ders_id IN (SELECT id FROM dersler WHERE bolum=%s)", (self.bolum_adi,))
            self.db.execute("DELETE FROM dersler WHERE bolum=%s", (self.bolum_adi,))
            self.db.execute("ALTER SEQUENCE dersler_id_seq RESTART WITH 1;")
            self.db.execute("ALTER SEQUENCE sinavlar_id_seq RESTART WITH 1;")
            self.loader.load_dersler(path, self.bolum_adi)
            self.show_message("Başarılı", "Yeni ders listesi yüklendi.")
        except Exception as e:
            self.show_message("Hata",f"Yükleme hatası: {e}",QMessageBox.Critical)

    def load_ogr_excel(self):
        path,_ = QFileDialog.getOpenFileName(self,"Öğrenci Excel Seç","","Excel Files (*.xlsx *.xls)")
        if not path: return
        if QMessageBox.question(self,"Onay","Bu işlem mevcut öğrenci kayıtlarını silecek. Devam?")==QMessageBox.No: return
        try:
            self.db.execute("DELETE FROM ogrenci_ders;"); self.db.execute("DELETE FROM ogrenciler;")
            self.loader.load_ogrenciler(path); self.show_message("Başarılı","Öğrenciler yüklendi")
        except Exception as e:
            self.show_message("Hata",f"Yükleme hatası: {e}",QMessageBox.Critical)

    # === EXAM SETTINGS DIALOG ===
    def open_exam_settings(self):
        dlg = ExamSettingsDialog(self.db, self.bolum_adi, parent=self)
        dlg.exec()

# dialog
class ExamSettingsDialog(QDialog):
    def __init__(self, db, bolum, parent=None):
        super().__init__(parent)
        self.db = db; self.bolum = bolum
        self.setWindowTitle("Sınav Programı - Kısıtlar ve Oluşturma"); self.setMinimumSize(800,600)

        # left: course list with checkboxes
        self.course_list = QListWidget()
        self.load_courses()

        # center: options
        self.start_date = QDateEdit(); self.start_date.setCalendarPopup(True); self.start_date.setDate(QDate.currentDate())
        self.end_date = QDateEdit(); self.end_date.setCalendarPopup(True); self.end_date.setDate(QDate.currentDate().addDays(14))
        self.skip_weekends_cb = QCheckBox("Cumartesi/Pazar hariç tut (varsayılan)"); self.skip_weekends_cb.setChecked(True)
        self.no_simult_cb = QCheckBox("Sınavların aynı anda olmamasını sağla"); self.no_simult_cb.setChecked(False)
        self.duration_spin = QSpinBox(); self.duration_spin.setRange(30,240); self.duration_spin.setValue(75)
        self.bekleme_spin = QSpinBox(); self.bekleme_spin.setRange(0,120); self.bekleme_spin.setValue(15)
        self.type_combo = QLineEdit("Final")  # simple text for type
        self.times_edit = QLineEdit("09:00, 13:30, 17:00")

        # right: per-course exceptions (simple: choose checked course, then set duration override)
        self.override_label = QLabel("Seçili ders için süre (dk) ayarla:")
        self.override_spin = QSpinBox(); self.override_spin.setRange(30,240); self.override_spin.setValue(75)
        self.set_override_btn = QPushButton("Süreyi Uygula (Seçili Derslere)"); self.set_override_btn.clicked.connect(self.apply_override)

        # run button and output
        self.run_btn = QPushButton("Programı Oluştur")
        self.run_btn.clicked.connect(self.run_scheduler)
        self.output_text = QTextEdit(); self.output_text.setReadOnly(True)
        self.save_excel_btn = QPushButton("Excel'e Kaydet (Son Oluşturulan)"); self.save_excel_btn.clicked.connect(self.save_last_excel)
        self.save_excel_btn.setEnabled(False)

        # layout
        left_layout = QVBoxLayout(); left_layout.addWidget(QLabel("Ders Listesi (seçmek için tikleyin)")); left_layout.addWidget(self.course_list)
        center_layout = QVBoxLayout()
        center_layout.addWidget(QLabel("Tarih Aralığı:")); center_layout.addWidget(self.start_date); center_layout.addWidget(self.end_date)
        center_layout.addWidget(self.skip_weekends_cb); center_layout.addWidget(self.no_simult_cb)
        center_layout.addWidget(QLabel("Default sınav süresi (dk):")); center_layout.addWidget(self.duration_spin)
        center_layout.addWidget(QLabel("Bekleme süresi (dk):")); center_layout.addWidget(self.bekleme_spin)
        center_layout.addWidget(QLabel("Günlük saatler (virgül ile):")); center_layout.addWidget(self.times_edit)
        center_layout.addStretch(); center_layout.addWidget(self.run_btn)

        right_layout = QVBoxLayout(); right_layout.addWidget(self.override_label); right_layout.addWidget(self.override_spin)
        right_layout.addWidget(self.set_override_btn); right_layout.addStretch(); right_layout.addWidget(self.save_excel_btn)

        bottom_layout = QHBoxLayout(); bottom_layout.addLayout(left_layout); bottom_layout.addLayout(center_layout); bottom_layout.addLayout(right_layout)

        main = QVBoxLayout(); main.addLayout(bottom_layout); main.addWidget(QLabel("Çıktı:")); main.addWidget(self.output_text)
        self.setLayout(main)

        # state
        self.last_scheduled = None
        self.per_course_durations = {}

    def load_courses(self):
        rows = self.db.execute("SELECT id,kod,ad,sinif FROM dersler ORDER BY sinif, kod", fetchall=True)
        self.course_list.clear()
        for r in rows:
            item = QListWidgetItem(f"{r[1]} - {r[2]} (Sınıf {r[3]})")
            item.setData(Qt.UserRole, r[0])  # store id
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.course_list.addItem(item)

    def selected_course_ids(self):
        ids=[]
        for i in range(self.course_list.count()):
            it = self.course_list.item(i)
            if it.checkState() == Qt.Checked:
                ids.append(it.data(Qt.UserRole))
        return ids

    def apply_override(self):
        sel = self.selected_course_ids()
        if not sel: self.show_message("Seçim yok","Önce dersleri seçin.",QMessageBox.Warning); return
        val = self.override_spin.value()
        for cid in sel: self.per_course_durations[cid]=val
        self.show_message("Uygulandı", f"Seçili derslere {val} dk olarak ayarlandı.")

    def run_scheduler(self):
        try:
            start = self.start_date.date().toPython(); end = self.end_date.date().toPython()
            times = [t.strip() for t in self.times_edit.text().split(",") if t.strip()]
            duration = self.duration_spin.value(); bekleme = self.bekleme_spin.value()
            skip_weekends = self.skip_weekends_cb.isChecked()
            no_sim = self.no_simult_cb.isChecked()
            selected = self.selected_course_ids()
            if not selected: self.show_message("Seçim yok","En az bir ders seçin.",QMessageBox.Warning); return
            scheduler = ExamScheduler(self.db, times_per_day=times, bekleme_suresi_minutes=bekleme, no_simultaneous_exams=no_sim)
            scheduled, failed = scheduler.schedule(start, end, selected_course_ids=selected,
                                                   duration_default=duration, per_course_durations=self.per_course_durations,
                                                   bolum=self.bolum, skip_weekends=skip_weekends,
                                                   excluded_weekdays=None, excluded_dates=None,
                                                   no_simultaneous_exams=no_sim)
            self.last_scheduled = scheduled
            self.output_text.clear()
            self.output_text.append(f"✅ Planlanan: {len(scheduled)}")
            for se in scheduled:
                self.output_text.append(f"{se['ders_kod']} - {se['ders_ad']} | {se['tarih']} {se['saat'].strftime('%H:%M')} | {se['derslik_ad']}")
            if failed:
                self.output_text.append(f"\n⚠ Planlanamayan: {len(failed)}")
                for f in failed: 
                    c = f.get("course")
                    k = c.get("kod") if isinstance(c, dict) else (c[1] if isinstance(c, (list,tuple)) and len(c)>1 else str(c))
                    self.output_text.append(f"{k} -> {f.get('reason')}")
            # enable save excel
            if scheduled:
                fname = scheduler.export_to_excel(scheduled, filename="sinav_takvimi.xlsx")
                self.output_text.append(f"\nExcel kaydedildi: {fname}")
                self.save_excel_btn.setEnabled(True)
        except Exception as e:
            self.output_text.setText(f"❌ Hata: {e}")

    def save_last_excel(self):
        if not self.last_scheduled:
            self.show_message("Yok","Önce plan oluşturun",QMessageBox.Warning); return
        path,_ = QFileDialog.getSaveFileName(self,"Excel Kaydet","sinav_takvimi.xlsx","Excel Files (*.xlsx)")
        if not path: return
        df_rows=[]
        for se in self.last_scheduled:
            df_rows.append({
                "Ders Kodu":se['ders_kod'],"Ders Adı":se['ders_ad'],"Tarih":se['tarih'],"Saat":se['saat'].strftime("%H:%M"),
                "Derslik":se['derslik_ad'],"Süre":se['sure'],"Öğrenci Sayısı":se.get('n_students',0)
            })
        pd.DataFrame(df_rows).to_excel(path,index=False)
        self.show_message("Kaydedildi",f"Excel kaydedildi: {path}")

# Simple seat planner: assigns students to seats sequentially and can export PDF
class SeatPlanner:
    def __init__(self, db: Database):
        self.db = db

    def get_students_for_exam(self, sinav_id):
        row = self.db.execute("SELECT ders_id, derslik_id, tarih, saat FROM sinavlar WHERE id=%s", (sinav_id,), fetchone=True)
        if not row: return []
        ders_id = row[0]
        studs = self.db.execute("SELECT ogrenci_no FROM ogrenci_ders WHERE ders_id=%s ORDER BY ogrenci_no", (ders_id,), fetchall=True)
        return [s[0] for s in studs]

    def get_room_info(self, derslik_id):
        return self.db.execute("SELECT ad,enine_sira,boyuna_sira,sira_yapisi FROM derslikler WHERE id=%s", (derslik_id,), fetchone=True)

    def assign_seats(self, sinav_id):
        row = self.db.execute("SELECT ders_id, derslik_id FROM sinavlar WHERE id=%s", (sinav_id,), fetchone=True)
        if not row: raise RuntimeError("Sınav bulunamadı")
        ders_id = row[0]; derslik_id = row[1]
        students = self.get_students_for_exam(sinav_id)
        room = self.get_room_info(derslik_id)
        if not room: raise RuntimeError("Derslik bilgisi yok")
        ad,enine,boyuna,sira = room
        capacity = enine*boyuna
        if len(students) > capacity:
            raise RuntimeError(f"Kapasite yetersiz: {len(students)} öğrenci, kapasite {capacity}")
        assignments = []
        idx=0
        for r in range(int(boyuna)):
            for c in range(int(enine)):
                if idx >= len(students): break
                assignments.append({"ogrenci_no":students[idx][0] if isinstance(students[idx], tuple) else students[idx],
                                    "row":r+1,"col":c+1})
                idx+=1
            if idx>=len(students): break
        # save to DB oturma tablos (clear existing for this sinav)
        self.db.execute("DELETE FROM oturma WHERE sinav_id=%s", (sinav_id,))
        for a in assignments:
            self.db.execute("INSERT INTO oturma (sinav_id, ogrenci_no, sira, sutun) VALUES (%s,%s,%s,%s)",
                            (sinav_id, a['ogrenci_no'], a['row'], a['col']))
        return assignments

    def export_pdf(self, sinav_id, output_path):
        info = self.db.execute("SELECT s.id, d.kod, d.ad, s.tarih, s.saat, l.ad, l.enine_sira, l.boyuna_sira FROM sinavlar s JOIN dersler d ON s.ders_id=d.id JOIN derslikler l ON s.derslik_id=l.id WHERE s.id=%s", (sinav_id,), fetchone=True)
        if not info: raise RuntimeError("Sınav bulunamadı")
        _, ders_kod, ders_ad, tarih, saat, room_ad, enine, boyuna = info
        # get assignments
        assigns = self.db.execute("SELECT o.ogrenci_no, ogr.adsoyad, o.sira, o.sutun FROM oturma o JOIN ogrenciler ogr ON o.ogrenci_no=ogr.no WHERE o.sinav_id=%s ORDER BY o.sira, o.sutun", (sinav_id,), fetchall=True)
        c = canvas.Canvas(output_path, pagesize=A4)
        c.setFont("Helvetica-Bold", 14); c.drawString(40,800, f"{ders_kod} - {ders_ad} Oturma Planı")
        c.setFont("Helvetica",10); c.drawString(40,785, f"Tarih: {tarih} Saat: {saat.strftime('%H:%M')} Derslik: {room_ad}")
        y=760
        c.setFont("Helvetica",9)
        c.drawString(40,y, "No"); c.drawString(120,y,"Ad Soyad"); c.drawString(360,y,"Sıra"); c.drawString(420,y,"Sütun"); y-=14
        for a in assigns:
            c.drawString(40,y, str(a[0])); c.drawString(120,y, str(a[1])); c.drawString(360,y, str(a[2])); c.drawString(420,y, str(a[3])); y-=12
            if y < 60:
                c.showPage(); y=800
        c.save()
        return output_path

if __name__ == "__main__":
    db = Database()
    db.connect()
    app = QApplication(sys.argv)
    win = CoordinatorPanel(db, bolum_adi="Bilgisayar Mühendisliği")
    win.show()
    sys.exit(app.exec())
