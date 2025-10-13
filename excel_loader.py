# excel_loader.py
import pandas as pd
from connection import Database

class ExcelLoader:
    def __init__(self, db: Database):
        self.db = db

    def load_dersler(self, file_path, bolum):
        df = pd.read_excel(file_path, header=None)
        current_class = None
        current_type = "Zorunlu"  # veya "Seçmeli"

        for i, row in df.iterrows():
            cell0 = str(row[0]).strip() if pd.notna(row[0]) else ""

            # === SINIF veya SEÇMELİ başlıklarını yakala ===
            if "Sınıf" in cell0:
                # Örn: "3. Sınıf"
                digits = ''.join(filter(str.isdigit, cell0))
                current_class = int(digits) if digits else None
                current_type = "Zorunlu"
                continue
            elif "SEÇMELİ" in cell0.upper():
                current_type = "Seçmeli"
                continue

            # Başlık satırını atla
            if "DERS KODU" in cell0.upper():
                continue

            # Geçerli ders satırı mı?
            if pd.notna(row[0]) and pd.notna(row[1]):
                ders_kodu = str(row[0]).strip()
                ders_adi = str(row[1]).strip()
                hoca = str(row[2]).strip() if pd.notna(row[2]) else ""

                sinif = current_class if current_class else 0
                zorunlu = (current_type != "Seçmeli")

                q = """
                INSERT INTO dersler (bolum, kod, ad, hoca, sinif, zorunlu)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (kod) DO NOTHING;
                """
                try:
                    self.db.execute(q, (bolum, ders_kodu, ders_adi, hoca, sinif, zorunlu))
                except Exception as e:
                    print(f"Hata ({ders_kodu}):", e)

        print("✅ Ders listesi başarıyla yüklendi.")


    def load_ogrenciler(self, file_path):
        df = pd.read_excel(file_path)
        required_cols = ["Öğrenci No", "Ad Soyad", "Sınıf", "Ders"]
        for c in required_cols:
            if c not in df.columns:
                raise ValueError(f"Excel'de '{c}' sütunu eksik!")

        for _, row in df.iterrows():
            no = str(row["Öğrenci No"]).strip()
            ad = str(row["Ad Soyad"]).strip()
            sinif = int(''.join(filter(str.isdigit, str(row["Sınıf"]))))
            ders_kodu = str(row["Ders"]).strip()

            # Öğrenci tablosuna ekle
            self.db.execute(
                """INSERT INTO ogrenciler (no, adsoyad, sinif)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (no) DO NOTHING;""",
                (no, ad, sinif)
            )

            # Ders ID’sini bul
            ders = self.db.execute("SELECT id FROM dersler WHERE kod=%s", (ders_kodu,), fetchone=True)
            if ders:
                ders_id = ders[0]
                self.db.execute(
                    """INSERT INTO ogrenci_ders (ogrenci_no, ders_id)
                       VALUES (%s, %s)
                       ON CONFLICT DO NOTHING;""",
                    (no, ders_id)
                )

        print("✅ Öğrenci listesi başarıyla yüklendi.")
