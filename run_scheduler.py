# run_scheduler.py
from exam_scheduler import ExamScheduler
from connection import Database
from datetime import date

db = Database(host="localhost", database="exam_schedule_db", user="postgres", password="thisisapassword")
db.connect()

scheduler = ExamScheduler(db,
                          times_per_day=["09:00","13:30","17:00"],
                          bekleme_suresi_minutes=15,
                          no_simultaneous_exams=False)

start = date(2025, 6, 1)
end = date(2025, 6, 14)
scheduled, failed = scheduler.schedule(start, end, duration_minutes=75, bolum=None,
                                       skip_weekends=True, excluded_dates=None,
                                       no_simultaneous_exams=False)

print("Planlanan sınav sayısı:", len(scheduled))
print("Planlanamayan ders sayısı:", len(failed))
for f in failed:
    print("FAILED:", f["course"]["kod"] if "course" in f and "kod" in f["course"] else f, "->", f["reason"])

# Excel export
if scheduled:
    fname = scheduler.export_to_excel(scheduled, filename="outputs/exam_schedule.xlsx")
    print("Excel çıktı:", fname)

db.close()
