import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SolarYield",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@400;600;700;800&display=swap');

:root {
    --bg:        #0a0f0a;
    --surface:   #111811;
    --border:    #1e2e1e;
    --green:     #4ade80;
    --green-dim: #166534;
    --amber:     #fbbf24;
    --red:       #f87171;
    --blue:      #60a5fa;
    --muted:     #4b5e4b;
    --text:      #e2f0e2;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'DM Mono', monospace !important;
}

[data-testid="stAppViewContainer"] {
    background: 
        radial-gradient(ellipse 80% 50% at 50% -10%, rgba(74,222,128,0.07) 0%, transparent 60%),
        var(--bg) !important;
}

h1, h2, h3 { font-family: 'Syne', sans-serif !important; }

[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stSidebar"] { background: var(--surface) !important; }

.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--green), transparent);
}
.metric-label {
    font-size: 10px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
}
.metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: var(--green);
    line-height: 1;
}
.metric-value.warn  { color: var(--amber); }
.metric-value.alert { color: var(--red); }
.metric-unit {
    font-size: 11px;
    color: var(--muted);
    margin-top: 4px;
}

.anomaly-banner {
    background: rgba(248,113,113,0.1);
    border: 1px solid rgba(248,113,113,0.4);
    border-radius: 10px;
    padding: 14px 20px;
    margin-bottom: 8px;
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    color: var(--red);
    letter-spacing: 0.05em;
}
.normal-banner {
    background: rgba(74,222,128,0.07);
    border: 1px solid rgba(74,222,128,0.2);
    border-radius: 10px;
    padding: 14px 20px;
    margin-bottom: 8px;
    font-size: 13px;
    color: var(--green);
    letter-spacing: 0.05em;
}

.tilt-visual {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    text-align: center;
}

.section-header {
    font-family: 'Syne', sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin-bottom: 16px;
}

.growth-table {
    font-size: 12px;
}

div[data-testid="stNumberInput"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label {
    color: var(--muted) !important;
    font-size: 11px !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}

div[data-testid="stButton"] button {
    background: var(--green-dim) !important;
    border: 1px solid var(--green) !important;
    color: var(--green) !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 12px !important;
    letter-spacing: 0.1em !important;
    border-radius: 8px !important;
}
div[data-testid="stButton"] button:hover {
    background: rgba(74,222,128,0.2) !important;
}

.stPlotlyChart { border-radius: 12px; overflow: hidden; }

footer { display: none; }
#MainMenu { display: none; }
</style>
""", unsafe_allow_html=True)

# ─── Config ───────────────────────────────────────────────────────────────────
API_BASE = "https://solaryield-api.onrender.com"
ANOMALY_COLOURS = {
    "none":             "#4ade80",
    "heat_stress":      "#f87171",
    "soil_drought":     "#fbbf24",
    "low_humidity":     "#60a5fa",
    "light_deficiency": "#a78bfa",
    "voltage_drop":     "#fb923c",
    "irradiance_limited": "#6b7280",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=10)
def fetch_log(n: int = 360):
    try:
        r = requests.get(f"{API_BASE}/log?n={n}", timeout=8)
        if r.status_code == 200:
            return r.json().get("readings", [])
    except Exception:
        pass
    return []

@st.cache_data(ttl=30)
def fetch_growth():
    try:
        r = requests.get(f"{API_BASE}/growth", timeout=8)
        if r.status_code == 200:
            return r.json().get("entries", [])
    except Exception:
        pass
    return []

def post_growth(condition, day, height, water, notes):
    try:
        r = requests.post(f"{API_BASE}/growth", json={
            "condition": condition, "day": day,
            "height_cm": height, "water_ml": water, "notes": notes
        }, timeout=8)
        return r.status_code == 200
    except Exception:
        return False

def make_chart(df, y_col, color, title, unit):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df[y_col],
        mode="lines",
        line=dict(color=color, width=1.5),
        fill="tozeroy",
        fillcolor=color.replace(")", ",0.07)").replace("rgb", "rgba") if "rgb" in color else color + "12",
        hovertemplate=f"%{{y:.1f}} {unit}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(family="Syne", size=13, color="#4b5e4b"),
                   x=0, pad=dict(l=4)),
        plot_bgcolor="#111811",
        paper_bgcolor="#111811",
        font=dict(family="DM Mono", color="#4b5e4b", size=11),
        margin=dict(l=8, r=8, t=36, b=8),
        height=180,
        xaxis=dict(showgrid=False, showline=False, tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor="#1e2e1e", showline=False,
                   tickfont=dict(size=10)),
        hovermode="x unified",
    )
    return fig

def tilt_svg(angle: int, anomaly_type: str) -> str:
    color  = ANOMALY_COLOURS.get(anomaly_type, "#4ade80")
    rad    = angle * 3.14159 / 180
    import math
    w = 90
    cx, cy = 100, 110
    x1 = cx - (w/2) * math.cos(rad)
    y1 = cy + (w/2) * math.sin(rad)
    x2 = cx + (w/2) * math.cos(rad)
    y2 = cy - (w/2) * math.sin(rad)
    return f"""
    <svg viewBox="0 0 200 160" xmlns="http://www.w3.org/2000/svg" width="200" height="160">
      <rect width="200" height="160" fill="#111811" rx="12"/>
      <!-- Ground line -->
      <line x1="20" y1="140" x2="180" y2="140" stroke="#1e2e1e" stroke-width="1.5"/>
      <!-- Crop silhouettes -->
      <rect x="55" y="118" width="8" height="22" rx="2" fill="#166534" opacity="0.7"/>
      <rect x="75" y="112" width="8" height="28" rx="2" fill="#166534" opacity="0.7"/>
      <rect x="95" y="116" width="8" height="24" rx="2" fill="#166534" opacity="0.7"/>
      <rect x="115" y="110" width="8" height="30" rx="2" fill="#166534" opacity="0.7"/>
      <rect x="135" y="115" width="8" height="25" rx="2" fill="#166534" opacity="0.7"/>
      <!-- Panel support -->
      <line x1="{cx}" y1="{cy}" x2="{cx}" y2="140" stroke="#1e2e1e" stroke-width="1.5" stroke-dasharray="3,3"/>
      <!-- Panel -->
      <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"
            stroke="{color}" stroke-width="5" stroke-linecap="round"/>
      <!-- Angle label -->
      <text x="100" y="20" text-anchor="middle"
            font-family="Syne,sans-serif" font-size="22" font-weight="700"
            fill="{color}">{angle}°</text>
      <text x="100" y="34" text-anchor="middle"
            font-family="DM Mono,monospace" font-size="9" fill="#4b5e4b"
            letter-spacing="0.1em">TILT ANGLE</text>
    </svg>"""

# ─── Header ───────────────────────────────────────────────────────────────────
col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown("""
    <h1 style='font-family:Syne,sans-serif;font-size:2rem;font-weight:800;
               color:#4ade80;margin:0;letter-spacing:-0.02em;'>
        ☀ SolarYield
    </h1>
    <p style='color:#4b5e4b;font-size:11px;letter-spacing:0.15em;
              text-transform:uppercase;margin:2px 0 20px;'>
        ML-Optimised Agrivoltaic Control · Team J-43
    </p>
    """, unsafe_allow_html=True)

# ─── Auto-refresh toggle ──────────────────────────────────────────────────────
with col_status:
    st.markdown("<br>", unsafe_allow_html=True)
    auto_refresh = st.toggle("Auto-refresh", value=True)
    st.markdown(f"<p style='font-size:10px;color:#4b5e4b;'>{datetime.now().strftime('%H:%M:%S')}</p>",
                unsafe_allow_html=True)

# ─── Fetch data ───────────────────────────────────────────────────────────────
readings = fetch_log(360)

if not readings:
    st.markdown("""
    <div class='anomaly-banner'>
        ⚠ No data received yet — waiting for ESP32 to connect
    </div>
    """, unsafe_allow_html=True)
    if auto_refresh:
        time.sleep(5)
        st.rerun()
    st.stop()

latest = readings[-1]
df = pd.DataFrame(readings)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["power_mw"]  = df["voltage"] * df["current"]

# ─── Anomaly banner ───────────────────────────────────────────────────────────
atype = latest.get("anomaly_type", "none")
if latest.get("anomaly_detected"):
    st.markdown(f"""
    <div class='anomaly-banner'>
        🔴 ANOMALY DETECTED — {atype.upper().replace('_',' ')} &nbsp;|&nbsp;
        Panel tilted to {latest['tilt_angle']}°
    </div>""", unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class='normal-banner'>
        ✓ System nominal &nbsp;|&nbsp; Panel at {latest['tilt_angle']}° baseline
    </div>""", unsafe_allow_html=True)

# ─── Live metrics row ─────────────────────────────────────────────────────────
st.markdown("<div class='section-header'>Live Readings</div>", unsafe_allow_html=True)

def metric_html(label, value, unit, alert=False, warn=False):
    cls = "alert" if alert else ("warn" if warn else "")
    return f"""
    <div class='metric-card'>
        <div class='metric-label'>{label}</div>
        <div class='metric-value {cls}'>{value}</div>
        <div class='metric-unit'>{unit}</div>
    </div>"""

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
temp  = latest["temperature"]
hum   = latest["humidity"]
soil  = latest["soil_moisture"]
lux   = latest["lux"]
volts = latest["voltage"]
amps  = latest["current"]
tilt  = latest["tilt_angle"]
power = volts * amps

with c1: st.markdown(metric_html("Temperature", f"{temp:.1f}", "°C",
    alert=temp>35, warn=temp>30), unsafe_allow_html=True)
with c2: st.markdown(metric_html("Humidity", f"{hum:.1f}", "%",
    warn=hum<50), unsafe_allow_html=True)
with c3: st.markdown(metric_html("Soil Moisture", f"{soil:.0f}", "ADC raw",
    alert=soil<1500), unsafe_allow_html=True)
with c4: st.markdown(metric_html("Irradiance", f"{lux:.0f}", "lux"), unsafe_allow_html=True)
with c5: st.markdown(metric_html("Voltage", f"{volts:.2f}", "V",
    warn=volts<3.0), unsafe_allow_html=True)
with c6: st.markdown(metric_html("Current", f"{amps:.1f}", "mA"), unsafe_allow_html=True)
with c7: st.markdown(metric_html("Power", f"{power:.1f}", "mW"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── Tilt visual + anomaly history ───────────────────────────────────────────
col_tilt, col_hist = st.columns([1, 2])

with col_tilt:
    st.markdown("<div class='section-header'>Panel Position</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='tilt-visual'>{tilt_svg(tilt, atype)}</div>",
                unsafe_allow_html=True)

with col_hist:
    st.markdown("<div class='section-header'>Tilt Decision Log</div>", unsafe_allow_html=True)
    recent = df.tail(30)[["timestamp", "tilt_angle", "anomaly_type", "temperature",
                           "humidity", "soil_moisture"]].copy()
    recent["timestamp"] = recent["timestamp"].dt.strftime("%H:%M:%S")
    recent.columns      = ["Time", "Tilt °", "Anomaly", "Temp °C", "Hum %", "Soil"]
    recent              = recent.iloc[::-1]

    def colour_anomaly(val):
        c = ANOMALY_COLOURS.get(val, "#4b5e4b")
        return f"color: {c}"

    st.dataframe(
        recent.style.applymap(colour_anomaly, subset=["Anomaly"]),
        use_container_width=True,
        height=220,
        hide_index=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ─── Sensor time-series charts ────────────────────────────────────────────────
st.markdown("<div class='section-header'>Sensor History (Last Hour)</div>",
            unsafe_allow_html=True)

r1c1, r1c2 = st.columns(2)
r2c1, r2c2 = st.columns(2)
r3c1, r3c2 = st.columns(2)

with r1c1: st.plotly_chart(make_chart(df, "temperature", "#f87171", "Temperature", "°C"),
                            use_container_width=True)
with r1c2: st.plotly_chart(make_chart(df, "humidity", "#60a5fa", "Humidity", "%"),
                            use_container_width=True)
with r2c1: st.plotly_chart(make_chart(df, "soil_moisture", "#fbbf24", "Soil Moisture", "ADC"),
                            use_container_width=True)
with r2c2: st.plotly_chart(make_chart(df, "lux", "#a78bfa", "Irradiance", "lux"),
                            use_container_width=True)
with r3c1: st.plotly_chart(make_chart(df, "power_mw", "#4ade80", "Panel Power", "mW"),
                            use_container_width=True)
with r3c2: st.plotly_chart(make_chart(df, "tilt_angle", "#4ade80", "Tilt Angle", "°"),
                            use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── Growth log ───────────────────────────────────────────────────────────────
st.markdown("<div class='section-header'>Plant Growth Log — Cai Xin</div>",
            unsafe_allow_html=True)

tab_view, tab_add = st.tabs(["📊 View data", "➕ Add measurement"])

with tab_view:
    growth = fetch_growth()
    if growth:
        gdf = pd.DataFrame(growth)
        gdf["timestamp"] = pd.to_datetime(gdf["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(gdf[["timestamp","condition","day","height_cm","water_ml","notes"]],
                     use_container_width=True, hide_index=True)

        if len(gdf) > 1:
            fig_g = px.line(gdf, x="day", y="height_cm", color="condition",
                            markers=True,
                            color_discrete_map={"A":"#60a5fa","B":"#fbbf24","C":"#4ade80"},
                            labels={"height_cm":"Height (cm)","day":"Day","condition":"Condition"},
                            title="Plant Height by Condition")
            fig_g.update_layout(
                plot_bgcolor="#111811", paper_bgcolor="#111811",
                font=dict(family="DM Mono", color="#4b5e4b", size=11),
                title_font=dict(family="Syne", size=13, color="#4b5e4b"),
                margin=dict(l=8, r=8, t=36, b=8), height=280,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#1e2e1e"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig_g, use_container_width=True)
    else:
        st.markdown("<p style='color:#4b5e4b;font-size:12px;'>No growth data yet.</p>",
                    unsafe_allow_html=True)

with tab_add:
    ga, gb, gc = st.columns(3)
    with ga:
        g_condition = st.selectbox("Condition", ["A — Open field", "B — Fixed tilt", "C — SolarYield"])
        g_condition = g_condition[0]
    with gb:
        g_day    = st.number_input("Day", min_value=1, max_value=42, value=1)
    with gc:
        g_height = st.number_input("Height (cm)", min_value=0.0, value=5.0, step=0.5)

    gd, ge = st.columns(2)
    with gd: g_water = st.number_input("Water (mL)", min_value=0.0, value=0.0, step=10.0)
    with ge: g_notes = st.text_input("Notes (optional)")

    if st.button("Log measurement"):
        if post_growth(g_condition, int(g_day), g_height, g_water, g_notes):
            st.success("Logged!")
            st.cache_data.clear()
        else:
            st.error("Failed to log — check API connection")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("""
<hr style='border-color:#1e2e1e;margin-top:32px;'>
<p style='color:#4b5e4b;font-size:10px;letter-spacing:0.1em;text-align:center;'>
    SOLARYIELD · TEAM J-43 · YUVABHARATHI INTERNATIONAL SCHOOL · EIC 2026
</p>
""", unsafe_allow_html=True)

# ─── Auto-refresh ─────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(10)
    st.rerun()
