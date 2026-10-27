import os, datetime as dt, requests, pandas as pd, pydeck as pdk, streamlit as st

def _get(k, d):
    try: return st.secrets[k]
    except Exception: return os.getenv(k, d)
API = _get("FASTAPI_ENDPOINT", "http://127.0.0.1:8001").rstrip("/") + "/cc"
st.set_page_config(page_title="CareConnect", page_icon="🩺", layout="wide")
st.markdown("""<style>
.hero{background:linear-gradient(120deg,#0b6b5f,#1b9e8a);color:#fff;padding:24px 28px;border-radius:16px;margin-bottom:16px}
.hero h1{margin:0;color:#fff}.hero p{margin:6px 0 0;opacity:.92}
.dcard{border:1px solid rgba(128,150,145,.4);border-radius:14px;padding:14px 16px;margin-bottom:6px;background:rgba(255,255,255,.88);color:#12302b}
.pill{display:inline-block;background:#d9f3ec;color:#075247;border-radius:99px;padding:2px 10px;font-size:.78rem;margin-right:6px}
.st{display:inline-block;border-radius:99px;padding:2px 10px;font-size:.78rem;background:#fff1c9;color:#6b4e00}
.st.confirmed,.st.completed{background:#d9f3ec;color:#075247}.st.cancelled{background:#fde3e1;color:#7a1c14}
</style>""", unsafe_allow_html=True)
S = st.session_state

def api(method, path, **kw):
    try:
        r = requests.request(method, API + path, headers={"X-Token": S.get("cc_token", "")}, timeout=15, **kw)
        if r.ok: return r.json()
        st.error(r.json().get("detail", "Request failed"))
        if r.status_code == 401 and S.get("cc_token"):
            for k in [k for k in S if k.startswith("cc_")]: del S[k]
            st.rerun()
    except requests.RequestException: st.error(f"Cannot reach the API at {API}. Start FastAPI first.")

@st.cache_data(ttl=300)
def meta(url): return requests.get(url + "/meta", timeout=10).json()

st.markdown('<div class="hero"><h1>🩺 CareConnect</h1><p>Describe how you feel, find nearby specialists on the map, and book a visit. Demo data only, not medical advice.</p></div>', unsafe_allow_html=True)

if "cc_token" not in S:
    a, b = st.columns(2)
    with a:
        t1, t2 = st.tabs(["Log in", "Create patient account"])
        with t1:
            e = st.text_input("Email", key="le"); p = st.text_input("Password", type="password", key="lp")
            if st.button("Log in", type="primary"):
                r = api("POST", "/login", json={"email": e, "password": p})
                if r: S.update(cc_token=r["token"], cc_name=r["name"], cc_role=r["role"]); st.rerun()
        with t2:
            n = st.text_input("Full name"); e2 = st.text_input("Email", key="re"); p2 = st.text_input("Password (6+ characters)", type="password", key="rp")
            if st.button("Create account", type="primary") and api("POST", "/register", json={"email": e2, "name": n, "password": p2}):
                st.success("Account created. Log in to continue.")
    b.info("**Demo doctor login:** doctor1@demo.test / doctor123\n\nDoctors see their queue, an AI-assisted summary and any note the patient chose to share.")
    st.stop()

c1, c2 = st.columns([6, 1]); c1.markdown(f"Signed in as **{S.cc_name}** ({S.cc_role})")
if c2.button("Log out"):
    for k in [k for k in S if k.startswith("cc_")]: del S[k]
    st.rerun()

def badge(s): return f'<span class="st {s}">{s}</span>'

def appt_list(role):
    rows = api("GET", "/appointments") or []
    if not rows: st.info("No appointments yet.")
    for a in rows:
        who = a["patient"] if role == "doctor" else f"{a['doctor']} · {a['specialty']}"
        urgent = " 🚨 urgent symptoms flagged" if a.get("urgent") else ""
        st.markdown(f'<div class="dcard"><b>{a["slot"]}</b> {badge(a["status"])}{urgent}<br>{who}<br>{a["hospital"]}, {a["city"]}</div>', unsafe_allow_html=True)
        if a["reason"]: st.caption(f"Reason: {a['reason']}")
        if a["shared_summary"]: st.caption(f"Shared summary: {a['shared_summary']}")
        if a["status"] in ("requested", "confirmed"):
            opts = ([("Confirm", "confirmed")] if role == "doctor" and a["status"] == "requested" else []) + ([("Mark completed", "completed")] if role == "doctor" and a["status"] == "confirmed" else []) + [("Cancel", "cancelled")]
            cols = st.columns(len(opts) + 3)
            for i, (lab, val) in enumerate(opts):
                if cols[i].button(lab, key=f"{val}{a['id']}") and api("POST", f"/appointments/{a['id']}/status", json={"status": val}): st.rerun()

if S.cc_role == "doctor":
    st.subheader("Your appointment queue"); appt_list("doctor"); st.stop()

def results(data, prefix):
    if not data or not data.get("center"): st.warning("No sample results for this PIN code."); return
    docs = data["doctors"]
    if not docs: st.info("No doctors match these filters."); return
    df = pd.DataFrame(docs); c = data["center"]
    layers = [pdk.Layer("ScatterplotLayer", df, get_position="[lon, lat]", get_radius=380, get_fill_color=[11, 122, 107, 210], pickable=True),
              pdk.Layer("ScatterplotLayer", pd.DataFrame([c]), get_position="[lon, lat]", get_radius=220, get_fill_color=[220, 60, 60, 230])]
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=c["lat"], longitude=c["lon"], zoom=11.3),
                             tooltip={"text": "{name}\n{specialty} · ★{rating}\n{hospital}\nFee ₹{fee}"}))
    st.caption("Red dot = city centre. Hover a green dot for details.")
    mynotes = api("GET", "/reports") or []
    for d in docs:
        st.markdown(f'<div class="dcard"><b>{d["name"]}</b> <span class="pill">{d["specialty"]}</span><span class="pill">★ {d["rating"]}</span><span class="pill">₹{d["fee"]}</span><span class="pill">{d["years"]} yrs</span><br>'
                    f'{d["hospital"]}, {d["city"]} · {d["distance_km"]} km from city centre · <a href="https://www.google.com/maps/dir/?api=1&destination={d["lat"]},{d["lon"]}" target="_blank">Get directions</a></div>', unsafe_allow_html=True)
        with st.expander(f"Book {d['name']}"):
            day = st.date_input("Date", dt.date.today() + dt.timedelta(days=1), min_value=dt.date.today(), key=f"{prefix}d{d['doctor_id']}")
            sl = api("GET", "/slots", params={"doctor_id": d["doctor_id"], "date": day.isoformat()}) or []
            if not sl: st.caption("No free slots that day.")
            else:
                slot = st.selectbox("Time", sl, key=f"{prefix}s{d['doctor_id']}", format_func=lambda x: x[11:])
                rep = st.selectbox("Share a health note with the doctor", [None] + mynotes, key=f"{prefix}r{d['doctor_id']}",
                                   format_func=lambda x: "Don't share" if x is None else f"{x['created']} · {x['text'][:50]}")
                why = st.text_input("Reason for visit (optional)", key=f"{prefix}w{d['doctor_id']}")
                if st.button("Request appointment", type="primary", key=f"{prefix}b{d['doctor_id']}") and api("POST", "/appointments", json={"doctor_id": d["doctor_id"], "slot": slot, "report_id": rep["id"] if rep else None, "reason": why}):
                    st.success(f"Requested {slot} with {d['name']}. Track it under My appointments.")

M = meta(API); pins = M["pins"]; loc = lambda p: f"{pins[p]} ({p})"
t1, t2, t3, t4 = st.tabs(["Find care", "My health notes", "Nearby by condition", "My appointments"])
with t1:
    a, b, c_, d_ = st.columns(4)
    pin = a.selectbox("Location", list(pins), format_func=loc, key="fp"); sp = b.selectbox("Specialty", ["Any"] + M["specialties"])
    sort = c_.selectbox("Sort by", ["distance", "rating", "fee"]); mk = d_.slider("Max distance (km)", 1, 30, 30)
    if st.button("Search", type="primary"): S.cc_find = api("GET", "/search", params={"pin": pin, "specialty": "" if sp == "Any" else sp, "sort": sort, "max_km": mk})
    if S.get("cc_find"): results(S.cc_find, "f")
with t2:
    txt = st.text_area("What are you experiencing?", placeholder="e.g. headache for three days with nausea and light sensitivity", height=110)
    if st.button("Save note", type="primary"):
        r = api("POST", "/reports", json={"text": txt})
        if r:
            if r["urgent"]: st.error(r["emergency"])
            st.success("Saved. You can share it when you book.")
            st.write(f"**Summary for your doctor:** {r['summary']}")
            for m in r["matches"]: st.write(f"**Possible match: {m['name']}** → {m['specialty']} ({int(m['score']*100)}% keyword overlap: {', '.join(m['matched'])})")
            st.caption(r["note"])
    st.subheader("Saved notes")
    for n in api("GET", "/reports") or []:
        st.markdown(f'<div class="dcard"><b>{n["created"]}</b> <span class="pill">{n["disease"]}</span><span class="pill">{n["specialty"]}</span>{"🚨" if n["urgent"] else ""}<br>{n["text"]}</div>', unsafe_allow_html=True)
with t3:
    a, b, c_ = st.columns(3)
    dz = a.selectbox("Condition", M["diseases"]); pn = b.selectbox("Location", list(pins), format_func=loc, key="np"); so = c_.selectbox("Sort by", ["distance", "rating", "fee"], key="ns")
    if st.button("Show nearby specialists", type="primary"): S.cc_near = api("GET", "/nearby", params={"pin": pn, "disease": dz, "sort": so})
    if S.get("cc_near"):
        d = S.cc_near["disease"]; st.write(f"**{d['name']}** ({d['category']}) → see a **{d['specialty']}** specialist. Typical approach: {d['treatment']}.")
        results(S.cc_near, "n")
with t4: appt_list("patient")
