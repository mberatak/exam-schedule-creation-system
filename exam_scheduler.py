# exam_scheduler.py
import pandas as pd
from datetime import datetime, date, time, timedelta
from connection import Database

def generate_dates(start_date: date, end_date: date, skip_weekends=True, excluded_weekdays=None, excluded_dates=None):
    excluded_weekdays = set(excluded_weekdays or [])
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
        # Load rooms ordered by capacity DESC so larger rooms are tried first
        if bolum:
            rows = self.db.execute("SELECT id, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi FROM derslikler WHERE bolum=%s ORDER BY kapasite DESC", (bolum,), fetchall=True)
        else:
            rows = self.db.execute("SELECT id, kod, ad, kapasite, enine_sira, boyuna_sira, sira_yapisi FROM derslikler ORDER BY kapasite DESC", fetchall=True)
        rooms=[]
        for r in rows:
            rooms.append({"id":r[0],"kod":r[1],"ad":r[2],"kapasite":r[3],"enine":r[4],"boyuna":r[5],"sira":r[6]})
        return rooms

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
        bekleme = getattr(self, "bekleme_suresi_minutes", 15)

        # Eski oturma kayıtlarını temizle
        try:
            self.db.execute("TRUNCATE TABLE oturma RESTART IDENTITY CASCADE;")
            
        except Exception as e:
            # Eğer TRUNCATE desteklenmiyorsa DELETE kullan
            self.db.execute("DELETE FROM oturma;")

        #  Dersleri ve sınıfları yüklüyoruz
        courses = self.load_courses(filter_ids=selected_course_ids)
        courses.sort(key=lambda c: (c['sinif'], -c['n_students']))
        rooms = self.load_rooms(bolum=bolum)
        if not rooms:
            raise RuntimeError("Derslik bulunamadı!")

        #  Tarih listesi 
        date_list = list(generate_dates(start_date, end_date, skip_weekends=skip_weekends,
                                        excluded_weekdays=excluded_weekdays, excluded_dates=excluded_dates))
        if not date_list:
            raise RuntimeError("Verilen tarih aralığında kullanılabilir gün yok.")

        #  Hazırlık 
        scheduled = []
        failed = []
        student_schedule = {}   # öğrenci_no -> [(start, end)]
        class_day_count = {}    # (sınıf, gün) -> count
        room_index = 0          # round-robin için oda göstergesi

        for course in courses:
            placed = False
            dur = per_course_durations.get(course['id'], duration_default)
            
            # Her ders için farklı oda başlangıcı
            start_room_index = room_index

            for d in date_list:
                for t in self.times_per_day:
                    # aynı anda başka sınav varsa ve kısıt aktifse geç
                    if no_simultaneous_exams and any(s['tarih'] == d and s['saat'] == t for s in scheduled):
                        continue

                    for i in range(len(rooms)):
                        room = rooms[(start_room_index + i) % len(rooms)]

                        # aynı saat ve günde o oda dolu mu?
                        if any(s['tarih'] == d and s['saat'] == t and s['derslik_id'] == room['id'] for s in scheduled):
                            continue
                        # Odanın kapasitesi yetersizse atla
                        if room['kapasite'] < course['n_students']:
                            continue

                        # öğrenci çakışması kontrolü
                        cand_start = datetime.combine(d, t)
                        cand_end = cand_start + timedelta(minutes=dur)
                        conflict = False
                        for stu in course['students']:
                            for (st, en) in student_schedule.get(stu, []):
                                overlap = not (cand_end <= st or en <= cand_start)
                                if overlap or 0 <= (cand_start - en).total_seconds()/60.0 < bekleme or \
                                0 <= (st - cand_end).total_seconds()/60.0 < bekleme:
                                    conflict = True
                                    break
                            if conflict:
                                break
                        if conflict:
                            continue

                        # aynı sınıftan aynı güne fazla sınav olmasın
                        class_key = (course['sinif'], d)
                        if class_day_count.get(class_key, 0) >= 2:
                            continue

                        # Planı oluştur
                        rec = {
                            "ders_id": course['id'],
                            "ders_kod": course['kod'],
                            "ders_ad": course['ad'],
                            "tarih": d,
                            "saat": t,
                            "sure": dur,
                            "derslik_id": room['id'],
                            "derslik_ad": room['ad'],
                            "kapasite": room['kapasite'],
                            "n_students": course['n_students'],
                            "sinif": course['sinif']
                        }
                        scheduled.append(rec)

                        # öğrenci takvimi güncelle
                        for stu in course['students']:
                            student_schedule.setdefault(stu, []).append((cand_start, cand_end))

                        class_day_count[class_key] = class_day_count.get(class_key, 0) + 1

                        placed = True
                        break  # bu oda seçildi
                    if placed:
                        break
                if placed:
                    break

            # Her dersten sonra oda indexini artır
            room_index = (room_index + 1) % len(rooms)

            if not placed:
                failed.append({"course": course, "reason": "Uygun slot / derslik bulunamadı"})

        #  Veritabanına yaz 
        sinav_id_map = {}  # ders_id -> sinav_id mapping
        for se in scheduled:
            try:
                # Insert ve oluşturulan sinav_id'yi al
                result = self.db.execute(
                    "INSERT INTO sinavlar (ders_id, tarih, saat, sure, derslik_id) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (se['ders_id'], se['tarih'], se['saat'], se['sure'], se['derslik_id']),
                    fetchone=True
                )
                if result:
                    sinav_id = result[0]
                    sinav_id_map[se['ders_id']] = sinav_id
                    se['sinav_id'] = sinav_id  # scheduled listesine de ekle
            except Exception as e:
                failed.append({"course": se, "reason": f"DB insert hatası: {e}"})

        # Oturma planlarını otomatik oluştur
        seating_errors = []
        for se in scheduled:
            if 'sinav_id' in se:
                try:
                    self._create_seating_for_exam(se['sinav_id'], se['ders_id'], se['derslik_id'])
                except Exception as e:
                    seating_errors.append(f"{se['ders_kod']}: {e}")
        
        if seating_errors:
            for err in seating_errors:
                failed.append({"course": {"kod": "OTURMA"}, "reason": err})

        return scheduled, failed

    def _create_seating_for_exam(self, sinav_id: int, ders_id: int, derslik_id: int):
        """Belirli bir sınav için oturma planı oluşturur."""
        # Öğrencileri al
        studs = self.db.execute(
            "SELECT ogrenci_no FROM ogrenci_ders WHERE ders_id=%s ORDER BY ogrenci_no",
            (ders_id,), fetchall=True
        )
        students = [s[0] for s in studs] if studs else []
        
        # Derslik bilgisini al
        room = self.db.execute(
            "SELECT enine_sira, boyuna_sira FROM derslikler WHERE id=%s",
            (derslik_id,), fetchone=True
        )
        if not room:
            raise RuntimeError(f"Derslik bulunamadı (ID: {derslik_id})")
        
        enine, boyuna = room
        capacity = int(enine) * int(boyuna)
        
        if len(students) > capacity:
            raise RuntimeError(f"Kapasite yetersiz: {len(students)} öğrenci, kapasite {capacity}")
        
        # Mevcut oturma kayıtlarını temizle
        self.db.execute("DELETE FROM oturma WHERE sinav_id=%s", (sinav_id,))
        
        # Oturma planını oluştur
        idx = 0
        for r in range(int(boyuna)):
            for c in range(int(enine)):
                if idx >= len(students):
                    break
                self.db.execute(
                    "INSERT INTO oturma (sinav_id, ogrenci_no, sira, sutun) VALUES (%s, %s, %s, %s)",
                    (sinav_id, students[idx], r + 1, c + 1)
                )
                idx += 1
            if idx >= len(students):
                break

    def export_to_excel(self, scheduled_exams, filename="sinav_takvimi.xlsx", exam_type=None):
        rows = []
        for se in scheduled_exams:
            tarih_str = se["tarih"].strftime("%Y-%m-%d") if hasattr(se["tarih"], "strftime") else str(se["tarih"])
            saat_str = se["saat"].strftime("%H:%M") if hasattr(se["saat"], "strftime") else str(se["saat"])

            kapasite = se.get("kapasite")
            if kapasite is None and hasattr(self, "db"):
                try:
                    cap_row = self.db.execute(
                        "SELECT kapasite FROM derslikler WHERE id=%s",
                        (se["derslik_id"],),
                        fetchone=True
                    )
                    if cap_row:
                        kapasite = cap_row[0]
                except Exception:
                    kapasite = None

            rows.append({
                "Sınav Türü": exam_type if exam_type else "",  # <— EK
                "Ders ID": se["ders_id"],
                "Ders Kodu": se["ders_kod"],
                "Ders Adı": se["ders_ad"],
                "Sınıf": se.get("sinif", ""),
                "Tarih": tarih_str,
                "Saat": saat_str,
                "Süre (dk)": se["sure"],
                "Derslik ID": se["derslik_id"],
                "Derslik Adı": se.get("derslik_ad", ""),
                "Derslik Kapasitesi": kapasite if kapasite is not None else "",
            })

        df = pd.DataFrame(rows)
        with pd.ExcelWriter(filename, engine="openpyxl", datetime_format="YYYY-MM-DD", date_format="YYYY-MM-DD") as writer:
            df.to_excel(writer, index=False, sheet_name="Sınav Takvimi")
            ws = writer.sheets["Sınav Takvimi"]
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        if cell.value:
                            max_len = max(max_len, len(str(cell.value)))
                    except Exception:
                        pass
                ws.column_dimensions[col_letter].width = max_len + 2
        return filename
