import tkinter as tk
from tkinter import filedialog, messagebox
import re
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# Beklenen Excel sütunları
REQUIRED_COLS = ["Öğrenci No", "Ad Soyad", "Sınıf", "Ders"]

def norm_code(x):
    if x is None:
        return None
    return str(x).strip().upper()

def clean_sinif(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    m = re.search(r"\d+", s)
    if not m:
        return None
    try:
        return int(m.group())
    except Exception:
        return None

def log(msg: str):
    txt_log.config(state="normal")
    txt_log.insert("end", msg + "\n")
    txt_log.see("end")
    txt_log.config(state="disabled")
    txt_log.update_idletasks()

def enable_ui(enabled: bool):
    state = ("normal" if enabled else "disabled")
    for w in (
        entry_host, entry_port, entry_dbname, entry_user, entry_pass,
        entry_students, entry_courses, btn_pick_students, btn_pick_courses, btn_start
    ):
        w.config(state=state)
    root.config(cursor="" if enabled else "watch")

def select_students():
    path = filedialog.askopenfilename(
        title="Öğrenci Listesi Seç (.xlsx)",
        filetypes=[("Excel Files", "*.xlsx")]
    )
    if path:
        entry_students.delete(0, tk.END)
        entry_students.insert(0, path)

def select_courses():
    path = filedialog.askopenfilename(
        title="Ders Listesi Seç (.xlsx) - Opsiyonel",
        filetypes=[("Excel Files", "*.xlsx")]
    )
    if path:
        entry_courses.delete(0, tk.END)
        entry_courses.insert(0, path)

def validate_excel_columns(df: pd.DataFrame):
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError("Excel eksik kolon(lar): " + ", ".join(missing))

def start_process():
    students_path = entry_students.get().strip()
    courses_path  = entry_courses.get().strip() or None
    if not students_path:
        messagebox.showwarning("Eksik Bilgi", "Lütfen öğrenci Excel dosyasını seçin.")
        return

    db_host = entry_host.get().strip() or "localhost"
    db_port = int(entry_port.get().strip() or 5432)
    db_name = entry_dbname.get().strip() or "exam_schedule_db"
    db_user = entry_user.get().strip() or "exam_user"
    db_pass = entry_pass.get()

    enable_ui(False)
    txt_log.config(state="normal"); txt_log.delete("1.0", "end"); txt_log.config(state="disabled")
    log("▶ İşlem başladı...")

    conn = None
    cur = None
    try:
        # Excel oku
        try:
            df = pd.read_excel(students_path, engine="openpyxl")
        except ImportError:
            raise RuntimeError("Excel okumak için 'openpyxl' gerekli. 'pip install openpyxl' komutuyla kurun.")
        except Exception as e:
            raise RuntimeError(f"Öğrenci Excel okunamadı: {e}")

        # Sütunları doğrula
        validate_excel_columns(df)
        log("✓ Excel sütun kontrolü OK.")

        # Normalize
        df["Öğrenci No"] = df["Öğrenci No"].astype(str).str.strip()
        df["Ad Soyad"]   = df["Ad Soyad"].astype(str).str.strip()
        df["Sınıf"]      = df["Sınıf"].apply(clean_sinif)   # INT/None
        df["Ders"]       = df["Ders"].map(norm_code)

        # DB bağlantısı
        try:
            conn = psycopg2.connect(
                host=db_host, port=db_port,
                dbname=db_name, user=db_user, password=db_pass
            )
        except Exception as e:
            raise RuntimeError(f"Veritabanına bağlanılamadı: {e}")

        conn.autocommit = False
        cur = conn.cursor()
        log("✓ Veritabanı bağlantısı OK.")

        # Ders sözlüğü
        try:
            cur.execute("SELECT id, kod FROM dersler")
            kod_to_id = {norm_code(kod): _id for _id, kod in cur.fetchall()}
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"'dersler' tablosu okunamadı: {e}")

        missing_courses = set()

        # TEKİLLEŞTİRME
        # Aynı öğrenci no birden fazla satırdaysa son görüleni alsın (ad, sınıf güncellenir)
        student_map = {}   # no -> (no, adsoyad, sinif)
        rel_set = set()    # (no, ders_id)

        for _, row in df.iterrows():
            no       = row["Öğrenci No"]
            adsoyad  = row["Ad Soyad"]
            sinif    = row["Sınıf"]
            ders_kod = row["Ders"]

            if not no or not ders_kod:
                continue

            ders_id = kod_to_id.get(ders_kod)
            if not ders_id:
                missing_courses.add(ders_kod)
                continue

            # Öğrenciyi map'e yaz (son satır kazanır)
            student_map[no] = (no, adsoyad, sinif)

            # İlişkiyi set ile tekilleştir
            rel_set.add((no, ders_id))

        upsert_students = list(student_map.values())
        rel_pairs = list(rel_set)

        dup_count = len(df["Öğrenci No"]) - len(student_map)
        if dup_count > 0:
            log(f"ℹ Aynı öğrenci numarasından birden fazla satır vardı. "
                f"{dup_count} kopya satır tekilleştirildi (son satır baz alındı).")

        # Öğrenci upsert (artık tekil)
        if upsert_students:
            insert_sql = """
                INSERT INTO ogrenciler(no, adsoyad, sinif)
                VALUES %s
                ON CONFLICT (no) DO UPDATE
                SET adsoyad = EXCLUDED.adsoyad,
                    sinif   = EXCLUDED.sinif;
            """
            try:
                execute_values(cur, insert_sql, upsert_students, page_size=1000)
                log(f"✓ Öğrenci upsert: {len(upsert_students)} kayıt.")
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Öğrenci upsert sırasında hata: {e}")

        # İlişki insert (zaten tekilleştirildi)
        if rel_pairs:
            rel_sql = """
                INSERT INTO ogrenci_ders(ogrenci_no, ders_id)
                VALUES %s
                ON CONFLICT DO NOTHING;
            """
            try:
                execute_values(cur, rel_sql, rel_pairs, page_size=1000)
                log(f"✓ İlişki eklendi: {len(rel_pairs)} satır.")
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"İlişki ekleme sırasında hata: {e}")

        # Commit
        conn.commit()
        log("✓ Commit tamam.")

        # Özet
        summary = (
            f"✅ Öğrenci upsert sayısı: {len(upsert_students)}\n"
            f"✅ İlişki eklenen sayısı: {len(rel_pairs)}"
        )
        if missing_courses:
            summary += "\n⚠️ Eşleşmeyen ders kodları:\n" + "\n".join(f" - {k}" for k in sorted(missing_courses))
        messagebox.showinfo("Tamamlandı", summary)

    except Exception as e:
        messagebox.showerror("Hata", str(e))
        log(f"⛔ Hata: {e}")

    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except Exception:
            pass
        enable_ui(True)
        log("⏹ İşlem bitti.")

# UI
root = tk.Tk()
root.title("Öğrenci-Ders Yükleme")
root.geometry("600x520")

tk.Label(root, text="Veritabanı Ayarları", font=("Arial", 11, "bold")).pack(pady=4)
frm_db = tk.Frame(root); frm_db.pack(pady=2)

tk.Label(frm_db, text="Host:").grid(row=0, column=0, sticky="e")
entry_host = tk.Entry(frm_db, width=18); entry_host.insert(0, "localhost"); entry_host.grid(row=0, column=1, padx=6)

tk.Label(frm_db, text="Port:").grid(row=0, column=2, sticky="e")
entry_port = tk.Entry(frm_db, width=8); entry_port.insert(0, "5432"); entry_port.grid(row=0, column=3, padx=6)

tk.Label(frm_db, text="DB Name:").grid(row=1, column=0, sticky="e")
entry_dbname = tk.Entry(frm_db, width=18); entry_dbname.insert(0, "exam_schedule_db"); entry_dbname.grid(row=1, column=1, padx=6)

tk.Label(frm_db, text="User:").grid(row=1, column=2, sticky="e")
entry_user = tk.Entry(frm_db, width=14); entry_user.insert(0, "exam_user"); entry_user.grid(row=1, column=3, padx=6)

tk.Label(frm_db, text="Password:").grid(row=2, column=0, sticky="e")
entry_pass = tk.Entry(frm_db, show="*", width=18); entry_pass.insert(0, "1234"); entry_pass.grid(row=2, column=1, padx=6)

tk.Label(root, text="Excel Dosyaları", font=("Arial", 11, "bold")).pack(pady=4)
frm_files = tk.Frame(root); frm_files.pack(pady=2)

tk.Label(frm_files, text="Öğrenci Listesi:").grid(row=0, column=0, sticky="e")
entry_students = tk.Entry(frm_files, width=48); entry_students.grid(row=0, column=1, padx=6)
btn_pick_students = tk.Button(frm_files, text="Seç...", command=select_students); btn_pick_students.grid(row=0, column=2)

tk.Label(frm_files, text="Ders Listesi (ops.):").grid(row=1, column=0, sticky="e")
entry_courses = tk.Entry(frm_files, width=48); entry_courses.grid(row=1, column=1, padx=6)
btn_pick_courses = tk.Button(frm_files, text="Seç...", command=select_courses); btn_pick_courses.grid(row=1, column=2)

btn_start = tk.Button(root, text="Yüklemeyi Başlat", command=start_process, width=28, height=2, bg="#4CAF50", fg="white")
btn_start.pack(pady=10)

tk.Label(root, text="Kayıt / Log", font=("Arial", 11, "bold")).pack(pady=2)
txt_log = tk.Text(root, height=12, state="disabled")
txt_log.pack(fill="both", padx=10, pady=4, expand=True)

root.mainloop()
