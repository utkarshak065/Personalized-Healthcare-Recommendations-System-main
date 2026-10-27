"""CareConnect module: accounts, health notes, map search, booking, doctor queue (SQLite, fictional data).
Mounted under /cc by main.py. Works without OpenAI/Snowflake/Postgres; OpenAI is used for note summaries only if OPENAI_API_KEY is set."""
import os, re, math, sqlite3, hashlib, secrets, datetime as dt
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

router = APIRouter(prefix="/cc", tags=["careconnect"])
DB = os.getenv("CC_DB_PATH", "careconnect.db")
CITIES = {"110001": ("New Delhi", "Delhi", 28.6139, 77.2090), "400001": ("Mumbai", "Maharashtra", 18.9402, 72.8347),
          "560001": ("Bengaluru", "Karnataka", 12.9716, 77.5946), "600001": ("Chennai", "Tamil Nadu", 13.0878, 80.2785),
          "700001": ("Kolkata", "West Bengal", 22.5726, 88.3639), "500001": ("Hyderabad", "Telangana", 17.3850, 78.4867),
          "411001": ("Pune", "Maharashtra", 18.5204, 73.8567), "682001": ("Kochi", "Kerala", 9.9312, 76.2673)}
SPECS = ["General Medicine", "Cardiology", "Dermatology", "Pulmonology", "Gastroenterology", "Neurology"]
DISEASES = [
 ("Common Cold", "Respiratory", "cough sneezing runny nose sore throat mild fever", "Clinical history", "Rest, fluids, symptomatic relief", "General Medicine"),
 ("Asthma", "Respiratory", "wheezing shortness breath chest tightness cough", "Spirometry", "Inhaler therapy as prescribed", "Pulmonology"),
 ("Hypertension", "Cardiovascular", "headache dizziness chest pain blurred vision", "Blood pressure monitoring", "Lifestyle changes, prescribed medication", "Cardiology"),
 ("Eczema", "Skin", "itching rash dry skin redness", "Skin examination", "Moisturisers, topical treatment", "Dermatology"),
 ("Gastritis", "Digestive", "stomach pain nausea bloating heartburn vomiting", "Clinical exam, endoscopy if needed", "Dietary changes, prescribed medication", "Gastroenterology"),
 ("Migraine", "Neurological", "headache nausea light sensitivity visual aura", "Clinical history", "Trigger avoidance, prescribed medication", "Neurology")]
RED_FLAGS = ["chest pain", "shortness of breath", "difficulty breathing", "severe bleeding", "unconscious", "fainting", "slurred speech", "seizure", "suicidal", "face drooping"]
NOTE = "Demo data only. Not medical advice; no real availability or coverage. Consult a licensed clinician."
EMERGENCY = "Some of what you described can signal an emergency. Call your local emergency number (112 in India) or go to the nearest emergency department now instead of waiting for an appointment."
HOURS = [9, 10, 11, 12, 14, 15, 16]

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
def _hash(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()
def _user(c, email, name, role, pw, doctor_id=None):
    s = secrets.token_hex(8)
    c.execute("INSERT INTO users(email,name,role,pw_hash,salt,doctor_id) VALUES(?,?,?,?,?,?)", (email, name, role, _hash(pw, s), s, doctor_id))

def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE, name TEXT, role TEXT, pw_hash TEXT, salt TEXT, doctor_id INT);
    CREATE TABLE IF NOT EXISTS tokens(token TEXT PRIMARY KEY, user_id INT);
    CREATE TABLE IF NOT EXISTS hospitals(hospital_id INTEGER PRIMARY KEY, name TEXT, pin TEXT, city TEXT, state TEXT, lat REAL, lon REAL);
    CREATE TABLE IF NOT EXISTS doctors(doctor_id INTEGER PRIMARY KEY, name TEXT, license_no TEXT, specialty TEXT, hospital_id INT, rating REAL, fee INT, years INT);
    CREATE TABLE IF NOT EXISTS diseases(disease_id INTEGER PRIMARY KEY, name TEXT, category TEXT, symptoms TEXT, diagnosis TEXT, treatment TEXT, specialty TEXT);
    CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, user_id INT, text TEXT, disease TEXT, specialty TEXT, summary TEXT, urgent INT, created TEXT);
    CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY, user_id INT, doctor_id INT, slot TEXT, status TEXT, report_id INT, reason TEXT, UNIQUE(doctor_id, slot));
    """)
    if not c.execute("SELECT 1 FROM hospitals").fetchone():
        n = 0
        for i, (pin, (city, state, la, lo)) in enumerate(CITIES.items()):
            for j, h in enumerate(("Sample General Hospital", "Demo Care Centre")):
                cur = c.execute("INSERT INTO hospitals(name,pin,city,state,lat,lon) VALUES(?,?,?,?,?,?)",
                                (f"{city} {h}", pin, city, state, la + (0.012 if j else -0.014), lo + (-0.016 if j else 0.013)))
                for k in range(3):
                    n += 1
                    d = c.execute("INSERT INTO doctors(name,license_no,specialty,hospital_id,rating,fee,years) VALUES(?,?,?,?,?,?,?)",
                                  (f"Dr. Sample {n}", f"DEMO-{1000+n}", SPECS[(i + k + n) % len(SPECS)], cur.lastrowid,
                                   round(3.8 + (n * 7 % 12) / 10, 1), 400 + (n % 5) * 150, 3 + n % 20))
                    _user(c, f"doctor{n}@demo.test", f"Dr. Sample {n}", "doctor", "doctor123", d.lastrowid)
        c.executemany("INSERT INTO diseases(name,category,symptoms,diagnosis,treatment,specialty) VALUES(?,?,?,?,?,?)", DISEASES)
    c.commit(); c.close()
init()

def me(tok):
    c = conn(); u = c.execute("SELECT u.* FROM tokens t JOIN users u ON u.id=t.user_id WHERE t.token=?", (tok,)).fetchone(); c.close()
    if not u: raise HTTPException(401, "Please log in again")
    return u
def km(a, b, c_, d):
    p = math.pi / 180; x = math.sin((c_ - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c_ * p) * math.sin((d - b) * p / 2) ** 2
    return round(12742 * math.asin(math.sqrt(x)), 1)
def match(text):
    w = set(re.findall(r"[a-z]+", text.lower())); c = conn(); out = []
    for d in c.execute("SELECT * FROM diseases"):
        sy = set(d["symptoms"].split()); hit = w & sy
        if hit: out.append((len(hit) / len(sy), dict(d) | {"matched": sorted(hit), "score": round(len(hit) / len(sy), 2)}))
    c.close(); return [d for _, d in sorted(out, key=lambda t: -t[0])[:3]]
def summarize(text, m):
    base = f"Patient reports: {text.strip()[:240]}" + (f" Keyword pattern (unconfirmed): {m[0]['name']}." if m else "")
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            r = OpenAI().chat.completions.create(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), max_tokens=120, messages=[
                {"role": "system", "content": "Summarise the patient's own description for a doctor in two neutral sentences. Do not diagnose."},
                {"role": "user", "content": text[:1500]}])
            return r.choices[0].message.content.strip()
        except Exception: pass
    return base
def docs(pin, specialty="", sort="distance", max_km=1000.0):
    if pin not in CITIES: return []
    la, lo = CITIES[pin][2:]; c = conn()
    rows = c.execute("""SELECT d.doctor_id,d.name,d.license_no,d.specialty,d.rating,d.fee,d.years,h.name hospital,h.city,h.lat,h.lon FROM doctors d
        JOIN hospitals h ON h.hospital_id=d.hospital_id WHERE h.pin=? AND (?='' OR d.specialty=?)""", (pin, specialty, specialty)).fetchall(); c.close()
    out = [dict(r) | {"distance_km": km(la, lo, r["lat"], r["lon"])} for r in rows]
    out = [r for r in out if r["distance_km"] <= max_km]
    key = {"rating": lambda r: -r["rating"], "fee": lambda r: r["fee"]}.get(sort, lambda r: r["distance_km"])
    return sorted(out, key=key)

class Reg(BaseModel):
    email: str; name: str = ""; password: str
class Login(BaseModel):
    email: str; password: str
class Note(BaseModel):
    text: str
class Book(BaseModel):
    doctor_id: int; slot: str; report_id: int | None = None; reason: str = ""
class Status(BaseModel):
    status: str

@router.post("/register")
def register(r: Reg):
    if len(r.password) < 6: raise HTTPException(400, "Password must be at least 6 characters")
    c = conn()
    try: _user(c, r.email.strip().lower(), r.name, "patient", r.password); c.commit()
    except sqlite3.IntegrityError: raise HTTPException(409, "Email already registered")
    finally: c.close()
    return {"message": "Registered"}

@router.post("/login")
def login(r: Login):
    c = conn(); u = c.execute("SELECT * FROM users WHERE email=?", (r.email.strip().lower(),)).fetchone()
    if not u or _hash(r.password, u["salt"]) != u["pw_hash"]: c.close(); raise HTTPException(401, "Invalid email or password")
    t = secrets.token_urlsafe(24); c.execute("INSERT INTO tokens VALUES(?,?)", (t, u["id"])); c.commit(); c.close()
    return {"token": t, "name": u["name"], "role": u["role"]}

@router.get("/meta")
def meta(): return {"specialties": SPECS, "diseases": [d[0] for d in DISEASES], "pins": {p: v[0] for p, v in CITIES.items()}}

@router.get("/search")
def search(pin: str, specialty: str = "", sort: str = "distance", max_km: float = 1000):
    if pin not in CITIES: return {"center": None, "doctors": [], "note": NOTE}
    return {"center": {"lat": CITIES[pin][2], "lon": CITIES[pin][3]}, "doctors": docs(pin, specialty, sort, max_km), "note": NOTE}

@router.get("/nearby")
def nearby(pin: str, disease: str, sort: str = "distance"):
    c = conn(); d = c.execute("SELECT * FROM diseases WHERE name=?", (disease,)).fetchone(); c.close()
    if not d: raise HTTPException(404, "Unknown condition")
    return {"disease": dict(d), "doctors": docs(pin, d["specialty"], sort), "center": {"lat": CITIES[pin][2], "lon": CITIES[pin][3]} if pin in CITIES else None, "note": NOTE}

@router.post("/reports")
def add_report(n: Note, x_token: str = Header("")):
    u = me(x_token)
    if not n.text.strip(): raise HTTPException(400, "Describe what you are experiencing")
    m = match(n.text); top = m[0] if m else {"name": "Unclear", "specialty": "General Medicine"}
    urgent = int(any(f in n.text.lower() for f in RED_FLAGS)); summ = summarize(n.text, m)
    c = conn(); cur = c.execute("INSERT INTO reports(user_id,text,disease,specialty,summary,urgent,created) VALUES(?,?,?,?,?,?,?)",
        (u["id"], n.text.strip(), top["name"], top["specialty"], summ, urgent, dt.datetime.now().strftime("%Y-%m-%d %H:%M"))); c.commit(); c.close()
    return {"id": cur.lastrowid, "matches": m, "summary": summ, "urgent": bool(urgent), "emergency": EMERGENCY if urgent else "", "note": NOTE}

@router.get("/reports")
def reports(x_token: str = Header("")):
    u = me(x_token); c = conn()
    r = [dict(x) for x in c.execute("SELECT * FROM reports WHERE user_id=? ORDER BY id DESC", (u["id"],))]; c.close(); return r

@router.get("/slots")
def slots(doctor_id: int, date: str):
    try: day = dt.date.fromisoformat(date)
    except ValueError: raise HTTPException(400, "Bad date")
    if day < dt.date.today(): return []
    c = conn(); taken = {r[0] for r in c.execute("SELECT slot FROM appointments WHERE doctor_id=? AND status!='cancelled'", (doctor_id,))}; c.close()
    return [s for s in (f"{date} {h:02d}:00" for h in HOURS) if s not in taken]

@router.post("/appointments")
def book(b: Book, x_token: str = Header("")):
    u = me(x_token)
    if u["role"] != "patient": raise HTTPException(403, "Only patients can book")
    c = conn()
    try:
        c.execute("DELETE FROM appointments WHERE doctor_id=? AND slot=? AND status='cancelled'", (b.doctor_id, b.slot))
        cur = c.execute("INSERT INTO appointments(user_id,doctor_id,slot,status,report_id,reason) VALUES(?,?,?,?,?,?)",
                        (u["id"], b.doctor_id, b.slot, "requested", b.report_id, b.reason)); c.commit()
    except sqlite3.IntegrityError: raise HTTPException(409, "That slot was just taken. Pick another time.")
    finally: c.close()
    return {"id": cur.lastrowid, "status": "requested"}

@router.get("/appointments")
def appts(x_token: str = Header("")):
    u = me(x_token); c = conn()
    where, arg = ("a.doctor_id=?", u["doctor_id"]) if u["role"] == "doctor" else ("a.user_id=?", u["id"])
    rows = c.execute(f"""SELECT a.id,a.slot,a.status,a.reason,d.name doctor,d.specialty,h.name hospital,h.city,p.name patient,
        r.summary shared_summary,r.text shared_note,r.disease suspected,r.urgent FROM appointments a JOIN doctors d ON d.doctor_id=a.doctor_id
        JOIN hospitals h ON h.hospital_id=d.hospital_id JOIN users p ON p.id=a.user_id LEFT JOIN reports r ON r.id=a.report_id
        WHERE {where} ORDER BY a.slot""", (arg,)).fetchall(); c.close(); return [dict(r) for r in rows]

@router.post("/appointments/{aid}/status")
def set_status(aid: int, s: Status, x_token: str = Header("")):
    u = me(x_token); ok = {"patient": {"cancelled"}, "doctor": {"confirmed", "completed", "cancelled"}}[u["role"]]
    if s.status not in ok: raise HTTPException(403, "Not allowed")
    c = conn(); a = c.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    if not a or (a["user_id"] != u["id"] and a["doctor_id"] != u["doctor_id"]): c.close(); raise HTTPException(404, "Not found")
    c.execute("UPDATE appointments SET status=? WHERE id=?", (s.status, aid)); c.commit(); c.close(); return {"status": s.status}
