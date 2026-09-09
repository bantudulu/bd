from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cari = (ROOT / "app/templates/customer/cari.html").read_text(encoding="utf-8")
cleaning = (ROOT / "app/templates/customer/cleaning.html").read_text(encoding="utf-8")
final_api = (ROOT / "app/routers/final_api.py").read_text(encoding="utf-8")

checks = [
    ('<span>Rumah</span><b>Mulai Rp60rb</b>', cari),
    ('<span>Rumah</span><b>Mulai Rp70rb/jam</b>', cari),
    ('<span>Harian</span><b>Mulai Rp50rb</b>', cari),
    ('<span>Harian</span><b>Mulai Rp70rb</b>', cari),
    ('<span>Kesehatan</span><b>Mulai Rp100rb</b>', cari),
    ('<span>Kecantikan</span><b>Mulai Rp200rb</b>', cari),
    ('<span>Acara</span><b>Mulai Rp500rb</b>', cari),
    ("function currentTotal()", cleaning),
    ("totalEl.textContent=rupiah(currentTotal())", cleaning),
    ("total:String(currentTotal())", cleaning),
    ('"tukang": {"tukang", "pipa & listrik"}', final_api),
    ('re.sub(r"^>\\s*", "di atas ", text)', final_api),
    ('item.get("label") or item.get("key")', final_api),
]
for token, source in checks:
    assert token in source, f"missing expected fix: {token}"

for stale in [
    '<span>Rumah</span><b>Mulai Rp35rb</b>',
    '<span>Harian</span><b>Mulai Rp15rb</b>',
    '<span>Kesehatan</span><b>Mulai Rp70rb</b>',
    '<span>Kecantikan</span><b>Mulai Rp100rb</b>',
    '<span>Acara</span><b>Mulai Rp150rb</b>',
]:
    assert stale not in cari, f"stale price still present: {stale}"

print("BANTUDULU FRONTEND + PRICE FIX GATE: PASS")
