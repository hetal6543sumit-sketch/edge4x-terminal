import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
import math
import requests
import io
from datetime import datetime
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

    /* EXPANDER FIX FOR WHITE BACKGROUND */
    div[data-testid="stExpander"] {{
        background-color: var(--bg-elevated) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 8px !important;
    }}
    div[data-testid="stExpander"] details summary {{
        color: var(--gold-primary) !important;
    }}
    div[data-testid="stExpander"] details summary p {{
        color: var(--gold-primary) !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        letter-spacing: 1px !important;
    }}
    div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {{
        color: var(--text-primary) !important;
    }}

    /* UI PANELS & METRIC CARDS */
    .metric-strip {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
    .metric-card {{ flex: 1 1 180px; background: var(--bg-surface); padding: 15px 18px; border-radius: 8px; border: 1px solid var(--border-subtle); position: relative; }}
    .metric-label {{ font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; display: flex; align-items: center; }}
    .metric-value {{ font-size: 1.35rem; font-weight: 700; color: var(--text-primary); }}

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


# --- 5. FAST VECTORIZED REAL DATA ENGINES ---

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def fetch_nse_json(api_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate, br"
    }
    for _ in range(2):
        try:
            session = requests.Session()
            session.headers.update(headers)
            session.get("https://www.nseindia.com", timeout=2.5) 
            time.sleep(0.3)
            session.headers.update({"Referer": "https://www.nseindia.com/"})
            res = session.get(api_url, timeout=3.0)
            if res.status_code == 200: return res.json()
            if res.status_code in [401, 403]:
                session.get("https://www.nseindia.com/option-chain", timeout=2.5)
                time.sleep(0.3)
                res = session.get(api_url, timeout=3.0)
                if res.status_code == 200: return res.json()
        except: pass
        time.sleep(0.5)
    return None

def get_yfinance_breadth_fallback():
    nifty_50_symbols = [
        "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LTIM.NS", "LT.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "UPL.NS", "ULTRACEMCO.NS", "WIPRO.NS"
    ]
    try:
        data = yf.download(nifty_50_symbols, period="2d", progress=False)['Close']
        if len(data) >= 2:
            changes = data.iloc[-1] - data.iloc[-2]
            return {"advances": int((changes > 0).sum()), "declines": int((changes < 0).sum()), "unchanged": int((changes == 0).sum())}
    except: pass
    return None

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

@st.cache_data(ttl=30, show_spinner=False)
def get_real_option_chain_data():
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    data = fetch_nse_json(url)
    if data is None: return None
        
    try:
        records = data.get('records', {})
        spot_price = float(records.get('underlyingValue', 0))
        expiry_dates = records.get('expiryDates', [])
        if not expiry_dates or spot_price == 0: return None
            
        current_expiry = expiry_dates[0]
        exp_date_obj = datetime.strptime(current_expiry, '%d-%b-%Y')
        days_to_expiry = max(1, (exp_date_obj - datetime.now()).days)
        time_to_exp = days_to_expiry / 365.0
        
        chain_data = records.get('data', [])
        filtered_chain = [d for d in chain_data if d.get('expiryDate') == current_expiry]
        atm_strike = int(round(spot_price / 50.0) * 50)
        
        parsed_strikes = []
        atm_data = {"CE_LTP": 0.0, "PE_LTP": 0.0, "CE_IV": 15.0, "PE_IV": 15.0}
        total_gex = 0.0
        
        for item in filtered_chain:
            strike = item.get('strikePrice')
            ce = item.get('CE', {})
            pe = item.get('PE', {})
            
            ce_oi = ce.get('openInterest', 0) * 25
            pe_oi = pe.get('openInterest', 0) * 25
            ce_iv = ce.get('impliedVolatility', 0.0) or 15.0
            pe_iv = pe.get('impliedVolatility', 0.0) or 15.0
            
            if strike == atm_strike:
                atm_data["CE_LTP"] = float(ce.get('lastPrice', 0.0))
                atm_data["PE_LTP"] = float(pe.get('lastPrice', 0.0))
                atm_data["CE_IV"] = ce_iv
                atm_data["PE_IV"] = pe_iv
                
            try:
                sigma = (ce_iv / 100.0)
                d1 = (math.log(spot_price / strike) + (0.07 + 0.5 * sigma ** 2) * time_to_exp) / (sigma * math.sqrt(time_to_exp))
                gamma = norm_pdf(d1) / (spot_price * sigma * math.sqrt(time_to_exp))
            except Exception:
                gamma = 0.0
                
            net_strike_gex = ((ce_oi - pe_oi) * gamma * (spot_price ** 2) * 0.01) / 1e7
            total_gex += net_strike_gex
            
            parsed_strikes.append({
                "Strike": strike, "CE_OI": ce_oi, "PE_OI": pe_oi,
                "CE_IV": ce_iv, "PE_IV": pe_iv, "GEX": net_strike_gex
            })
            
        df_strikes = pd.DataFrame(parsed_strikes).sort_values("Strike").reset_index(drop=True)
        
        df_strikes['cum_gex'] = df_strikes['GEX'].cumsum()
        flip_row = df_strikes[df_strikes['cum_gex'] >= 0]
        gamma_flip = float(flip_row.iloc[0]['Strike']) if not flip_row.empty else float(atm_strike)
        
        call_25d_strike = int(round((spot_price * 1.015) / 50.0) * 50)
        put_25d_strike = int(round((spot_price * 0.985) / 50.0) * 50)
        
        call_iv_row = df_strikes[df_strikes['Strike'] == call_25d_strike]
        put_iv_row = df_strikes[df_strikes['Strike'] == put_25d_strike]
        
        iv_25d_call = float(call_iv_row['CE_IV'].iloc[0]) if not call_iv_row.empty else atm_data['CE_IV']
        iv_25d_put = float(put_iv_row['PE_IV'].iloc[0]) if not put_iv_row.empty else atm_data['PE_IV']
        skew_25d = iv_25d_put - iv_25d_call
        
        synthetic_fut = atm_strike + atm_data["CE_LTP"] - atm_data["PE_LTP"]
        basis = synthetic_fut - spot_price
        coc_annual = (basis / spot_price) * (365.0 / days_to_expiry) * 100.0 if days_to_expiry > 0 else 0.0
        
        return {
            "spot": spot_price, "atm_strike": atm_strike, "atm_data": atm_data,
            "total_gex": total_gex, "gamma_flip": gamma_flip,
            "skew_25d": skew_25d, "iv_25d_put": iv_25d_put, "iv_25d_call": iv_25d_call,
            "basis": basis, "coc_annual": coc_annual, "days_to_expiry": days_to_expiry,
            "strikes": df_strikes
        }
    except Exception:
        return None

@st.cache_data(ttl=60, show_spinner=False)
def get_real_delivery_zscores():
    heavyweights = {
        "HDFCBANK.NS": "HDFC Bank", "RELIANCE.NS": "Reliance Ind.",
        "ICICIBANK.NS": "ICICI Bank", "INFY.NS": "Infosys", "TCS.NS": "TCS"
    }
    z_scores = []
    try:
        data = yf.download(list(heavyweights.keys()), period="1mo", progress=False)['Volume']
        for sym, name in heavyweights.items():
            if sym in data.columns:
                vols = data[sym].dropna()
                if len(vols) >= 15:
                    mean_20d = vols.iloc[-21:-1].mean() if len(vols) >= 21 else vols.mean()
                    std_20d = vols.iloc[-21:-1].std() if len(vols) >= 21 else vols.std()
                    today_vol = vols.iloc[-1]
                    z = (today_vol - mean_20d) / std_20d if std_20d > 0 else 0.0
                    state = "INSTITUTIONAL ACCUMULATION" if z > 1.5 else ("DISTRIBUTION SURGE" if z < -1.5 else "NORMAL FLOW")
                    z_scores.append({"Stock": name, "Volume": today_vol, "Mean_20D": mean_20d, "Z_Score": z, "State": state})
    except Exception: pass
    return pd.DataFrame(z_scores) if z_scores else None

@st.cache_data(ttl=30, show_spinner=False)
def get_real_market_breadth():
    url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050"
    data = fetch_nse_json(url)
    if data is not None:
        adv = data.get('advance', {})
        if adv.get('advances', 0) > 0 or adv.get('declines', 0) > 0:
            return {"advances": adv.get('advances', 0), "declines": adv.get('declines', 0), "unchanged": adv.get('unchanged', 0)}
    return get_yfinance_breadth_fallback()

@st.cache_data(ttl=30, show_spinner=False)
def get_real_sectoral_data():
    sectors = {
        "NIFTY 50 (Benchmark)": "^NSEI", "NIFTY BANK": "^NSEBANK", "NIFTY FIN SERVICE": "^CNXFIN", "NIFTY IT": "^CNXIT",
        "NIFTY AUTO": "^CNXAUTO", "NIFTY ENERGY": "^CNXENERGY", "NIFTY FMCG": "^CNXFMCG", "NIFTY PHARMA": "^CNXPHARMA",
        "NIFTY METAL": "^CNXMETAL", "NIFTY REALTY": "^CNXREALTY", "NIFTY MEDIA": "^CNXMEDIA", "NIFTY INFRA": "^CNXINFRA",
        "NIFTY PSU BANK": "^CNXPSUBANK", "NIFTY CONSUMPTION": "^CNXCONSUM"
    }
    sym_to_name = {v: k for k, v in sectors.items()}
    results = []
    try:
        df = yf.download(list(sectors.values()), period="5d", progress=False)['Close']
        for sym in sectors.values():
            if sym in df.columns:
                col_data = df[sym].dropna()
                if len(col_data) >= 2:
                    prev, curr = col_data.iloc[-2], col_data.iloc[-1]
                    pct = ((curr - prev) / prev) * 100
                    state = "STRONG LONG" if pct > 0.5 else "WEAK LONG" if pct > 0 else "WEAK SHORT" if pct > -0.5 else "STRONG SHORT"
                    results.append({"Sector": sym_to_name[sym], "Price": curr, "Change": pct, "State": state})
    except: pass
    return pd.DataFrame(results) if results else None

@st.cache_data(ttl=30, show_spinner=False)
def get_real_heavyweight_vwap():
    heavyweights = {
        "HDFCBANK.NS": {"name": "HDFC Bank", "weight": 11.03},
        "RELIANCE.NS": {"name": "Reliance Ind.", "weight": 9.23},
        "ICICIBANK.NS": {"name": "ICICI Bank", "weight": 7.75},
        "INFY.NS": {"name": "Infosys", "weight": 6.12},
        "TCS.NS": {"name": "TCS", "weight": 4.03}
    }
    data, composite_score = [], 0.0
    try:
        df = yf.download(list(heavyweights.keys()), period="1d", interval="1m", progress=False)
        for sym, meta in heavyweights.items():
            if 'Close' in df.columns and sym in df['Close'].columns:
                c, h, l, v = df['Close'][sym].dropna(), df['High'][sym].dropna(), df['Low'][sym].dropna(), df['Volume'][sym].dropna()
                if not c.empty:
                    curr_price = c.iloc[-1]
                    vwap = ((h + l + c) / 3 * v).sum() / v.sum() if v.sum() > 0 else curr_price
                    div = ((curr_price - vwap) / vwap) * 100
                    composite_score += (div * (meta['weight'] / 100))
                    state = "ALGO BUYING" if div > 0 else "ALGO SELLING"
                    data.append({"Symbol": meta["name"], "Weight": f"{meta['weight']}%", "Price": curr_price, "VWAP": vwap, "Divergence": div, "State": state})
                else: data.append({"Symbol": meta["name"], "Weight": f"{meta['weight']}%", "Price": 0.0, "VWAP": 0.0, "Divergence": 0.0, "State": "AWAITING MARKET OPEN"})
            else: data.append({"Symbol": meta["name"], "Weight": f"{meta['weight']}%", "Price": 0.0, "VWAP": 0.0, "Divergence": 0.0, "State": "DATA UNAVAILABLE"})
    except Exception:
        for sym, meta in heavyweights.items(): data.append({"Symbol": meta["name"], "Weight": f"{meta['weight']}%", "Price": 0.0, "VWAP": 0.0, "Divergence": 0.0, "State": "DATA UNAVAILABLE"})
    return pd.DataFrame(data), composite_score

@st.cache_data(ttl=300, show_spinner=False)
def get_premarket_macro_data():
    symbols = {"DXY": "DX-Y.NYB", "US10Y": "^TNX", "BRENT": "BZ=F", "HDFC_ADR": "HDB", "ICICI_ADR": "IBN", "INFY_ADR": "INFY", "WIPRO_ADR": "WIT", "DRREDDY_ADR": "RDY"}
    sym_to_name = {v: k for k, v in symbols.items()}
    macro_data = {}
    try:
        df = yf.download(list(symbols.values()), period="5d", progress=False)['Close']
        for sym in symbols.values():
            name = sym_to_name[sym]
            if sym in df.columns:
                col_data = df[sym].dropna()
                if len(col_data) >= 2:
                    prev, curr = col_data.iloc[-2], col_data.iloc[-1]
                    macro_data[name] = {"price": curr, "change": ((curr - prev) / prev) * 100}
                else: macro_data[name] = {"price": 0.0, "change": 0.0}
            else: macro_data[name] = {"price": 0.0, "change": 0.0}
    except:
        for name in symbols.keys(): macro_data[name] = {"price": 0.0, "change": 0.0}
    return macro_data

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

@st.cache_data(ttl=60, show_spinner=False)
def get_strike_precision_map():
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    data = fetch_nse_json(url)
    if data is None: return 0, 0, 0, 0
    
    try:
        records = data.get('records', {})
        spot_price = float(records.get('underlyingValue', 0))
        expiry_dates = records.get('expiryDates', [])
        if not expiry_dates or spot_price == 0: return 0, 0, 0, 0
        
        chain_data = records.get('data', [])
        filtered = [d for d in chain_data if d.get('expiryDate') == expiry_dates[0]]
        
        max_ce_oi, call_wall = 0, 0
        max_pe_oi, put_wall = 0, 0
        
        for item in filtered:
            strike = item.get('strikePrice', 0)
            ce_oi = item.get('CE', {}).get('openInterest', 0)
            pe_oi = item.get('PE', {}).get('openInterest', 0)
            if ce_oi > max_ce_oi: max_ce_oi, call_wall = ce_oi, strike
            if pe_oi > max_pe_oi: max_pe_oi, put_wall = pe_oi, strike
            
        return spot_price, call_wall, put_wall, (call_wall + put_wall)/2
    except: return 0, 0, 0, 0


@st.fragment(run_every="15s")
def render_live_ticker():
    data = get_live_ticker_feed()
    items_html = ""
    for name, vals in data.items():
        if vals['price'] > 0:
            pct = vals['pct_change']
            color_class, arrow = ("t-up", "▲") if pct > 0 else ("t-dn", "▼") if pct < 0 else ("", "")
            items_html += f'<span class="ticker-item">{name}: {vals["price"]:,.2f} <span class="{color_class}">{arrow} {pct:+.2f}%</span></span>'
        else:
             items_html += f'<span class="ticker-item">{name}: AWAITING LIVE DATA</span>'
    st.markdown(f'<div class="ticker-wrap"><div class="ticker">{items_html * 3}</div></div>', unsafe_allow_html=True)

render_live_ticker()

# --- 6. 6-TIER NAVIGATION STRUCTURE ---
tabs = [
    "LIVE COCKPIT", 
    "INTRADAY INTERNALS", 
    "🧠 AI INTELLIGENCE", 
    "🔬 QUANT & ALPHA METRICS", 
    "RISK ENGINE",
    "🗄️ DATA VAULT & SYNC"
]
selected_tab = st.radio("", tabs, horizontal=True, label_visibility="collapsed")


# --- 7. MODULE FUNCTIONS ---

@st.fragment(run_every="30s")
def module_live_cockpit():
    macro = get_premarket_macro_data()
    dxy_chg = macro.get("DXY", {}).get("change", 0)
    yield_chg = macro.get("US10Y", {}).get("change", 0)
    brent_chg = macro.get("BRENT", {}).get("change", 0)
    
    risk_score = 50 + (dxy_chg * 20) + (yield_chg * 15) + (brent_chg * 10)
    risk_score = max(5.0, min(95.0, risk_score))
    
    if risk_score > 60: risk_text, risk_theme_color = "HIGH RISK (GLOBAL CAPITAL DRAIN)", "#FF5C5C"
    elif risk_score < 40: risk_text, risk_theme_color = "LOW RISK (FAVORABLE INFLOWS)", "#39D353"
    else: risk_text, risk_theme_color = "MODERATE / NEUTRAL BIAS", "#D4AF37"

    st.markdown("<div class='section-header fade-in'>PRE-MARKET MACRO RADAR (Global Institutional Flows)</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.3, 1.1, 1.3])
    
    with c1:
        st.markdown(f"""
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
        st.markdown(f"""
        <div class="panel-box fade-in" style="height: 100%;">
            <div class="panel-header">MORNING GAP & TRAP ANALYZER</div>
        """, unsafe_allow_html=True)
        
        gift_nifty_gap = st.number_input("Input Live GIFT Nifty Gap (Pts)", value=0, step=10, help="Check TradingView or your broker for the live GIFT Nifty pre-market change.")
        
        if gift_nifty_gap == 0: gap_color, gap_alert, gap_desc = "var(--text-secondary)", "AWAITING MORNING INPUT", "Input the morning gap above to calculate trap probability."
        elif st.session_state.smart_money_score < 0 and gift_nifty_gap > 20: gap_color, gap_alert, gap_desc = "var(--accent-red)", "TRAP WARNING (FADE RALLY)", "Market indicating gap UP, but FIIs hold heavy net short futures. High probability of morning exhaustion."
        elif st.session_state.smart_money_score > 0 and gift_nifty_gap < -20: gap_color, gap_alert, gap_desc = "var(--accent-green)", "TRAP WARNING (BUY THE DIP)", "Market indicating gap DOWN, but FIIs are heavily long. Retail panic selling will be absorbed."
        else: gap_color, gap_alert, gap_desc = "var(--gold-primary)", "POSITIONING ALIGNED", "Morning gap direction aligns with underlying institutional positioning. Standard trend rules apply."

        st.markdown(f"""
            <div style="font-size: 1.25rem; font-weight: 800; color: {gap_color}; margin-top: 10px; margin-bottom: 8px;">{gap_alert}</div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 15px;">{gap_desc}</div>
            <div class="setup-row"><span class="setup-label">FII Inventory Bias</span><span class="setup-val" style="color:var(--gold-primary);">{st.session_state.fii_net_futures:,.0f} Contracts</span></div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        def format_adr(val): return f"<span style='color:var(--accent-green); font-weight:700;'>+{val:.2f}%</span>" if val > 0 else (f"<span style='color:var(--accent-red); font-weight:700;'>{val:.2f}%</span>" if val < 0 else "<span style='color:var(--text-muted);'>Awaiting Sync</span>")
        st.markdown(f"""
        <div class="panel-box fade-in" style="height: 100%;">
            <div class="panel-header">OVERNIGHT US ADR TRACKER</div>
            <table class="data-table">
                <tr><th>Constituent</th><th>US Ticker</th><th>Overnight Change</th></tr>
                <tr><td><b>HDFC Bank</b></td><td>HDB</td><td>{format_adr(macro.get("HDFC_ADR", {}).get("change", 0))}</td></tr>
                <tr><td><b>ICICI Bank</b></td><td>IBN</td><td>{format_adr(macro.get("ICICI_ADR", {}).get("change", 0))}</td></tr>
                <tr><td><b>Infosys</b></td><td>INFY</td><td>{format_adr(macro.get("INFY_ADR", {}).get("change", 0))}</td></tr>
                <tr><td><b>Wipro</b></td><td>WIT</td><td>{format_adr(macro.get("WIPRO_ADR", {}).get("change", 0))}</td></tr>
                <tr><td><b>Dr. Reddy's</b></td><td>RDY</td><td>{format_adr(macro.get("DRREDDY_ADR", {}).get("change", 0))}</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    # --- INTRADAY ACTION CENTER (Combines Injected Data + Live Data) ---
    st.markdown("<div class='section-header fade-in' style='margin-top: 40px;'>INTRADAY ACTION CENTER (Retail Execution)</div>", unsafe_allow_html=True)
    
    breadth = get_real_market_breadth()
    vwap_df, vwap_score = get_real_heavyweight_vwap()
    opt_data = get_real_option_chain_data()
    spot, cw, pw, magnet = get_strike_precision_map()
    
    ad_ratio = 1.0
    if breadth and breadth['declines'] > 0: ad_ratio = breadth['advances'] / breadth['declines']
    
    verdict_color = "var(--gold-primary)"
    verdict_title = "🟡 CHOP ZONE: NO CLEAR TREND"
    verdict_text = "Market internals are mixed. Option sellers are in control. Avoid directional options today."
    
    if ad_ratio > 1.5 and vwap_score > 0 and st.session_state.smart_money_score > -2:
        verdict_color = "var(--accent-green)"
        verdict_title = "🟢 TRENDING UP: BUY THE DIPS"
        verdict_text = "Institutions are accumulating heavyweights. Breadth is positive. Do not short. Look for entries near VWAP support."
    elif ad_ratio < 0.7 and vwap_score < 0 and st.session_state.smart_money_score < 2:
        verdict_color = "var(--accent-red)"
        verdict_title = "🔴 DISTRIBUTION DAY: FADE RALLIES"
        verdict_text = "Heavyweight stocks are being sold by algorithmic blocks. Breadth is deeply negative. Do not buy breakouts."

    c4, c5, c6 = st.columns([1.5, 1.2, 1.2])
    
    with c4:
        st.markdown(f"""
        <div class="panel-box fade-in" style="height: 100%; border: 1px solid {verdict_color}; background: rgba(0,0,0,0.2);">
            <div class="panel-header" style="color: {verdict_color};">LIVE EXECUTION VERDICT</div>
            <div style="font-size: 1.4rem; font-weight: 800; color: {verdict_color}; margin-bottom: 10px;">{verdict_title}</div>
            <div style="font-size: 0.9rem; color: var(--text-primary); line-height: 1.5;">{verdict_text}</div>
            <div style="margin-top: 15px; border-top: 1px solid var(--border-subtle); padding-top: 10px;">
                <div class="setup-row"><span class="setup-label">Heavyweight Algorithmic Pull</span><span class="setup-val">{vwap_score:+.2f}%</span></div>
                <div class="setup-row"><span class="setup-label">A/D Breadth Ratio</span><span class="setup-val">{ad_ratio:.2f}</span></div>
                <div class="setup-row"><span class="setup-label">Overnight EOD Bias</span><span class="setup-val">{st.session_state.market_regime}</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with c5:
        gamma_flip = opt_data['gamma_flip'] if opt_data else "Awaiting Stream"
        gamma_flip_display = f"{gamma_flip:,.0f}" if isinstance(gamma_flip, (int, float)) else gamma_flip
        
        st.markdown(f"""
        <div class="panel-box fade-in" style="height: 100%;">
            <div class="panel-header">INSTITUTIONAL CHEAT SHEET</div>
            <div class="setup-row"><span class="setup-label" style="color:var(--accent-red);">Call Wall (Hard Resistance)</span><span class="setup-val">{cw:,.0f}</span></div>
            <div class="setup-row"><span class="setup-label" style="color:var(--gold-primary);">Gamma Flip Line (Vol Pivot)</span><span class="setup-val">{gamma_flip_display}</span></div>
            <div class="setup-row" style="background: rgba(255,255,255,0.05); padding: 5px; border-radius: 4px;"><span class="setup-label" style="color:var(--text-primary); font-weight:bold;">LIVE NIFTY SPOT</span><span class="setup-val" style="font-size:1.1rem;">{spot:,.1f}</span></div>
            <div class="setup-row"><span class="setup-label" style="color:var(--accent-green);">Put Wall (Hard Support)</span><span class="setup-val">{pw:,.0f}</span></div>
        </div>
        """, unsafe_allow_html=True)
        
    with c6:
        engine_html = ""
        if not vwap_df.empty and vwap_df.iloc[0]["State"] not in ["AWAITING MARKET OPEN", "DATA UNAVAILABLE"]:
            for _, r in vwap_df.head(3).iterrows():
                c_style = "color: var(--accent-green);" if r["Divergence"] > 0 else "color: var(--accent-red);"
                engine_html += f"<div class='setup-row' style='padding: 10px 0;'><span class='setup-label' style='font-weight:700; color:var(--text-primary);'>{r['Symbol']}</span><div style='text-align: right;'><div class='setup-val' style='{c_style}'>{r['Price']:,.1f}</div><div style='font-size: 0.7rem; color: var(--text-muted);'>VWAP: {r['VWAP']:,.1f}</div></div></div>"
        else:
            engine_html = "<div style='color:var(--text-muted); text-align:center; padding: 20px 0;'>Awaiting Market Open</div>"
            
        st.markdown(f"""
        <div class="panel-box fade-in" style="height: 100%;">
            <div class="panel-header">INDEX ENGINE ROOM (TOP 3)</div>
            {engine_html}
        </div>
        """, unsafe_allow_html=True)

@st.fragment(run_every="30s")
def module_intraday_internals():
    st.markdown("<h2 class='fade-in' style='font-weight: 700; margin-bottom: 20px;'>LIVE INTRADAY INTERNALS: BREADTH & SECTOR ROTATION</h2>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.markdown("""<div class="panel-box fade-in" style="height:100%;"><div class="panel-header">INDEX MARKET BREADTH (The Internal Strength X-Ray)</div>""", unsafe_allow_html=True)
        breadth_data = get_real_market_breadth()
        if breadth_data is None or (breadth_data["advances"] == 0 and breadth_data["declines"] == 0):
            st.markdown("""<div style="text-align:center; padding: 30px 0; color:var(--text-secondary);"><b>Awaiting Live Breadth Data</b></div></div>""", unsafe_allow_html=True)
        else:
            adv, dec, unc = breadth_data["advances"], breadth_data["declines"], breadth_data["unchanged"]
            ad_ratio = adv / dec if dec > 0 else adv
            if ad_ratio > 1.5: breadth_state, breadth_color, breadth_msg = "STRONG INTERNAL BUYING", "var(--accent-green)", "The majority of index stocks are moving up."
            elif ad_ratio < 0.7: breadth_state, breadth_color, breadth_msg = "SEVERE INTERNAL SELLING", "var(--accent-red)", "The majority of stocks are falling. Prepare for a reversal."
            else: breadth_state, breadth_color, breadth_msg = "CHOPPY / MIXED INTERNALS", "var(--gold-primary)", "Stock participation is split."

            st.markdown(f"""
                <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
                    <div style="text-align:center;"><div style="font-size:2.2rem; font-weight:800; color:var(--accent-green);">{adv}</div><div style="font-size:0.8rem; color:var(--text-muted); text-transform:uppercase;">Advances</div></div>
                    <div style="text-align:center;"><div style="font-size:2.2rem; font-weight:800; color:var(--accent-red);">{dec}</div><div style="font-size:0.8rem; color:var(--text-muted); text-transform:uppercase;">Declines</div></div>
                    <div style="text-align:center;"><div style="font-size:2.2rem; font-weight:800; color:var(--text-secondary);">{unc}</div><div style="font-size:0.8rem; color:var(--text-muted); text-transform:uppercase;">Unchanged</div></div>
                </div>
                <div class="setup-row" style="margin-top:20px;"><span class="setup-label">Advance/Decline Ratio</span><span class="setup-val">{ad_ratio:.2f}</span></div>
                <div class="setup-row"><span class="setup-label">Internal Status</span><span class="setup-val" style="color:{breadth_color};">{breadth_state}</span></div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("""<div class="panel-box fade-in" style="height:100%;"><div class="panel-header">SECTORAL RELATIVE STRENGTH (The Money Rotation Map)</div>""", unsafe_allow_html=True)
        sector_df = get_real_sectoral_data()
        if sector_df is None or sector_df.empty:
            st.markdown("""<div style="text-align:center; padding: 30px 0; color:var(--text-secondary);"><b>Awaiting Live Sector Data</b></div></div>""", unsafe_allow_html=True)
        else:
            table_html = '<div style="max-height: 400px; overflow-y: auto;"><table class="data-table"><tr><th>Index / Sector</th><th>Live Price</th><th>Intraday Change</th><th>Institutional Flow</th></tr>'
            for _, r in sector_df.iterrows():
                chg = r["Change"]
                c_style = "color: var(--accent-green);" if chg > 0 else "color: var(--accent-red);" if chg < 0 else ""
                indicator = "🟢" if chg > 0 else "🔴" if chg < 0 else "⚪"
                bold_name = f"<span style='color:var(--gold-primary); font-weight:800;'>{r['Sector']}</span>" if "Benchmark" in r["Sector"] else f"<b>{r['Sector']}</b>"
                table_html += f"<tr><td>{bold_name}</td><td>₹{r['Price']:,.1f}</td><td style='{c_style}; font-weight:700;'>{chg:+.2f}%</td><td>{indicator} {r['State']}</td></tr>"
            table_html += "</table></div>"
            st.markdown(table_html + "</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-header fade-in' style='margin-top: 40px;'>INSTITUTIONAL ALGORITHMIC SCREENER</div>", unsafe_allow_html=True)
    df_vwap, composite_score = get_real_heavyweight_vwap()
    col3, col4 = st.columns([2.5, 1])
    with col3:
        st.markdown("""<div class="panel-box fade-in" style="height:100%;"><div class="panel-header">ALGORITHMIC VWAP DIVERGENCE</div>""", unsafe_allow_html=True)
        table_html = '<table class="data-table"><tr><th>Symbol</th><th>Weightage</th><th>LTP</th><th>Intraday VWAP</th><th>VWAP Divergence</th><th>Algorithmic State</th></tr>'
        for _, r in df_vwap.iterrows():
            div = r["Divergence"]
            if r["State"] in ["AWAITING MARKET OPEN", "DATA UNAVAILABLE"]: table_html += f"<tr><td><b>{r['Symbol']}</b></td><td>{r['Weight']}</td><td>--</td><td>--</td><td>--</td><td><span style='color:var(--text-muted);'>{r['State']}</span></td></tr>"
            else:
                c_style = "color: var(--accent-green);" if div > 0 else "color: var(--accent-red);" if div < 0 else ""
                indicator = "🟢" if div > 0 else "🔴" if div < 0 else "⚪"
                table_html += f"<tr><td><b>{r['Symbol']}</b></td><td>{r['Weight']}</td><td>₹{r['Price']:,.2f}</td><td>₹{r['VWAP']:,.2f}</td><td style='{c_style}; font-weight:600;'>{div:+.3f}%</td><td>{indicator} {r['State']}</td></tr>"
        st.markdown(table_html + "</table></div>", unsafe_allow_html=True)

    with col4:
        if df_vwap.iloc[0]["State"] in ["AWAITING MARKET OPEN", "DATA UNAVAILABLE"]: box_class, text_color, bias_text = "", "var(--text-secondary)", "AWAITING TICK DATA"
        else:
            box_class = "bullish" if composite_score > 0 else ""
            text_color = "var(--accent-green)" if composite_score > 0 else "var(--accent-red)"
            bias_text = "HEAVYWEIGHT ACCUMULATION" if composite_score > 0 else "DISTRIBUTION DRAG"
        st.markdown(f"""
        <div class="fade-in composite-box {box_class}" style="height:100%;">
            <div style="font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 600; margin-bottom: 5px;">Composite Algorithmic Pull</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: {text_color};">{composite_score:+.3f}%</div>
            <div style="font-size: 0.9rem; color: {text_color}; margin-top: 5px; font-weight: 600;">{bias_text}</div>
        </div>
        """, unsafe_allow_html=True)

@st.fragment(run_every="30s")
def module_quant_alpha_metrics():
    st.markdown("<h2 class='fade-in' style='font-weight: 800; color: var(--text-primary); margin-bottom: 20px; letter-spacing: 1px;'>🔬 QUANTITATIVE & ALPHA METRICS</h2>", unsafe_allow_html=True)
    
    opt_data = get_real_option_chain_data()
    delivery_df = get_real_delivery_zscores()
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""<div class="panel-box fade-in">""", unsafe_allow_html=True)
        st.markdown("<div class=\"panel-header\">DEALER NET GAMMA EXPOSURE (GEX)</div>", unsafe_allow_html=True)
        if opt_data:
            tot_gex = opt_data["total_gex"]
            g_flip = opt_data["gamma_flip"]
            spot = opt_data["spot"]
            g_regime = "LONG GAMMA (VOLATILITY DAMPENING)" if tot_gex >= 0 else "SHORT GAMMA (VOLATILITY ACCELERATION)"
            g_color = "#39D353" if tot_gex >= 0 else "#FF5C5C"
            st.markdown(f"""
                <div style="font-size: 1.8rem; font-weight: 800; color: {g_color}; margin-bottom: 6px;">₹{tot_gex:+,.1f} Cr</div>
                <div style="font-size: 0.85rem; color: {g_color}; font-weight: 700; margin-bottom: 12px;">{g_regime}</div>
                <div class="setup-row"><span class="setup-label">Gamma Flip Threshold</span><span class="setup-val" style="color:var(--gold-primary);">{g_flip:,.0f}</span></div>
                <div class="setup-row"><span class="setup-label">Distance to Volatility Flip</span><span class="setup-val">{spot - g_flip:+,.1f} Pts</span></div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:var(--text-muted); padding:30px 0; text-align:center;'>Awaiting Live Option Chain Stream</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("""<div class="panel-box fade-in">""", unsafe_allow_html=True)
        st.markdown("<div class=\"panel-header\">CASH-FUTURES BASIS & COST OF CARRY (CoC)</div>", unsafe_allow_html=True)
        if opt_data:
            basis = opt_data["basis"]
            coc = opt_data["coc_annual"]
            b_color = "#39D353" if basis >= 0 else "#FF5C5C"
            b_state = "PREMIUM (BULLISH CARRY)" if basis >= 0 else "DISCOUNT (INSTITUTIONAL HEDGING)"
            st.markdown(f"""
                <div style="font-size: 1.8rem; font-weight: 800; color: {b_color}; margin-bottom: 6px;">{basis:+,.2f} Pts</div>
                <div style="font-size: 0.85rem; color: {b_color}; font-weight: 700; margin-bottom: 12px;">{b_state}</div>
                <div class="setup-row"><span class="setup-label">Annualized Cost of Carry</span><span class="setup-val" style="color:var(--gold-primary);">{coc:+.2f}% p.a.</span></div>
                <div class="setup-row"><span class="setup-label">Days to Expiry Calibration</span><span class="setup-val">{opt_data['days_to_expiry']} Days</span></div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:var(--text-muted); padding:30px 0; text-align:center;'>Awaiting Live Basis Sync</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("""<div class="panel-box fade-in">""", unsafe_allow_html=True)
        st.markdown("<div class=\"panel-header\">25-DELTA IMPLIED VOLATILITY SKEW SURFACE</div>", unsafe_allow_html=True)
        if opt_data:
            skew = opt_data["skew_25d"]
            iv_put = opt_data["iv_25d_put"]
            iv_call = opt_data["iv_25d_call"]
            skew_status = "HEAVY TAIL-RISK PROTECTION (BEARISH SKEW)" if skew > 1.5 else ("CALL DEMAND EXPANSION" if skew < -1.0 else "BALANCED VOLATILITY SURFACE")
            s_color = "#FF5C5C" if skew > 1.5 else ("#39D353" if skew < -1.0 else "var(--gold-primary)")
            st.markdown(f"""
                <div style="font-size: 1.8rem; font-weight: 800; color: {s_color}; margin-bottom: 6px;">{skew:+.2f}% IV Spread</div>
                <div style="font-size: 0.85rem; color: {s_color}; font-weight: 700; margin-bottom: 12px;">{skew_status}</div>
                <div class="setup-row"><span class="setup-label">25-Delta OTM Put IV (Downside Insurance)</span><span class="setup-val" style="color:#FF5C5C;">{iv_put:.2f}%</span></div>
                <div class="setup-row"><span class="setup-label">25-Delta OTM Call IV (Upside Participation)</span><span class="setup-val" style="color:#39D353;">{iv_call:.2f}%</span></div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:var(--text-muted); padding:30px 0; text-align:center;'>Awaiting Option Volatility Surface</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""<div class="panel-box fade-in">""", unsafe_allow_html=True)
        st.markdown("<div class=\"panel-header\">INSTITUTIONAL VOLUME Z-SCORES (HEAVYWEIGHT DEMAT FLOWS)</div>", unsafe_allow_html=True)
        if delivery_df is not None and not delivery_df.empty:
            table_html = '<table class="data-table"><tr><th>Constituent</th><th>Rolling 20D Mean</th><th>Z-Score</th><th>Flow Interpretation</th></tr>'
            for _, r in delivery_df.iterrows():
                z = r["Z_Score"]
                z_c = "color: var(--accent-green);" if z > 1.0 else ("color: var(--accent-red);" if z < -1.0 else "")
                table_html += f"<tr><td><b>{r['Stock']}</b></td><td>{r['Mean_20D']:,.0f}</td><td style='{z_c} font-weight:700;'>{z:+.2f}σ</td><td>{r['State']}</td></tr>"
            table_html += "</table>"
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:var(--text-muted); padding:30px 0; text-align:center;'>Awaiting Exchange Delivery Records</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

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
        spot, cw, pw, magnet = get_strike_precision_map()
        st.markdown("""<div class="panel-box fade-in" style="height: 100%;">
        <div class="panel-header">INSTITUTIONAL STRIKE PRECISION MAP</div>""", unsafe_allow_html=True)
        
        if spot > 0:
            st.markdown(f"""
            <div style="text-align:center; margin-bottom: 20px;">
                <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase;">Live Nifty Spot Reference</div>
                <div style="font-size: 2rem; font-weight: 800; color: var(--text-primary);">{spot:,.1f}</div>
            </div>
            <div class="setup-row"><span class="setup-label" style="color:var(--accent-red);">Call Wall (Hard Resistance)</span><span class="setup-val">{cw:,.0f}</span></div>
            <div class="setup-row"><span class="setup-label" style="color:var(--gold-primary);">Max Pain (Options Magnet)</span><span class="setup-val">{magnet:,.0f}</span></div>
            <div class="setup-row"><span class="setup-label" style="color:var(--accent-green);">Put Wall (Hard Support)</span><span class="setup-val">{pw:,.0f}</span></div>
            <div class="directive-box">
                <b>EXECUTION DIRECTIVE:</b> {"Sell rallies towards Call Wall resistance." if bias_score < 0 else "Buy dips near Put Wall support." if bias_score > 0 else "Fade extreme deviations from Max Pain."} If spot breaks Call Wall or Put Wall, expect aggressive institutional gamma squeezes.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align:center; padding: 40px 0; color: var(--text-muted);'>Awaiting Live Option Chain Sync</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

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

    # --- COMPACT HORIZONTAL DUCKDB STATUS BAR ---
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

    # --- AUTO-COLLAPSING BATCH UPLOADER EXPANDER ---
    is_open = st.session_state.participant_matrix_curr is None
    with st.expander("⚙️ BATCH DATA OVERRIDE & REPORT GENERATION", expanded=is_open):
        st.markdown("<div style='color:var(--text-secondary); margin-bottom:15px; font-size:0.85rem;'><b>SMART BATCH UPLOAD:</b> Drop all T-1 files into Box 1. Drop all T files into Box 2. The AI will automatically identify Participant OI and Delivery files.</div>", unsafe_allow_html=True)
        
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

# --- 8. EXECUTION ROUTER ---
if selected_tab == "LIVE COCKPIT":
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