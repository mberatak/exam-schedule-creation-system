# exam_scheduler.py
import pandas as pd
from datetime import datetime, date, time, timedelta
from connection import Database

def generate_dates(start_date: date, end_date: date, skip_weekends=True, excluded_dates=None):
    """start_date, end_date: date objeleri. excluded_dates: set of date objeleri."""
    excluded_dates = excluded_dates or set()
    d = start_date
    while d <= end_date:
        if skip_weekends and d.weekday() >= 5:  # 5=Sat,6=Sun
            d += timedelta(days=1)
            continue
        if d in excluded_dates:
            d += timedelta(days=1)
            continue
        yield d
        d += timedelta(days=1)

def time_from_str(s):
    # expects "HH:MM" or "H:MM"
    h, m = s.split(":")
    return time(int(h), int(m))

class ExamScheduler:
    def __init__(self, db: Database, times_per_day=None, bekleme_suresi_minutes=15, no_simultaneous_exams=False):
        """
        times_per_day: list of "HH:MM" strings representing possible start times each day (ordered)
        bekleme_suresi_minutes: minimum minutes between two exams of same student
        no_simultaneous_exams: if True, ensures only one exam runs at any given time globally
        """
        self.db = db
        self.times_per_day = times_per_day or ["09:00", "13:30", "17:00"]
        self.times_per_day = [time_from_str(t) for t in self.times_per_day]
        self.bekleme = timedelta(minutes=bekleme_suresi_minutes)
        self.no_simultaneous = no_simultaneous_exams

    def load_courses(self, filter_course_ids=None):
        """Return list of dicts: {id, kod, ad, student_count, student_list}"""
        q = "SELECT id, kod, ad FROM dersler"
        if filter_course_ids:
            # filter_course_ids is list
            placeholders = ",".join(["%s"] * len(filter_course_ids))
            q += f" WHERE id IN ({placeholders})"
            rows = self.db.execute(q, tuple(filter_course_ids), fetchall=True)
        else:
            rows = self.db.execute(q, fetchall=True)

        courses = []
        for (cid, kod, ad) in rows:
            studs = self.db.execute("SELECT ogrenci_no FROM ogrenci_ders WHERE ders_id=%s", (cid,), fetchall=True)
            students = [r[0] for r in studs] if studs else []
            courses.append({
                "id": cid,
                "kod": kod,
                "ad": ad,
                "students": students,
                "n_students": len(students)
            })
        return courses

    def load_rooms(self, bolum=None):
        """Return list of dicts of derslikler: {id, ad/kod, kapasite, enine, boyuna, sira}"""
        if bolum:
            rows = self.db.execute("SELECT id, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi FROM derslikler WHERE bolum=%s ORDER BY kapasite", (bolum,), fetchall=True)
        else:
            rows = self.db.execute("SELECT id, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi FROM derslikler ORDER BY kapasite", fetchall=True)
        rooms = []
        for r in rows:
            rooms.append({
                "id": r[0], "kod": r[1], "ad": r[2], "kapasite": r[3], "enine": r[4], "boyuna": r[5], "sira": r[6]
            })
        return rooms

    def slot_conflicts(self, schedule_map, exam_date, exam_time, duration_minutes):
        """
        schedule_map: mapping (date,time) -> list of scheduled exam dicts
        returns True if slot is occupied (global single-exam constraint)
        """
        if not self.no_simultaneous:
            return False
        key = (exam_date, exam_time)
        return key in schedule_map and len(schedule_map[key]) > 0

    def student_has_conflict(self, student_no, student_exam_schedule, cand_date, cand_time, duration_minutes):
        """
        student_exam_schedule: dict student_no -> list of (date, time, duration_minutes)
        returns True if conflict considering bekleme_suresi
        """
        if student_no not in student_exam_schedule:
            return False
        cand_dt = datetime.combine(cand_date, cand_time)
        for (d, t, dur) in student_exam_schedule[student_no]:
            other_dt = datetime.combine(d, t)
            # If times overlap or within bekleme window, conflict.
            # Simplify: consider start times and bekleme both sides.
            # If abs(start_diff) < (duration + bekleme) => conflict
            diff = abs((cand_dt - other_dt))
            # allow non-overlap if diff >= (duration + bekleme)
            if diff < timedelta(minutes=duration_minutes) + self.bekleme:
                return True
        return False

    def schedule(self, start_date: date, end_date: date, duration_minutes=75, bolum=None,
                 skip_weekends=True, excluded_dates=None, no_simultaneous_exams=False):
        """
        Main scheduling function.
        Returns: scheduled_exams list and failed list (couldn't place)
        """
        # set option
        self.no_simultaneous = no_simultaneous_exams

        # load data
        courses = self.load_courses()
        if bolum:
            # filter by courses where dersler.bolum == bolum (if you store bolum)
            # assume dersler table has bolum column; if not, skip
            courses = [c for c in courses if True]  # default keep all unless filtering is needed

        # sort courses by decreasing student count (place big ones first)
        courses.sort(key=lambda x: x["n_students"], reverse=True)

        rooms = self.load_rooms(bolum=bolum)
        if not rooms:
            raise RuntimeError("Derslik bulunamadı!")

        # Prepare date-time slots iteration
        excluded = set(excluded_dates) if excluded_dates else set()
        date_iter = list(generate_dates(start_date, end_date, skip_weekends=skip_weekends, excluded_dates=excluded))

        # prepare schedule structures
        schedule_map = {}  # (date,time) -> list of scheduled exam dicts
        student_exam_schedule = {}  # student_no -> list of (date,time,duration)
        scheduled_exams = []
        failed = []

        for course in courses:
            placed = False
            # find a room with sufficient capacity
            candidate_rooms = [r for r in rooms if r["kapasite"] >= course["n_students"]]
            if not candidate_rooms:
                # no single room fits; try to allow multiple rooms? For now mark failed
                failed.append({"course": course, "reason": "Kapasite yetersiz (tek derslikle) -> çoklu derslik desteklenmiyor)"})
                continue

            # Prefer smallest room that fits
            candidate_rooms.sort(key=lambda r: r["kapasite"])

            # iterate over dates and times
            for d in date_iter:
                if placed:
                    break
                for t in self.times_per_day:
                    if placed:
                        break
                    # global simultaneous constraint
                    if self.slot_conflicts(schedule_map, d, t, duration_minutes):
                        continue

                    # try rooms in order
                    for room in candidate_rooms:
                        # check if room already booked at this slot
                        key = (d, t, room["id"])
                        room_booked = any(se["derslik_id"] == room["id"] and se["tarih"] == d and se["saat"] == t for se in scheduled_exams)
                        if room_booked:
                            continue

                        # check student conflicts
                        conflict_found = False
                        for stu in course["students"]:
                            if self.student_has_conflict(stu, student_exam_schedule, d, t, duration_minutes):
                                conflict_found = True
                                break
                        if conflict_found:
                            continue

                        # if all good, assign
                        sch = {
                            "ders_id": course["id"],
                            "ders_kod": course["kod"],
                            "ders_ad": course["ad"],
                            "tarih": d,
                            "saat": t,
                            "sure": duration_minutes,
                            "derslik_id": room["id"],
                            "derslik_ad": room["ad"],
                            "n_students": course["n_students"]
                        }
                        scheduled_exams.append(sch)
                        schedule_map.setdefault((d, t), []).append(sch)
                        # update students schedule
                        for stu in course["students"]:
                            student_exam_schedule.setdefault(stu, []).append((d, t, duration_minutes))
                        placed = True
                        break  # break room loop

            if not placed:
                failed.append({"course": course, "reason": "Uygun tarih/saat/oda bulunamadı"})

        # After placing, write to DB (optionally clear existing sinavlar for date range)
        # We will insert scheduled_exams into sinavlar
        for se in scheduled_exams:
            try:
                self.db.execute(
                    "INSERT INTO sinavlar (ders_id, tarih, saat, sure, derslik_id) VALUES (%s, %s, %s, %s, %s)",
                    (se["ders_id"], se["tarih"], se["saat"], se["sure"], se["derslik_id"])
                )
            except Exception as e:
                # If insertion fails, add to failed list
                failed.append({"course": se, "reason": f"DB insert hatası: {e}"})

        return scheduled_exams, failed

    def export_to_excel(self, scheduled_exams, filename="exam_schedule.xlsx"):
        # Build DataFrame
        rows = []
        for se in scheduled_exams:
            rows.append({
                "Ders ID": se["ders_id"],
                "Ders Kodu": se["ders_kod"],
                "Ders Adı": se["ders_ad"],
                "Tarih": se["tarih"],
                "Saat": se["saat"].strftime("%H:%M"),
                "Süre (dk)": se["sure"],
                "Derslik ID": se["derslik_id"],
                "Derslik Adı": se.get("derslik_ad", "")
            })
        df = pd.DataFrame(rows)
        df.to_excel(filename, index=False)
        return filename