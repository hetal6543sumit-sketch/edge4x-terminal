import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
import io
import yfinance as yf
import pyotp

# --- IMPORT AI ENGINE MODULE & DATABASE MANAGER ---
try:
    from edge4x_intel_engine import render_ai_intelligence_tab, DuckDBManager
except ImportError:
    render_ai_intelligence_tab = None
    DuckDBManager = None

# --- ANGEL ONE SECURE API WRAPPER ---
try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None

# --- 1. PAGE SETUP ---
st.set_page_config(
    page_title="EDGE4X | Institutional Terminal", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- 2. GLOBAL STATE MANAGEMENT ---
if 'eod_data_processed' not in st.session_state:
    st.session_state.eod_data_processed = False
if 'fii_net_futures' not in st.session_state:
    st.session_state.fii_net_futures = 0.0
if 'fii_dod_delta' not in st.session_state:
    st.session_state.fii_dod_delta = 0.0
if 'smart_money_score' not in st.session_state:
    st.session_state.smart_money_score = 0.0
if 'market_regime' not in st.session_state:
    st.session_state.market_regime = "AWAITING EOD DATA"
if 'participant_matrix_curr' not in st.session_state:
    st.session_state.participant_matrix_curr = None
if 'participant_matrix_prev' not in st.session_state:
    st.session_state.participant_matrix_prev = None
if 'delivery_stats' not in st.session_state:
    st.session_state.delivery_stats = {}

# --- 3. LIVE BROKER API AUTHENTICATION ---
@st.cache_resource(ttl=3600, show_spinner=False)
def connect_angel_one():
    if SmartConnect is None:
        return None, "SmartApi library not installed locally"
    try:
        if "angel_one" not in st.secrets:
            return None, "Secrets not configured in secrets.toml"
            
        api_key = st.secrets["angel_one"]["api_key"]
        client_id = st.secrets["angel_one"]["client_id"]
        mpin = st.secrets["angel_one"]["mpin"]
        totp_secret = st.secrets["angel_one"]["totp_secret"]

        if "YOUR_" in api_key or "YOUR_" in client_id:
            return None, "Default placeholder keys detected"

        smart_obj = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_secret).now()
        session_data = smart_obj.generateSession(client_id, mpin, totp)
        
        if session_data.get('status') is True:
            return smart_obj, "Connected"
        else:
            return None, session_data.get('message', 'Login rejected by Angel One')
    except Exception as e:
        return None, str(e)

angel_api, connection_message = connect_angel_one()

if angel_api:
    api_status_text = "API CONNECTED"
    api_status_color = "#39D353"
else:
    api_status_text = f"API DISCONNECTED ({connection_message})"
    api_status_color = "#FF5C5C"

# --- 4. MASTER CSS: GRAPHITE & CHAMPAGNE-GOLD ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    :root {{
        --bg-base: #080A0D;
        --bg-surface: #11151A;
        --bg-elevated: #151A20;
        --border-subtle: rgba(255, 255, 255, 0.08);
        --text-primary: #F5F7FA;
        --text-secondary: #A7AFBA;
        --text-muted: #6F7782;
        --gold-primary: #D4AF37; 
        --accent-green: #39D353; 
        --accent-red: #FF5C5C;   
    }}

    html, body, [class*="css"], .stApp {{
        font-family: 'Inter', sans-serif !important;
        background-color: var(--bg-base) !important;
        color: var(--text-primary) !important;
        font-variant-numeric: tabular-nums;
        font-size: 14.5px; 
    }}

    *[data-stale="true"] {{
        opacity: 1 !important; filter: none !important;
        transition: none !important; pointer-events: auto !important;
    }}
    .stSpinner {{ display: none !important; }}
    [data-testid="stSidebar"] {{ display: none !important; }}
    #MainMenu, header, footer {{ visibility: hidden; }}
    
    .block-container {{ padding-top: 105px !important; padding-bottom: 30px !important; max-width: 1600px; }}

    /* FIXED TOP BAR */
    .terminal-nav {{
        position: fixed; top: 0; left: 0; right: 0; height: 60px;
        background: rgba(8, 10, 13, 0.95); backdrop-filter: blur(12px);
        border-bottom: 1px solid var(--border-subtle); z-index: 999999;
        display: flex; justify-content: space-between; align-items: center; padding: 0 40px;
    }}
    .nav-brand {{ font-weight: 800; letter-spacing: 2.5px; color: var(--text-primary); font-size: 1.3rem; }}
    .nav-brand span {{ color: var(--gold-primary); }}
    .nav-status {{ font-size: 0.8rem; color: var(--text-secondary); font-weight: 600; display: flex; align-items: center; gap: 8px; }}
    .live-dot {{ height: 7px; width: 7px; background-color: {api_status_color}; border-radius: 50%; display: inline-block; box-shadow: 0 0 8px {api_status_color}; }}

    /* FIXED LIVE TICKER STRIP */
    .ticker-wrap {{
        position: fixed; top: 60px; left: 0; right: 0; height: 35px; z-index: 999998;
        background-color: var(--bg-elevated); border-bottom: 1px solid var(--border-subtle);
        display: flex; align-items: center; overflow: hidden;
        color: var(--text-secondary); font-size: 0.85rem; font-weight: 600; white-space: nowrap;
    }}
    .ticker {{ display: inline-block; animation: ticker 35s linear infinite; padding-left: 100%; }}
    .ticker-item {{ padding: 0 2rem; border-right: 1px solid var(--border-subtle); }}
    .t-up {{ color: var(--accent-green); }} .t-dn {{ color: var(--accent-red); }}
    @keyframes ticker {{ 0% {{ transform: translate3d(0, 0, 0); }} 100% {{ transform: translate3d(-100%, 0, 0); }} }}

    /* HORIZONTAL NAVIGATION PILLS */
    div[role="radiogroup"] {{
        display: flex !important; flex-direction: row !important; justify-content: center !important; flex-wrap: wrap !important;
        gap: 6px !important; background: var(--bg-surface) !important; padding: 8px 12px !important;
        border-radius: 8px !important; border: 1px solid var(--border-subtle) !important; margin-bottom: 25px !important;
    }}
    div[role="radiogroup"] label {{
        background: transparent !important; border: none !important; color: var(--text-muted) !important;
        padding: 8px 16px !important; font-weight: 600 !important; font-size: 0.8rem !important;
        letter-spacing: 0.5px !important; border-radius: 6px !important; transition: all 0.2s ease !important;
    }}
    div[role="radiogroup"] label:hover {{ color: var(--text-primary) !important; background: rgba(255, 255, 255, 0.03) !important; }}
    div[role="radiogroup"] label[data-checked="true"] {{
        color: #000000 !important; background: var(--gold-primary) !important;
        box-shadow: 0 4px 10px rgba(212, 175, 55, 0.15) !important;
    }}

    /* UI PANELS & METRIC CARDS */
    .panel-box {{ background: var(--bg-surface); border: 1px solid var(--border-subtle); padding: 20px; border-radius: 8px; margin-bottom: 18px; }}
    .panel-header {{ font-size: 0.82rem; color: var(--gold-primary); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 12px; font-weight: 700; }}
    .section-header {{ font-size: 1.05rem; color: var(--text-primary); text-transform: uppercase; letter-spacing: 1.8px; margin: 25px 0 15px 0; font-weight: 800; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px; }}
    
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    .data-table th {{ text-align: left; padding: 10px 12px; color: var(--text-muted); border-bottom: 1px solid var(--border-subtle); font-weight: 600; text-transform: uppercase; font-size: 0.72rem; letter-spacing: 0.8px; }}
    .data-table td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.02); color: var(--text-primary); }}
    .data-table tr:hover {{ background: var(--bg-elevated); }}

    .setup-row {{ display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0; font-size: 0.88rem; align-items: center; }}
    .setup-row:last-child {{ border-bottom: none; }}
    .setup-label {{ color: var(--text-secondary); }}
    .setup-val {{ font-weight: 700; color: var(--text-primary); }}

    .composite-box {{ background: rgba(255, 92, 92, 0.05); border: 1px solid var(--accent-red); border-radius: 8px; padding: 15px; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center; }}
    .composite-box.bullish {{ background: rgba(57, 211, 83, 0.05); border: 1px solid var(--accent-green); }}

    /* INTELLIGENCE REPORT STYLES */
    .report-banner {{ background: linear-gradient(90deg, rgba(212,175,55,0.15) 0%, rgba(212,175,55,0.02) 100%); border-left: 4px solid var(--gold-primary); padding: 15px 20px; margin-bottom: 20px; border-radius: 0 8px 8px 0; }}
    .report-title {{ font-size: 1.1rem; font-weight: 800; color: var(--gold-primary); letter-spacing: 1px; margin-bottom: 4px; }}
    .report-subtitle {{ font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
    .grid-card {{ background: var(--bg-elevated); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 15px; text-align: center; }}
    .grid-label {{ font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
    .grid-val {{ font-size: 1.4rem; font-weight: 800; }}
    .directive-box {{ background: rgba(255,255,255,0.02); border: 1px dashed var(--border-subtle); padding: 15px; border-radius: 6px; margin-top: 15px; font-size: 0.9rem; line-height: 1.6; }}

    .fade-in {{ animation: fadeIn 0.25s ease forwards; }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
</style>

<div class="terminal-nav">
    <div class="nav-brand">EDGE<span>4X</span></div>
    <div class="nav-status"><span class="live-dot"></span> {api_status_text}</div>
</div>
""", unsafe_allow_html=True)

# --- 5. ZERO-LAG PRE-MARKET MACRO DATA ENGINE ---

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_premarket_macro_data():
    """Fetches macro radar and ADR spreads in a single cached batch."""
    symbols = {
        "DXY": "DX-Y.NYB", "US10Y": "^TNX", "BRENT": "BZ=F", 
        "US_VIX": "^VIX", "INDIA_VIX": "^INDIAVIX",
        "HDB": "HDB", "IBN": "IBN", "INFY": "INFY", "WIT": "WIT", "RDY": "RDY"
    }
    macro_data = {}
    try:
        df = yf.download(list(symbols.values()), period="5d", progress=False)['Close']
        for name, ticker in symbols.items():
            if ticker in df.columns:
                col_data = df[ticker].dropna()
                if len(col_data) >= 2:
                    prev, curr = col_data.iloc[-2], col_data.iloc[-1]
                    chg = ((curr - prev) / prev) * 100
                    macro_data[name] = {"price": curr, "change": chg}
                else: macro_data[name] = {"price": 0.0, "change": 0.0}
            else: macro_data[name] = {"price": 0.0, "change": 0.0}
    except:
        for name in symbols.keys(): macro_data[name] = {"price": 0.0, "change": 0.0}
    return macro_data

@st.cache_data(ttl=15, show_spinner=False)
def get_live_ticker_feed():
    results = {}
    if angel_api:
        try:
            nifty_req = angel_api.ltpData("NSE", "Nifty 50", "26000")
            bank_req = angel_api.ltpData("NSE", "Nifty Bank", "26009")
            if nifty_req.get('status') and bank_req.get('status'):
                results["NIFTY 50"] = {"price": nifty_req['data']['ltp'], "pct_change": 0.0}
                results["BANK NIFTY"] = {"price": bank_req['data']['ltp'], "pct_change": 0.0}
        except: pass

    symbols = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK", "INDIA VIX": "^INDIAVIX"}
    try:
        df = yf.download(list(symbols.values()), period="5d", progress=False)['Close']
        for name, sym in symbols.items():
            if sym in df.columns:
                col_data = df[sym].dropna()
                if len(col_data) >= 2:
                    prev, curr = col_data.iloc[-2], col_data.iloc[-1]
                    pct = ((curr - prev) / prev) * 100
                    if name in results and results[name]["price"] > 0:
                        results[name]["pct_change"] = ((results[name]["price"] - prev) / prev) * 100
                    else:
                        results[name] = {"price": curr, "pct_change": pct}
                else:
                    if name not in results: results[name] = {"price": 0.0, "pct_change": 0.0}
    except:
        for name in symbols.keys():
            if name not in results: results[name] = {"price": 0.0, "pct_change": 0.0}
    return results

@st.fragment(run_every="15s")
def render_live_ticker():
    data = get_live_ticker_feed()
    items_html = ""
    for name, vals in data.items():
        if vals['price'] > 0:
            pct = vals['pct_change']
            color_class, arrow = ("t-up", "▲") if pct > 0 else ("t-dn", "▼") if pct < 0 else ("", "")
            items_html += f'<span class="ticker-item">{name}: {vals["price"]:,.2f} <span class="{color_class}">{arrow} {pct:+.2f}%</span></span>'
    st.markdown(f'<div class="ticker-wrap"><div class="ticker">{items_html * 3}</div></div>', unsafe_allow_html=True)

render_live_ticker()

# --- 6. NAVIGATION STRUCTURE ---
tabs = [
    "🌍 PRE-MARKET & MACRO",
    "LIVE COCKPIT", 
    "INTRADAY INTERNALS", 
    "🧠 AI INTELLIGENCE", 
    "🔬 QUANT & ALPHA METRICS", 
    "RISK ENGINE",
    "🗄️ DATA VAULT & SYNC"
]
selected_tab = st.radio("", tabs, horizontal=True, label_visibility="collapsed")


# --- 7. UNIFIED PRE-MARKET MACRO RADAR MODULE ---

def module_premarket_macro():
    st.markdown("<div class='section-header fade-in' style='margin-top:0;'>PRE-MARKET MACRO RADAR (Global Institutional Flows)</div>", unsafe_allow_html=True)
    
    macro = fetch_premarket_macro_data()
    
    # Quantitative Risk Factor Calculation
    dxy_chg = macro.get("DXY", {}).get("change", 0)
    yield_chg = macro.get("US10Y", {}).get("change", 0)
    brent_chg = macro.get("BRENT", {}).get("change", 0)
    us_vix_chg = macro.get("US_VIX", {}).get("change", 0)
    ind_vix_chg = macro.get("INDIA_VIX", {}).get("change", 0)
    
    risk_score = 50 + (dxy_chg * 20) + (yield_chg * 15) + (brent_chg * 10) + (us_vix_chg * 0.5)
    risk_score = max(5.0, min(95.0, risk_score))
    
    if risk_score > 60: risk_text, risk_theme_color = "HIGH RISK (GLOBAL CAPITAL DRAIN)", "#FF5C5C"
    elif risk_score < 40: risk_text, risk_theme_color = "LOW RISK (FAVORABLE INFLOWS)", "#39D353"
    else: risk_text, risk_theme_color = "MODERATE / NEUTRAL BIAS", "#D4AF37"

    # ADR Point Drag Computation
    hdb_chg = macro.get("HDB", {}).get("change", 0)
    ibn_chg = macro.get("IBN", {}).get("change", 0)
    infy_chg = macro.get("INFY", {}).get("change", 0)
    nifty_drag_est = ((hdb_chg * 0.11) + (ibn_chg * 0.08) + (infy_chg * 0.06)) * 240

    c1, c2, c3 = st.columns([1.2, 1.2, 1.2])
    
    with c1:
        st.markdown("""
        <div class="panel-box fade-in" style="height: 100%;">
            <div class="panel-header">GLOBAL RISK SPEEDOMETER</div>
        """, unsafe_allow_html=True)
        
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number", value=risk_score, domain={'x': [0, 1], 'y': [0, 1]},
            number={'suffix': "/100", 'font': {'size': 22, 'color': risk_theme_color, 'family': 'Inter'}},
            gauge={'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#A7AFBA"},
                   'bar': {'color': risk_theme_color, 'thickness': 0.28},
                   'bgcolor': "rgba(0,0,0,0)", 'borderwidth': 0,
                   'steps': [{'range': [0, 40], 'color': "rgba(57, 211, 83, 0.15)"}, {'range': [40, 60], 'color': "rgba(212, 175, 55, 0.15)"}, {'range': [60, 100], 'color': "rgba(255, 92, 92, 0.15)"}],
                   'threshold': {'line': {'color': risk_theme_color, 'width': 3}, 'thickness': 0.75, 'value': risk_score}}
        ))
        gauge_fig.update_layout(height=140, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#A7AFBA", family="Inter"))
        st.plotly_chart(gauge_fig, use_container_width=True, config={'displayModeBar': False})
        
        st.markdown(f"""
            <div style="font-size: 0.95rem; font-weight: 700; color: {risk_theme_color}; margin-top: -5px; text-align: center;">{risk_text}</div>
            <div style="margin-top: 15px; border-top: 1px solid var(--border-subtle); padding-top: 10px;">
                <div class="setup-row"><span class="setup-label">Brent Crude Oil</span><span class="setup-val">${macro.get('BRENT', {}).get('price', 0):.2f}</span></div>
                <div class="setup-row"><span class="setup-label">US 10-Year Yield</span><span class="setup-val">{macro.get('US10Y', {}).get('price', 0):.2f}%</span></div>
                <div class="setup-row"><span class="setup-label">US Dollar (DXY)</span><span class="setup-val">{macro.get('DXY', {}).get('price', 0):.2f}</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        def format_adr(val): return f"<span style='color:var(--accent-green); font-weight:700;'>+{val:.2f}%</span>" if val > 0 else (f"<span style='color:var(--accent-red); font-weight:700;'>{val:.2f}%</span>" if val < 0 else "<span style='color:var(--text-muted);'>0.00%</span>")
        
        drag_color = "var(--accent-green)" if nifty_drag_est > 0 else "var(--accent-red)"
        drag_text = f"+{nifty_drag_est:.1f} Pts Drag" if nifty_drag_est > 0 else f"{nifty_drag_est:.1f} Pts Drag"
        
        st.markdown(f"""
        <div class="panel-box fade-in" style="height: 100%;">
            <div class="panel-header" style="display:flex; justify-content:space-between;">
                <span>OVERNIGHT US ADR TRACKER</span>
                <span style="color:{drag_color}; font-size:0.75rem;">{drag_text}</span>
            </div>
            <table class="data-table">
                <tr><th>Constituent</th><th>US Ticker</th><th>Overnight Change</th></tr>
                <tr><td><b>HDFC Bank</b></td><td>HDB</td><td>{format_adr(hdb_chg)}</td></tr>
                <tr><td><b>ICICI Bank</b></td><td>IBN</td><td>{format_adr(ibn_chg)}</td></tr>
                <tr><td><b>Infosys</b></td><td>INFY</td><td>{format_adr(infy_chg)}</td></tr>
                <tr><td><b>Wipro</b></td><td>WIT</td><td>{format_adr(macro.get("WIT", {}).get("change", 0))}</td></tr>
                <tr><td><b>Dr. Reddy's</b></td><td>RDY</td><td>{format_adr(macro.get("RDY", {}).get("change", 0))}</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        if us_vix_chg > 5 and ind_vix_chg < 2:
            vix_color = "var(--accent-red)"
            vix_alert = "🔴 CONTAGION LAG (VIX DIVERGENCE)"
            vix_desc = "US VIX spiking but India VIX lagging. Smart money will buy cheap put options at the open. Expect downside."
        else:
            vix_color = "var(--gold-primary)"
            vix_alert = "🟡 NORMAL VOLATILITY PRICING"
            vix_desc = "No extreme divergence between US and Indian volatility. Options pricing is balanced."

        st.markdown(f"""
        <div class="panel-box fade-in" style="height: 100%;">
            <div class="panel-header">VOLATILITY CONTAGION ALERT</div>
            <div style="font-size: 1.1rem; font-weight: 800; color: {vix_color}; margin-top: 5px; margin-bottom: 8px;">{vix_alert}</div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 15px;">{vix_desc}</div>
            <div class="setup-row"><span class="setup-label">Wall Street Fear Gauge (US VIX)</span><span class="setup-val" style="color:{'var(--accent-red)' if us_vix_chg > 0 else 'var(--accent-green)'};">{us_vix_chg:+.2f}%</span></div>
            <div class="setup-row"><span class="setup-label">Domestic Fear Gauge (INDIA VIX)</span><span class="setup-val">{ind_vix_chg:+.2f}%</span></div>
        </div>
        """, unsafe_allow_html=True)


# --- 8. BASE UI MODULES ---

def module_live_cockpit():
    st.markdown("<div class='section-header fade-in'>LIVE INTRADAY COCKPIT</div>", unsafe_allow_html=True)
    st.markdown("""
        <div class="panel-box fade-in">
            <div style="text-align:center; padding: 40px; color: var(--text-muted);">
                <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 10px;">Awaiting Next Intraday Module</div>
                <div>Live execution tools (VWAP Pulls, Gamma Walls) will be mapped here next.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def module_intraday_internals():
    st.markdown("<h2 class='fade-in' style='font-weight: 700; margin-bottom: 20px;'>LIVE INTRADAY INTERNALS</h2>", unsafe_allow_html=True)
    st.markdown("""
        <div class="panel-box fade-in">
            <div style="text-align:center; padding: 40px; color: var(--text-muted);">
                <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 10px;">Awaiting Internals Pipeline</div>
                <div>Advance/Decline breadth and Sectoral Relative Strength will be integrated here.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def module_quant_alpha_metrics():
    st.markdown("<h2 class='fade-in' style='font-weight: 800; color: var(--text-primary); margin-bottom: 20px; letter-spacing: 1px;'>🔬 QUANTITATIVE & ALPHA METRICS</h2>", unsafe_allow_html=True)
    st.markdown("""
        <div class="panel-box fade-in">
            <div style="text-align:center; padding: 40px; color: var(--text-muted);">
                <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 10px;">Awaiting Option Data Engine</div>
                <div>Dealer Net Gamma Exposure (GEX) and 25-Delta Skew Surfaces will be added here.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def module_risk_calculator():
    st.markdown("<h2 class='fade-in' style='font-weight: 700; margin-bottom: 15px;'>🛡️ PRECISION RISK & POSITION SIZING ENGINE</h2>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.markdown("<div class='panel-box fade-in'><div class='panel-header'>TRADE PARAMETERS</div>", unsafe_allow_html=True)
        capital = st.number_input("Account Capital (₹)", value=500000, step=25000)
        risk_pct = st.slider("Risk Tolerance (% of Capital)", min_value=0.5, max_value=3.0, value=1.0, step=0.25)
        instrument = st.selectbox("Instrument", ["NIFTY 50 (Lot: 25)", "BANK NIFTY (Lot: 15)"])
        lot_size = 25 if "NIFTY 50" in instrument else 15
        entry_price = st.number_input("Option Entry Premium (₹)", value=120.0, step=5.0)
        sl_price = st.number_input("Option Stop Loss (₹)", value=95.0, step=5.0)
        target_price = st.number_input("Option Target (₹)", value=180.0, step=5.0)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        max_rupee_loss = (capital * risk_pct) / 100.0
        risk_per_unit = max(1.0, entry_price - sl_price)
        reward_per_unit = max(1.0, target_price - entry_price)
        rr_ratio = reward_per_unit / risk_per_unit
        
        total_units = int(max_rupee_loss // risk_per_unit)
        total_lots = max(1, total_units // lot_size)
        actual_quantity = total_lots * lot_size
        actual_rupee_loss = actual_quantity * risk_per_unit
        expected_profit = actual_quantity * reward_per_unit
        
        st.markdown("<div class='panel-box fade-in'><div class='panel-header'>INSTITUTIONAL ALLOCATION MATRIX</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="setup-row"><span class="setup-label">Max Allowed Risk (₹)</span><span class="setup-val">₹{max_rupee_loss:,.2f} ({risk_pct}%)</span></div>
        <div class="setup-row"><span class="setup-label">Recommended Lot Size</span><span class="setup-val" style="color:var(--gold-primary); font-size:1.2rem;">{total_lots} Lots ({actual_quantity} Qty)</span></div>
        <div class="setup-row"><span class="setup-label">Total Capital Required</span><span class="setup-val">₹{actual_quantity * entry_price:,.2f}</span></div>
        <div class="setup-row"><span class="setup-label">Loss at Invalidation (SL)</span><span class="setup-val" style="color:var(--accent-red);">-₹{actual_rupee_loss:,.2f}</span></div>
        <div class="setup-row"><span class="setup-label">Target Profit (Reward)</span><span class="setup-val" style="color:var(--accent-green);">+₹{expected_profit:,.2f}</span></div>
        <div class="setup-row"><span class="setup-label">Risk-to-Reward Ratio</span><span class="setup-val">1 : {rr_ratio:.2f}</span></div>
        </div>
        """, unsafe_allow_html=True)

# --- DATA VAULT PARSERS & UI ---
def parse_participant_csv_full(file):
    try:
        content = file.getvalue().decode("utf-8", errors="ignore").strip().split('\n')
        if len(content) > 0 and ("Participant" in content[0] or "Date" in content[0] or "participant" in content[0].lower()):
            content = content[1:]
        df = pd.read_csv(io.StringIO('\n'.join(content)))
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        fil_col = next((c for c in df.columns if 'future index long' in c), None)
        fis_col = next((c for c in df.columns if 'future index short' in c), None)
        ocl_col = next((c for c in df.columns if 'call long' in c and 'index' in c), None)
        ocs_col = next((c for c in df.columns if 'call short' in c and 'index' in c), None)
        opl_col = next((c for c in df.columns if 'put long' in c and 'index' in c), None)
        ops_col = next((c for c in df.columns if 'put short' in c and 'index' in c), None)
        
        matrix = {}
        for client_type in ['Client', 'FII', 'Pro']:
            row = df[df[df.columns[0]].astype(str).str.contains(client_type, case=False, na=False)]
            if not row.empty and fil_col and fis_col:
                matrix[client_type] = {
                    "Futures": float(row.iloc[0][fil_col]) - float(row.iloc[0][fis_col]),
                    "Calls": float(row.iloc[0][ocl_col]) - float(row.iloc[0][ocs_col]) if ocl_col and ocs_col else 0,
                    "Puts": float(row.iloc[0][opl_col]) - float(row.iloc[0][ops_col]) if opl_col and ops_col else 0
                }
        return matrix
    except Exception: return None

def parse_delivery_file(file):
    try:
        content = file.getvalue().decode("utf-8", errors="ignore").strip().split('\n')
        if len(content) > 0 and not content[0].startswith('10'): pass
        df = pd.read_csv(io.StringIO('\n'.join(content)))
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        sym_col = next((c for c in df.columns if 'SYMBOL' in c or 'SECURITY' in c), None)
        del_col = next((c for c in df.columns if 'DELIV' in c and '%' in c or 'DELI QTY TO TRADED' in c), None)
        
        res = {}
        if sym_col and del_col:
            targets = ["HDFCBANK", "ICICIBANK", "RELIANCE", "INFY", "KOTAKBANK"]
            for t in targets:
                row = df[df[sym_col].astype(str).str.contains(t, case=False, na=False)]
                if not row.empty:
                    val = str(row.iloc[0][del_col]).replace('%', '').strip()
                    res[t] = float(val) if val.replace('.','',1).isdigit() else 0.0
        return res
    except Exception: return {}

def generate_institutional_report():
    st.markdown("<div class='section-header fade-in' style='margin-top: 40px;'>INSTITUTIONAL MARKET INTELLIGENCE REPORT</div>", unsafe_allow_html=True)
    
    curr = st.session_state.participant_matrix_curr
    prev = st.session_state.participant_matrix_prev
    del_stats = st.session_state.delivery_stats
    
    fii_fut_shift = curr['FII']['Futures'] - prev['FII']['Futures'] if prev else 0
    ret_net_puts = curr['Client']['Puts']
    
    pro_puts = curr['Pro']['Puts']
    pro_calls = curr['Pro']['Calls']
    fii_calls = curr['FII']['Calls']
    fii_puts = curr['FII']['Puts']
    
    rvi = abs(ret_net_puts) / (abs(curr['FII']['Futures']) * 15.0) if curr['FII']['Futures'] != 0 else 0
    ihpr = pro_puts / pro_calls if pro_calls != 0 else 1.0
    cbci = (del_stats.get('HDFCBANK', 0) * 0.11) + (del_stats.get('RELIANCE', 0) * 0.09) + (del_stats.get('ICICIBANK', 0) * 0.08)
    
    if curr['FII']['Futures'] < -50000 and ret_net_puts < -50000 and ihpr > 1.5:
        verdict_title = "DIVERGENCE WARNING: FIIs BUY PUTS, RETAIL TRAPPED AS PUT WRITERS"
        verdict_color = "var(--accent-red)"
        bias_score = -2.0 - (rvi * 0.1)
        plan_desc = "Retail traders are dangerously exposed as the primary Put Writers, subsidizing institutional downside hedges. Smart Money is bracing for a derivatives flush to wipe out retail put-writers while safely locking away core banking assets in the cash market."
        st.session_state.market_regime = "BEARISH FLUSH BIAS"
    elif curr['FII']['Futures'] > 50000 and ret_net_puts > 50000 and pro_calls > pro_puts:
        verdict_title = "ACCUMULATION TRIGGER: RETAIL SHORT CALLS, SMART MONEY ACCUMULATES"
        verdict_color = "var(--accent-green)"
        bias_score = +5.0 + (rvi * 0.1)
        plan_desc = "Retail is aggressively fading the rally by shorting calls, providing liquidity for institutional accumulation. Expect a sustained squeeze higher as market makers force retail shorts to cover."
        st.session_state.market_regime = "BULLISH ACCUMULATION"
    else:
        verdict_title = "NEUTRAL CHOP ZONE: MIXED INSTITUTIONAL FLOWS"
        verdict_color = "var(--gold-primary)"
        bias_score = 0.0
        plan_desc = "No extreme divergences detected. Market is positioned for intraday mean-reversion. Focus on selling OTM strangles and fading the edges."
        st.session_state.market_regime = "NEUTRAL RANGE-BOUND"
        
    st.session_state.smart_money_score = bias_score
    bias_text = st.session_state.market_regime
    
    st.markdown(f"""
    <div class="report-banner fade-in">
        <div class="report-title" style="color: {verdict_color};">{verdict_title}</div>
        <div class="report-subtitle">Trade Desk Synthesis & Hidden Formula Output</div>
        <div style="font-size: 0.9rem; color: var(--text-primary); margin-top: 10px; line-height: 1.6;">{plan_desc}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-grid fade-in">
        <div class="grid-card">
            <div class="grid-label">FII Futures Flow (DoD)</div>
            <div class="grid-val" style="color: {'var(--accent-red)' if fii_fut_shift < 0 else 'var(--accent-green)'};">{fii_fut_shift:+,.0f}</div>
        </div>
        <div class="grid-card">
            <div class="grid-label">Retail Net Put Exposure</div>
            <div class="grid-val" style="color: {'var(--accent-red)' if ret_net_puts < 0 else 'var(--accent-green)'};">{ret_net_puts:+,.0f}</div>
        </div>
        <div class="grid-card">
            <div class="grid-label">Cash-Buffer Cushion (CBCI)</div>
            <div class="grid-val" style="color: var(--gold-primary);">{cbci:.1f} Pts</div>
        </div>
        <div class="grid-card" style="border-color: {verdict_color}; background: rgba(0,0,0,0.2);">
            <div class="grid-label">NET SMART MONEY SCORE</div>
            <div class="grid-val" style="color: {verdict_color};">{bias_score:+.1f} / 10</div>
            <div style="font-size: 0.75rem; color: {verdict_color}; font-weight: 600; margin-top: 4px;">{bias_text}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1.2, 1])
    
    with c1:
        st.markdown("""<div class="panel-box fade-in" style="height: 100%;">
        <div class="panel-header">FII OPTIONS INTENT & BATTLEGROUND DECODER</div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="setup-row"><span class="setup-label">Pro Desk Net Puts (Downside Bets)</span><span class="setup-val" style="color:var(--accent-red);">{pro_puts:+,.0f}</span></div>
        <div class="setup-row"><span class="setup-label">Pro Desk Net Calls (Upside Bets)</span><span class="setup-val" style="color:var(--accent-green);">{pro_calls:+,.0f}</span></div>
        <div class="setup-row"><span class="setup-label">FII Net Puts</span><span class="setup-val">{fii_puts:+,.0f}</span></div>
        <div class="setup-row"><span class="setup-label">FII Net Calls</span><span class="setup-val">{fii_calls:+,.0f}</span></div>
        <div class="setup-row" style="border-top: 1px solid var(--border-subtle); margin-top: 10px; padding-top: 15px;">
            <span class="setup-label">Institutional Hedging Pressure (IHPR)</span>
            <span class="setup-val" style="color:var(--gold-primary); font-size:1.1rem;">{ihpr:.2f}x Ratio</span>
        </div>
        <div class="directive-box">
            <b>TRUE INSTITUTIONAL INTENT:</b> {'Aggressive Downside Hedging detected. Market makers are loaded on puts.' if ihpr > 1.2 else 'Upside Accumulation detected. Market makers are heavily favoring calls.' if ihpr < 0.8 else 'Balanced Hedging. Market makers are delta-neutral.'} The Retail Vulnerability Index (RVI) sits at <b>{rvi:.2f}</b>, marking retail traders as the primary liquidity targets.
        </div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown("""<div class="panel-box fade-in" style="height: 100%;">
        <div class="panel-header">INSTITUTIONAL STRIKE PRECISION MAP</div>
        <div style="text-align:center; padding: 40px 0; color: var(--text-muted);">
            Awaiting Live Option Chain Sync.<br>This will be integrated safely in the next phase.
        </div>
        </div>""", unsafe_allow_html=True)

def module_data_vault():
    st.markdown("<h2 class='fade-in' style='font-weight: 800; margin-bottom: 15px; letter-spacing: 1px; font-size: 1.4rem;'>🗄️ INSTITUTIONAL DATA VAULT & REPORT GENERATOR</h2>", unsafe_allow_html=True)
    
    db_status, db_color, record_count = "OFFLINE", "var(--accent-red)", 0
    if DuckDBManager:
        try:
            db = DuckDBManager()
            df_records = db.fetch_training_dataset()
            record_count = len(df_records)
            db_status, db_color = "SECURE & SYNCHRONIZED", "var(--accent-green)"
        except Exception: pass

    st.markdown(f"""
    <div class="panel-box fade-in" style="padding: 12px 20px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid {db_color};">
        <div>
            <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Local Edge Database</div>
            <div style="font-size: 0.95rem; font-weight: 800; color:{db_color};">{db_status}</div>
        </div>
        <div style="border-left: 1px solid var(--border-subtle); padding-left: 20px;">
            <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Settled EOD Sessions</div>
            <div style="font-size: 0.95rem; font-weight: 800; color:var(--gold-primary);">{record_count} Records</div>
        </div>
        <div style="border-left: 1px solid var(--border-subtle); padding-left: 20px;">
            <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">AI Intelligence Status</div>
            <div style="font-size: 0.95rem; font-weight: 800; color:var(--text-secondary);">{"Online (Ready for Inference)" if record_count >= 20 else "Awaiting 20 Sessions"}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    is_open = st.session_state.participant_matrix_curr is None
    with st.expander("⚙️ BATCH DATA OVERRIDE & REPORT GENERATION", expanded=is_open):
        st.markdown("<div style='color:var(--text-secondary); margin-bottom:15px; font-size:0.85rem;'><b>SMART BATCH UPLOAD:</b> Drop all T-1 files into Box 1. Drop all T files into Box 2. The system automatically identifies Participant OI and Delivery files.</div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='compact-upload-title' style='font-size:0.75rem; color:var(--gold-primary); font-weight:bold;'>PREVIOUS DAY (T-1) BATCH</div>", unsafe_allow_html=True)
            batch_t1 = st.file_uploader("Drop all T-1 files here", accept_multiple_files=True, key="batch_t1", label_visibility="collapsed")
        with c2:
            st.markdown("<div class='compact-upload-title' style='font-size:0.75rem; color:var(--gold-primary); font-weight:bold;'>CURRENT DAY (T) BATCH</div>", unsafe_allow_html=True)
            batch_t = st.file_uploader("Drop all T files here", accept_multiple_files=True, key="batch_t", label_visibility="collapsed")

        if st.button("EXECUTE REPORT GENERATION ENGINE", type="primary", use_container_width=True):
            if batch_t1 and batch_t:
                with st.spinner("Auto-detecting file types and compiling institutional positioning..."):
                    time.sleep(0.5)
                    
                    def sniff_and_extract(file_list):
                        matrix, deliv = None, {}
                        for f in file_list:
                            try:
                                content = f.getvalue().decode("utf-8", errors="ignore").strip().split('\n')
                                if not content: continue
                                header = (content[0] + (content[1] if len(content)>1 else "")).lower()
                                
                                if 'future index long' in header and 'future index short' in header:
                                    matrix = parse_participant_csv_full(f)
                                elif 'deliv' in header or 'deli qty' in header:
                                    deliv = parse_delivery_file(f)
                            except: pass
                        return matrix, deliv

                    prev_matrix, _ = sniff_and_extract(batch_t1)
                    curr_matrix, del_stats = sniff_and_extract(batch_t)
                    
                    if curr_matrix and "FII" in curr_matrix and prev_matrix:
                        st.session_state.participant_matrix_curr = curr_matrix
                        st.session_state.participant_matrix_prev = prev_matrix
                        st.session_state.delivery_stats = del_stats
                        
                        st.session_state.fii_net_futures = curr_matrix['FII']['Futures']
                        st.session_state.fii_dod_delta = curr_matrix['FII']['Futures'] - prev_matrix['FII']['Futures']
                        
                        st.session_state.eod_data_processed = True
                        st.success("✅ Smart Batch Sync Complete. Auto-routing data to report engines.")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Error: Could not detect valid Participant OI files in your batch. Ensure they are downloaded from NSE.")
            else:
                st.warning("Please upload files into both T-1 and T boxes to generate the report.")

    if st.session_state.participant_matrix_curr:
        generate_institutional_report()

# --- 9. EXECUTION ROUTER ---
if selected_tab == "🌍 PRE-MARKET & MACRO":
    module_premarket_macro()
elif selected_tab == "LIVE COCKPIT":
    module_live_cockpit()
elif selected_tab == "INTRADAY INTERNALS":
    module_intraday_internals()
elif selected_tab == "🧠 AI INTELLIGENCE":
    if render_ai_intelligence_tab: render_ai_intelligence_tab()
    else: st.error("AI Engine module (`edge4x_intel_engine.py`) not found or missing dependencies.")
elif selected_tab == "🔬 QUANT & ALPHA METRICS":
    module_quant_alpha_metrics()
elif selected_tab == "RISK ENGINE":
    module_risk_calculator()
elif selected_tab == "🗄️ DATA VAULT & SYNC":
    module_data_vault()