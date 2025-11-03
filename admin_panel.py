# admin_panel.py
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QComboBox
)
from PySide6.QtWidgets import QAbstractItemView
from PySide6.QtCore import Qt
from connection import Database

class AdminPanel(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setWindowTitle("Admin Paneli - Kullanıcı Yönetimi")
        self.setMinimumSize(800, 500)

        # Form alanları
        self.ad_input = QLineEdit()
        self.ad_input.setPlaceholderText("Ad Soyad")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("E-posta")

        self.sifre_input = QLineEdit()
        self.sifre_input.setPlaceholderText("Şifre (geçici/ilk şifre)")
        self.sifre_input.setEchoMode(QLineEdit.Password)

        self.rol_input = QComboBox()
        self.rol_input.addItems(["Bilgisayar Mühendisliği", "Yazılım Mühendisliği", "Elektrik Mühendisliği", "Elektronik Mühendisliği", "İnşaat Mühendisliği"])

        self.bolum_input = QComboBox()
        self.bolum_input.addItems(["admin", "koordinator"])

        self.add_btn = QPushButton("Yeni Kullanıcı Ekle")
        self.add_btn.clicked.connect(self.add_user)

        # Arama / Güncelle / Sil
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ara (isim veya e-posta)")
        self.search_btn = QPushButton("Ara")
        self.search_btn.clicked.connect(self.search_users)

        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.clicked.connect(self.load_users)

        self.delete_btn = QPushButton("Seçili Kullanıcıyı Sil")
        self.delete_btn.clicked.connect(self.delete_selected_user)

        self.update_pwd_btn = QPushButton("Seçili Kullanıcının Şifresini Güncelle")
        self.update_pwd_btn.clicked.connect(self.update_password_dialog)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Ad", "E-posta", "Rol", "Bölüm"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows) # self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Layout
        form_layout = QHBoxLayout()
        form_layout.addWidget(self.ad_input)
        form_layout.addWidget(self.email_input)
        form_layout.addWidget(self.sifre_input)
        form_layout.addWidget(self.rol_input)
        form_layout.addWidget(self.bolum_input)
        form_layout.addWidget(self.add_btn)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(self.search_input)
        ctrl_layout.addWidget(self.search_btn)
        ctrl_layout.addWidget(self.refresh_btn)
        ctrl_layout.addWidget(self.delete_btn)
        ctrl_layout.addWidget(self.update_pwd_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addLayout(ctrl_layout)
        main_layout.addWidget(self.table)

        self.setLayout(main_layout)

        # load
        self.load_users()

    def show_message(self, title, text, icon=QMessageBox.Information):
        msg = QMessageBox()
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.exec()

    def add_user(self):
        ad = self.ad_input.text().strip()
        email = self.email_input.text().strip()
        sifre = self.sifre_input.text().strip()
        rol = self.rol_input.currentText()
        bolum = self.bolum_input.text().strip()

        if not (ad and email and sifre):
            self.show_message("Eksik Alan", "Ad, e-posta ve şifre girilmesi zorunludur.", QMessageBox.Warning)
            return

        try:
            self.db.add_user(ad, email, sifre, rol, bolum)
            self.show_message("Başarılı", "Kullanıcı eklendi.")
            self.ad_input.clear(); self.email_input.clear(); self.sifre_input.clear(); self.bolum_input.clear()
            self.load_users()
        except Exception as e:
            self.show_message("Hata", f"Kullanıcı eklenemedi: {e}", QMessageBox.Critical)

    def load_users(self):
        try:
            rows = self.db.list_users()
            self.table.setRowCount(0)
            for r in rows:
                row_pos = self.table.rowCount()
                self.table.insertRow(row_pos)
                for c, val in enumerate(r):
                    self.table.setItem(row_pos, c, QTableWidgetItem(str(val)))
            self.table.resizeColumnsToContents()
        except Exception as e:
            self.show_message("Hata", f"Kullanıcılar yüklenemedi: {e}", QMessageBox.Critical)

    def search_users(self):
        text = self.search_input.text().strip()
        try:
            rows = self.db.list_users(filter_text=text)
            self.table.setRowCount(0)
            for r in rows:
                row_pos = self.table.rowCount()
                self.table.insertRow(row_pos)
                for c, val in enumerate(r):
                    self.table.setItem(row_pos, c, QTableWidgetItem(str(val)))
            self.table.resizeColumnsToContents()
        except Exception as e:
            self.show_message("Hata", f"Ara hatası: {e}", QMessageBox.Critical)

    def get_selected_email(self):
        sel = self.table.selectedItems()
        if not sel:
            return None
        # email sütunu index 2
        row = sel[0].row()
        item = self.table.item(row, 2)
        return item.text() if item else None

    def delete_selected_user(self):
        email = self.get_selected_email()
        if not email:
            self.show_message("Seçim Yok", "Lütfen silmek için bir kullanıcı seçin.", QMessageBox.Warning)
            return
        if QMessageBox.question(self, "Onay", f"{email} silinsin mi?") == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete_user_by_email(email)
                self.show_message("Başarılı", "Kullanıcı silindi.")
                self.load_users()
            except Exception as e:
                self.show_message("Hata", f"Silme başarısız: {e}", QMessageBox.Critical)

    def update_password_dialog(self):
        email = self.get_selected_email()
        if not email:
            self.show_message("Seçim Yok", "Lütfen şifre güncellemek için bir kullanıcı seçin.", QMessageBox.Warning)
            return
        # basit input dialog
        from PySide6.QtWidgets import QInputDialog
        new_pwd, ok = QInputDialog.getText(self, "Yeni Şifre", f"{email} için yeni şifreyi girin:", QLineEdit.Password)
        if ok and new_pwd:
            try:
                self.db.update_password(email, new_pwd)
                self.show_message("Başarılı", "Şifre güncellendi.")
            except Exception as e:
                self.show_message("Hata", f"Şifre güncellenemedi: {e}", QMessageBox.Critical)


if __name__ == "__main__":
    # DB bilgilerini ihtiyaç ise buradan değiştir
    db = Database(host="localhost", database="exam_schedule_db", user="exam_user", password="1234", port=5432)
    db.connect()

    app = QApplication(sys.argv)
    w = AdminPanel(db)
    w.show()
    sys.exit(app.exec())