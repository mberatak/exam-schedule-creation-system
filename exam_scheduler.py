# exam_scheduler.py
import pandas as pd
from datetime import datetime, date, time, timedelta
from connection import Database

def generate_dates(start_date: date, end_date: date, skip_weekends=True, excluded_weekdays=None, excluded_dates=None):
    excluded_weekdays = set(excluded_weekdays or [])  # e.g. {5,6}
    excluded_dates = set(excluded_dates or [])
    d = start_date
    while d <= end_date:
        if skip_weekends and d.weekday() >= 5:
            d += timedelta(days=1); continue
        if d.weekday() in excluded_weekdays:
            d += timedelta(days=1); continue
        if d in excluded_dates:
            d += timedelta(days=1); continue
        yield d
        d += timedelta(days=1)

def time_from_str(s):
    h,m = s.split(":"); return time(int(h), int(m))

class ExamScheduler:
    def __init__(self, db: Database, times_per_day=None, bekleme_suresi_minutes=15, no_simultaneous_exams=False):
        self.db = db
        self.times_per_day = [time_from_str(t) for t in (times_per_day or ["09:00","13:30","17:00"])]
        self.bekleme = timedelta(minutes=bekleme_suresi_minutes)
        self.no_simultaneous = no_simultaneous_exams

    def load_courses(self, filter_ids=None):
        q = "SELECT id, kod, ad, sinif FROM dersler"
        params = ()
        if filter_ids:
            placeholders = ",".join(["%s"]*len(filter_ids))
            q += f" WHERE id IN ({placeholders})"
            params = tuple(filter_ids)
        rows = self.db.execute(q, params, fetchall=True)
        courses = []
        for cid,kod,ad,sinif in rows:
            studs = self.db.execute("SELECT ogrenci_no FROM ogrenci_ders WHERE ders_id=%s", (cid,), fetchall=True)
            students = [r[0] for r in studs] if studs else []
            courses.append({"id":cid,"kod":kod,"ad":ad,"sinif": sinif or 0,"students":students,"n_students":len(students)})
        return courses

    def load_rooms(self, bolum=None):
        if bolum:
            rows = self.db.execute("SELECT id, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi FROM derslikler WHERE bolum=%s ORDER BY kapasite", (bolum,), fetchall=True)
        else:
            rows = self.db.execute("SELECT id, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi FROM derslikler ORDER BY kapasite", fetchall=True)
        rooms=[]
        for r in rows:
            rooms.append({"id":r[0],"kod":r[1],"ad":r[2],"kapasite":r[3],"enine":r[4],"boyuna":r[5],"sira":r[6]})
        return rooms

    def student_has_conflict(self, student_exam_schedule, cand_date, cand_time, duration_minutes):
        cand_dt = datetime.combine(cand_date, cand_time)
        for (d,t,dur) in student_exam_schedule.get(student_exam_schedule_key(student_exam_schedule, None), []):
            pass
        # actual check below:
        for s, exams in student_exam_schedule.items():
            # we'll call per student outside, so not used
            pass

    def schedule(self, start_date: date, end_date: date, selected_course_ids=None,
                 duration_default=75, per_course_durations=None, bolum=None,
                 skip_weekends=True, excluded_weekdays=None, excluded_dates=None,
                 no_simultaneous_exams=False):
        """
        per_course_durations: dict course_id -> duration_minutes
        excluded_weekdays: iterable of weekday numbers to skip (0=Mon...6=Sun)
        """
        self.no_simultaneous = no_simultaneous_exams
        per_course_durations = per_course_durations or {}

        # load courses and rooms
        courses = self.load_courses(filter_ids=selected_course_ids)
        # sort by class and then by student count descending (helps distribution)
        courses.sort(key=lambda c: (c['sinif'], -c['n_students']))

        rooms = self.load_rooms(bolum=bolum)
        if not rooms:
            raise RuntimeError("Derslik bulunamadı!")

        date_list = list(generate_dates(start_date, end_date, skip_weekends=skip_weekends,
                                        excluded_weekdays=excluded_weekdays, excluded_dates=excluded_dates))
        if not date_list:
            raise RuntimeError("Verilen tarih aralığında kullanılabilir gün yok.")

        # Structures
        scheduled = []   # list of exam dicts
        failed = []
        student_schedule = {}  # student_no -> list of (datetime_start, datetime_end)

        # We'll try greedy: iterate courses, try to place them with heuristics
        # Additional constraint: spread same class across days: track how many exams placed per day per class
        class_day_count = {}  # (sinif, date) -> count

        for course in courses:
            placed=False
            dur = per_course_durations.get(course['id'], duration_default)
            for d in date_list:
                # prefer days where same class has fewer exams
                # iterate times
                for t in self.times_per_day:
                    # check global simultaneous
                    if no_simultaneous_exams and any(s['tarih']==d and s['saat']==t for s in scheduled):
                        continue
                    # find room that fits
                    candidate_rooms = [r for r in rooms if r['kapasite'] >= course['n_students']]
                    if not candidate_rooms:
                        failed.append({"course":course,"reason":"Kapasite yetersiz (tek derslikle sığmıyor)"})
                        placed=True
                        break
                    candidate_rooms.sort(key=lambda r: r['kapasite'])
                    for room in candidate_rooms:
                        # room availability
                        room_taken = any(s['tarih']==d and s['saat']==t and s['derslik_id']==room['id'] for s in scheduled)
                        if room_taken: continue
                        # student conflicts
                        conflict=False
                        cand_start = datetime.combine(d,t)
                        cand_end = cand_start + timedelta(minutes=dur)
                        for stu in course['students']:
                            exams = student_schedule.get(stu, [])
                            for (st,en) in exams:
                                # if overlap or within bekleme time (15 min default)
                                # require gap >= bekleme between end and next start
                                gap_before = (cand_start - en).total_seconds()/60.0 if en < cand_start else (st - cand_end).total_seconds()/60.0
                                # simpler: check overlap
                                if not (cand_end <= st or en <= cand_start):
                                    conflict=True; break
                                # also ensure bekleme 15 min between exams
                                if abs((cand_start - en).total_seconds()/60.0) < 15 and en <= cand_start:
                                    conflict=True; break
                                if abs((st - cand_end).total_seconds()/60.0) < 15 and st >= cand_end:
                                    conflict=True; break
                            if conflict: break
                        if conflict: continue
                        # class distribution heuristic: avoid placing too many same-class exams same day
                        class_key = (course['sinif'], d)
                        if class_day_count.get(class_key,0) >= 2:
                            # if already two for this class that day, skip to next slot
                            continue
                        # place
                        rec = {"ders_id":course['id'], "ders_kod":course['kod'], "ders_ad":course['ad'],
                               "tarih":d, "saat":t, "sure":dur, "derslik_id":room['id'], "derslik_ad":room['ad'],
                               "n_students":course['n_students'], "sinif": course['sinif']}
                        scheduled.append(rec)
                        # update student schedules
                        for stu in course['students']:
                            student_schedule.setdefault(stu, []).append((cand_start, cand_end))
                        class_day_count[class_key] = class_day_count.get(class_key,0) + 1
                        placed=True
                        break
                    if placed: break
                if placed: break
            if not placed:
                failed.append({"course":course,"reason":"Uygun slot / derslik bulunamadı"})

        # write scheduled into DB
        for se in scheduled:
            try:
                self.db.execute(
                    "INSERT INTO sinavlar (ders_id, tarih, saat, sure, derslik_id) VALUES (%s,%s,%s,%s,%s)",
                    (se['ders_id'], se['tarih'], se['saat'], se['sure'], se['derslik_id'])
                )
            except Exception as e:
                failed.append({"course":se,"reason":f"DB insert hatası: {e}"})

        return scheduled, failed

    def export_to_excel(self, scheduled_exams, filename="sinav_takvimi.xlsx"):
        rows=[]
        for se in scheduled_exams:
            rows.append({
                "Ders ID": se["ders_id"],
                "Ders Kodu": se["ders_kod"],
                "Ders Adı": se["ders_ad"],
                "Sınıf": se.get("sinif",""),
                "Tarih": se["tarih"],
                "Saat": se["saat"].strftime("%H:%M"),
                "Süre (dk)": se["sure"],
                "Derslik ID": se["derslik_id"],
                "Derslik Adı": se.get("derslik_ad",""),
                "Öğrenci Sayısı": se.get("n_students",0)
            })
        df = pd.DataFrame(rows)
        df.to_excel(filename, index=False)
        return filename
