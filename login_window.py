
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QMessageBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import QRect
from PySide6.QtGui import QPainter, QImage
from passlib.hash import sha256_crypt 
from connection import Database

try:
    from admin_panel import AdminPanel
    from coordinator_panel import CoordinatorPanel
except ImportError as e:
    class AdminPanel(QWidget): pass 
    class CoordinatorPanel(QWidget): pass

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dinamik Sınav Takvimi - Giriş")
        self.setFixedSize(750, 400)

        self.db = Database()
        self.db.connect()
        
        self.admin_window = None
        self.coord_window = None
        

        self.title = QLabel("Kocaeli Üniversitesi Sınav Sistemi")
        self.title.setFont(QFont("Arial", 16, QFont.Bold))
        self.title.setStyleSheet("color: #ffffff; margin-bottom: 15px;")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("E-posta adresi")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Şifre")
        self.password_input.setEchoMode(QLineEdit.Password)

        self.login_button = QPushButton("Giriş")
        self.login_button.setStyleSheet("background-color: #3498db; color: white; padding: 5px; border-radius: 8px;")
        self.login_button.clicked.connect(self.check_login)

        # ekle
        layout = QVBoxLayout()
        layout.addWidget(self.title)
        layout.addWidget(self.email_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)
        self.setLayout(layout)

    def paintEvent(self, event):
        painter = QPainter(self)
        image = QImage('pics/bgimage.jpg')
        painter.drawImage(QRect(0, 0, self.width(), self.height()), image)

    def check_login(self):
        email = self.email_input.text().strip()
        sifre = self.password_input.text().strip()

        if not email or not sifre:
            QMessageBox.warning(self, "Uyarı", "Lütfen e-posta ve şifre giriniz.")
            return

    
        user_data = self.db.get_user_by_email(email) 
        
        if user_data:
            
            rol, bolum, sifre_hash = user_data[3], user_data[4], user_data[5]
            
            
            if sha256_crypt.verify(sifre, sifre_hash): 
                
                QMessageBox.information(self, "Giriş Başarılı", f"Hoşgeldiniz {rol} ({bolum})")

                
                if rol == "admin":
                    print("Admin paneline yönlendiriliyor...")
                    if self.admin_window is None:
                        
                        self.admin_window = AdminPanel(self.db) 
                    self.hide()  
                    self.admin_window.show() 
                    
                else: 
                    print("Koordinatör paneline yönlendiriliyor...")
                    if self.coord_window is None:
                        
                        self.coord_window = CoordinatorPanel(self.db) 
                    self.hide() 
                    self.coord_window.show() 

            else:
                QMessageBox.critical(self, "Hata", "Geçersiz e-posta veya şifre!")
        else:
            
            QMessageBox.critical(self, "Hata", "Geçersiz e-posta veya şifre!")
            

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
