from connection import Database

db = Database(host="localhost", database="exam_schedule_db", user="exam_user", password="1234")
db.connect()

db.add_user(
    ad="Furkan Yılmaz",
    email="furkan@kocaeli.edu.tr",
    sifre_plain="1234",
    rol="koordinator",      # or "admin"
    bolum="Bilgisayar Mühendisliği"
)

db.close()
print("✅ User added successfully.")