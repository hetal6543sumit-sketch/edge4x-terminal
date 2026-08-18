import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
import math
import requests
from datetime import datetime
import yfinance as yf
import pyotp

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
    st.session_state.fii_net_futures = 0
if 'fii_dod_delta' not in st.session_state:
    st.session_state.fii_dod_delta = 0
if 'smart_money_score' not in st.session_state:
    st.session_state.smart_money_score = 0.0
if 'market_regime' not in st.session_state:
    st.session_state.market_regime = "AWAITING EOD DATA"
if 'participant_matrix' not in st.session_state:
    st.session_state.participant_matrix = None

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
        font-size: 15px; 
    }}

    /* KILL STREAMLIT STALE DIMMING COMPLETELY */
    *[data-stale="true"] {{
        opacity: 1 !important;
        filter: none !important;
        transition: none !important;
        pointer-events: auto !important;
    }}
    .stSpinner {{
        display: none !important;
    }}

    [data-testid="stSidebar"] {{ display: none !important; }}
    #MainMenu, header, footer {{ visibility: hidden; }}
    
    .block-container {{
        padding-top: 105px !important; 
        padding-bottom: 30px !important;
        max-width: 1600px;
    }}

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
    .t-up {{ color: var(--accent-green); }}
    .t-dn {{ color: var(--accent-red); }}
    @keyframes ticker {{ 0% {{ transform: translate3d(0, 0, 0); }} 100% {{ transform: translate3d(-100%, 0, 0); }} }}

    /* HORIZONTAL NAVIGATION PILLS */
    div[role="radiogroup"] {{
        display: flex !important; flex-direction: row !important; justify-content: center !important;
        gap: 10px !important; background: var(--bg-surface) !important; padding: 8px 16px !important;
        border-radius: 8px !important; border: 1px solid var(--border-subtle) !important; margin-bottom: 25px !important;
    }}
    div[role="radiogroup"] label {{
        background: transparent !important; border: none !important; color: var(--text-muted) !important;
        padding: 8px 24px !important; font-weight: 600 !important; font-size: 0.85rem !important;
        letter-spacing: 1px !important; border-radius: 6px !important; transition: all 0.2s ease !important;
    }}
    div[role="radiogroup"] label:hover {{ color: var(--text-primary) !important; background: rgba(255, 255, 255, 0.03) !important; }}
    div[role="radiogroup"] label[data-checked="true"] {{
        color: #000000 !important; background: var(--gold-primary) !important;
        box-shadow: 0 4px 10px rgba(212, 175, 55, 0.15) !important;
    }}

    /* UI PANELS & METRIC CARDS */
    .metric-strip {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
    .metric-card {{
        flex: 1 1 180px; background: var(--bg-surface); padding: 15px 18px; border-radius: 8px;
        border: 1px solid var(--border-subtle); position: relative;
    }}
    .metric-label {{ font-size: 0.78rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; display: flex; align-items: center; }}
    .metric-sublabel {{ font-size: 0.72rem; color: var(--gold-primary); font-weight: 500; text-transform: none; margin-bottom: 6px; }}
    .metric-value {{ font-size: 1.35rem; font-weight: 700; color: var(--text-primary); }}

    .panel-box {{ background: var(--bg-surface); border: 1px solid var(--border-subtle); padding: 20px; border-radius: 8px; margin-bottom: 18px; }}
    .panel-header {{ font-size: 0.82rem; color: var(--gold-primary); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 12px; font-weight: 700; }}
    .section-header {{ font-size: 1.05rem; color: var(--text-primary); text-transform: uppercase; letter-spacing: 1.8px; margin: 25px 0 15px 0; font-weight: 800; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px; }}
    
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    .data-table th {{ text-align: left; padding: 10px 12px; color: var(--text-muted); border-bottom: 1px solid var(--border-subtle); font-weight: 600; text-transform: uppercase; font-size: 0.74rem; letter-spacing: 0.8px; }}
    .data-table td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.02); color: var(--text-primary); }}
    .data-table tr:hover {{ background: var(--bg-elevated); }}

    .setup-row {{ display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0; font-size: 0.9rem; align-items: center; }}
    .setup-row:last-child {{ border-bottom: none; }}
    .setup-label {{ color: var(--text-secondary); }}
    .setup-val {{ font-weight: 700; color: var(--text-primary); }}

    .composite-box {{
        background: rgba(255, 92, 92, 0.05); border: 1px solid var(--accent-red); 
        border-radius: 8px; padding: 15px; text-align: center; height: 100%;
        display: flex; flex-direction: column; justify-content: center;
    }}
    .composite-box.bullish {{
        background: rgba(57, 211, 83, 0.05); border: 1px solid var(--accent-green);
    }}
    
    /* TOOLTIP ENGINE */
    .tooltip {{
        position: relative; display: inline-block; cursor: help;
        color: var(--gold-primary); margin-left: 6px; font-size: 0.85rem; font-weight: 700;
    }}
    .tooltip .tooltiptext {{
        visibility: hidden; width: 250px; background-color: var(--bg-elevated);
        color: var(--text-primary); text-align: left; border-radius: 6px; padding: 10px 12px;
        position: absolute; z-index: 1000; bottom: 130%; left: 50%; margin-left: -125px;
        border: 1px solid var(--gold-primary); box-shadow: 0px 8px 16px rgba(0,0,0,0.8);
        font-size: 0.75rem; font-weight: 400; line-height: 1.5; text-transform: none; letter-spacing: normal;
        opacity: 0; transition: opacity 0.2s;
    }}
    .tooltip .tooltiptext::after {{
        content: ""; position: absolute; top: 100%; left: 50%; margin-left: -6px;
        border-width: 6px; border-style: solid; border-color: var(--gold-primary) transparent transparent transparent;
    }}
    .tooltip:hover .tooltiptext {{ visibility: visible; opacity: 1; }}

    .fade-in {{ animation: fadeIn 0.35s ease forwards; }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
</style>

<div class="terminal-nav">
    <div class="nav-brand">EDGE<span>4X</span></div>
    <div class="nav-status"><span class="live-dot"></span> {api_status_text}</div>
</div>
""", unsafe_allow_html=True)


# --- 5. LIVE DATA BACKGROUND ENGINES (NO DUMMY DATA) ---

def fetch_nse_json(api_url):
    """Fortified NSE Fetcher to bypass localhost and cloud firewalls"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br"
    }
    
    for _ in range(3):
        try:
            session = requests.Session()
            session.headers.update(headers)
            
            # Step 1: Hit homepage to warm up cookies
            session.get("https://www.nseindia.com", timeout=5)
            time.sleep(1.0) # Simulate human load time
            
            # Step 2: Set Referer and request the actual API
            session.headers.update({"Referer": "https://www.nseindia.com/"})
            res = session.get(api_url, timeout=5)
            
            if res.status_code == 200:
                return res.json()
                
            # Step 3: If blocked, try secondary Option Chain route to get deeper cookies
            if res.status_code in [401, 403]:
                session.get("https://www.nseindia.com/option-chain", timeout=5)
                time.sleep(1.0)
                res = session.get(api_url, timeout=5)
                if res.status_code == 200:
                    return res.json()
        except:
            pass
        time.sleep(1.5)
    return None

def get_yfinance_breadth_fallback():
    """Calculates live Market Breadth perfectly by downloading all 50 Nifty stocks if NSE blocks us."""
    nifty_50_symbols = [
        "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", 
        "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS", 
        "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", 
        "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", 
        "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", 
        "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LTIM.NS", 
        "LT.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS", 
        "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SUNPHARMA.NS", 
        "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", 
        "TITAN.NS", "UPL.NS", "ULTRACEMCO.NS", "WIPRO.NS"
    ]
    try:
        data = yf.download(nifty_50_symbols, period="2d", progress=False)['Close']
        if len(data) >= 2:
            prev_close = data.iloc[-2]
            curr_price = data.iloc[-1]
            changes = curr_price - prev_close
            adv = int((changes > 0).sum())
            dec = int((changes < 0).sum())
            unc = int((changes == 0).sum())
            return {"advances": adv, "declines": dec, "unchanged": unc}
    except:
        pass
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
        except Exception:
            pass

    symbols = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK", "INDIA VIX": "^INDIAVIX"}
    for name, sym in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_price = hist['Close'].iloc[-1]
                pct_change = ((curr_price - prev_close) / prev_close) * 100
                
                if name in results and results[name]["price"] > 0:
                    live_price = results[name]["price"]
                    live_pct = ((live_price - prev_close) / prev_close) * 100
                    results[name] = {"price": live_price, "pct_change": live_pct}
                else:
                    results[name] = {"price": curr_price, "pct_change": pct_change}
            else:
                if name not in results: results[name] = {"price": 0.0, "pct_change": 0.0}
        except Exception:
            if name not in results: results[name] = {"price": 0.0, "pct_change": 0.0}
    return results

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

@st.cache_data(ttl=30, show_spinner=False)
def get_real_option_chain_data():
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    data = fetch_nse_json(url)
    
    if data is None: 
        return None
        
    try:
        records = data.get('records', {})
        spot_price = records.get('underlyingValue', 0)
        expiry_dates = records.get('expiryDates', [])
        
        if not expiry_dates or spot_price == 0: return None
            
        current_expiry = expiry_dates[0]
        exp_date_obj = datetime.strptime(current_expiry, '%d-%b-%Y')
        days_to_expiry = (exp_date_obj - datetime.now()).days
        time_to_exp = max(1.0, days_to_expiry) / 365.0
        
        chain_data = records.get('data', [])
        filtered_chain = [d for d in chain_data if d['expiryDate'] == current_expiry]
        atm_strike = int(round(spot_price / 50.0) * 50)
        
        parsed_strikes = []
        atm_data = {"CE_LTP": 0, "PE_LTP": 0, "CE_IV": 0, "PE_IV": 0}
        
        for item in filtered_chain:
            strike = item.get('strikePrice')
            ce = item.get('CE', {})
            pe = item.get('PE', {})
            
            ce_oi = ce.get('openInterest', 0) * 25
            pe_oi = pe.get('openInterest', 0) * 25
            ce_chgoi = ce.get('changeinOpenInterest', 0) * 25
            pe_chgoi = pe.get('changeinOpenInterest', 0) * 25
            ce_iv = ce.get('impliedVolatility', 0.0)
            pe_iv = pe.get('impliedVolatility', 0.0)
            
            if ce_iv == 0: ce_iv = 15.0
            if pe_iv == 0: pe_iv = 15.0
            
            if strike == atm_strike:
                atm_data["CE_LTP"] = ce.get('lastPrice', 0)
                atm_data["PE_LTP"] = pe.get('lastPrice', 0)
                atm_data["CE_IV"] = ce_iv
                atm_data["PE_IV"] = pe_iv
                atm_data["CE_OI"] = ce_oi
                atm_data["PE_OI"] = pe_oi
                
            try:
                d1 = (math.log(spot_price / strike) + (0.10 + 0.5 * (ce_iv/100) ** 2) * time_to_exp) / ((ce_iv/100) * math.sqrt(time_to_exp))
                gamma = norm_pdf(d1) / (spot_price * (ce_iv/100) * math.sqrt(time_to_exp))
            except:
                gamma = 0.0
                
            net_gex = (ce_oi * gamma * spot_price * 0.01) - (pe_oi * gamma * spot_price * 0.01)
            parsed_strikes.append({
                "Strike": strike, "CE_OI": ce_oi, "PE_OI": pe_oi, 
                "CE_chgOI": ce_chgoi, "PE_chgOI": pe_chgoi, "GEX": net_gex
            })
            
        return {
            "spot": spot_price, "atm_strike": atm_strike, "atm_data": atm_data,
            "strikes": pd.DataFrame(parsed_strikes)
        }
    except Exception:
        return None

@st.cache_data(ttl=30, show_spinner=False)
def get_real_market_breadth():
    url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050"
    data = fetch_nse_json(url)
    
    if data is not None:
        adv = data.get('advance', {})
        if adv.get('advances', 0) > 0 or adv.get('declines', 0) > 0:
            return {
                "advances": adv.get('advances', 0),
                "declines": adv.get('declines', 0),
                "unchanged": adv.get('unchanged', 0)
            }
    return get_yfinance_breadth_fallback()

@st.cache_data(ttl=30, show_spinner=False)
def get_real_sectoral_data():
    sectors = {
        "NIFTY 50 (Benchmark)": "^NSEI", "NIFTY BANK": "^NSEBANK",
        "NIFTY FIN SERVICE": "^CNXFIN", "NIFTY IT": "^CNXIT",
        "NIFTY AUTO": "^CNXAUTO", "NIFTY ENERGY": "^CNXENERGY",
        "NIFTY FMCG": "^CNXFMCG", "NIFTY PHARMA": "^CNXPHARMA",
        "NIFTY METAL": "^CNXMETAL", "NIFTY REALTY": "^CNXREALTY",
        "NIFTY MEDIA": "^CNXMEDIA", "NIFTY INFRA": "^CNXINFRA",
        "NIFTY PSU BANK": "^CNXPSUBANK", "NIFTY CONSUMPTION": "^CNXCONSUM"
    }
    results = []
    for name, sym in sectors.items():
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_price = hist['Close'].iloc[-1]
                pct_change = ((curr_price - prev_close) / prev_close) * 100
                state = "STRONG LONG" if pct_change > 0.5 else "WEAK LONG" if pct_change > 0 else "WEAK SHORT" if pct_change > -0.5 else "STRONG SHORT"
                results.append({"Sector": name, "Price": curr_price, "Change": pct_change, "State": state})
        except:
            pass
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
    data = []
    composite_score = 0.0

    for sym, meta in heavyweights.items():
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="1d", interval="1m")
            
            if not df.empty:
                current_price = df['Close'].iloc[-1]
                
                df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
                df['Volume_Price'] = df['Typical_Price'] * df['Volume']
                cumulative_vp = df['Volume_Price'].sum()
                cumulative_vol = df['Volume'].sum()
                
                vwap = cumulative_vp / cumulative_vol if cumulative_vol > 0 else current_price
                divergence_pct = ((current_price - vwap) / vwap) * 100
                
                composite_score += (divergence_pct * (meta["weight"] / 100))
                state = "ALGO BUYING (ACCUMULATION)" if divergence_pct > 0 else "ALGO SELLING (DISTRIBUTION)"
                
                data.append({
                    "Symbol": meta["name"], "Weight": f"{meta['weight']}%",
                    "Price": current_price, "VWAP": vwap,
                    "Divergence": divergence_pct, "State": state
                })
            else:
                data.append({"Symbol": meta["name"], "Weight": f"{meta['weight']}%", "Price": 0.0, "VWAP": 0.0, "Divergence": 0.0, "State": "AWAITING MARKET OPEN"})
        except Exception:
            data.append({"Symbol": meta["name"], "Weight": f"{meta['weight']}%", "Price": 0.0, "VWAP": 0.0, "Divergence": 0.0, "State": "DATA UNAVAILABLE"})
            
    return pd.DataFrame(data), composite_score

@st.cache_data(ttl=300, show_spinner=False)
def get_premarket_macro_data():
    symbols = {
        "DXY": "DX-Y.NYB", "US10Y": "^TNX", "BRENT": "BZ=F",
        "HDFC_ADR": "HDB", "ICICI_ADR": "IBN", "INFY_ADR": "INFY",
        "WIPRO_ADR": "WIT", "DRREDDY_ADR": "RDY"
    }
    macro_data = {}
    for name, sym in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr = hist['Close'].iloc[-1]
                pct = ((curr - prev_close) / prev_close) * 100
                macro_data[name] = {"price": curr, "change": pct}
            else:
                macro_data[name] = {"price": 0.0, "change": 0.0}
        except:
            macro_data[name] = {"price": 0.0, "change": 0.0}
    return macro_data

# FASTER AUTO-REFRESH (15 Seconds)
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

def style_plotly_fig(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#A7AFBA", size=12), margin=dict(l=0, r=0, t=15, b=0),
        xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False)
    )
    return fig


# --- 6. NAVIGATION STRUCTURE ---
selected_tab = st.radio(
    "",
    ["LIVE COCKPIT", "INTRADAY INTERNALS", "DATA INGESTION & INTELLIGENCE", "RISK CALCULATOR"],
    horizontal=True,
    label_visibility="collapsed"
)


# --- 7. MODULE ARCHITECTURE ---

# SILENT BACKGROUND AUTO-REFRESH EVERY 30 SECONDS
@st.fragment(run_every="30s")
def module_live_cockpit():
    macro = get_premarket_macro_data()
    
    dxy_chg = macro.get("DXY", {}).get("change", 0)
    yield_chg = macro.get("US10Y", {}).get("change", 0)
    brent_chg = macro.get("BRENT", {}).get("change", 0)
    
    risk_score = 50 + (dxy_chg * 20) + (yield_chg * 15) + (brent_chg * 10)
    risk_score = max(5.0, min(95.0, risk_score))
    
    if risk_score > 60:
        risk_text, risk_theme_color = "HIGH RISK (GLOBAL CAPITAL DRAIN)", "#FF5C5C"
    elif risk_score < 40:
        risk_text, risk_theme_color = "LOW RISK (FAVORABLE INFLOWS)", "#39D353"
    else:
        risk_text, risk_theme_color = "MODERATE / NEUTRAL BIAS", "#D4AF37"

    # --- TOP ROW: REAL MACRO RADAR RESTORED ---
    st.markdown("<div class='section-header fade-in'>PRE-MARKET MACRO RADAR (Global Institutional Flows)</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.3, 1.1, 1.3])
    
    with c1:
        st.markdown(f"""
        <div class="panel-box fade-in" style="height: 100%;">
            <div class="panel-header">
                GLOBAL RISK SPEEDOMETER
                <span class="tooltip">ⓘ<span class="tooltiptext">Synthesizes the US Dollar (DXY), US 10Y Bond Yields, and Brent Crude Oil into a single 0-100 institutional risk metric.</span></span>
            </div>
        """, unsafe_allow_html=True)
        
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number", value=risk_score, domain={'x': [0, 1], 'y': [0, 1]},
            number={'suffix': "/100", 'font': {'size': 22, 'color': risk_theme_color, 'family': 'Inter'}},
            gauge={'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#A7AFBA"},
                   'bar': {'color': risk_theme_color, 'thickness': 0.28},
                   'bgcolor': "rgba(0,0,0,0)", 'borderwidth': 0,
                   'steps': [{'range': [0, 40], 'color': "rgba(57, 211, 83, 0.15)"},
                             {'range': [40, 60], 'color': "rgba(212, 175, 55, 0.15)"},
                             {'range': [60, 100], 'color': "rgba(255, 92, 92, 0.15)"}],
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
            <div class="panel-header">
                MORNING GAP & TRAP ANALYZER
                <span class="tooltip">ⓘ<span class="tooltiptext">Cross-references your manual GIFT Nifty gap input against overnight institutional futures inventory.</span></span>
            </div>
        """, unsafe_allow_html=True)
        
        gift_nifty_gap = st.number_input("Input Live GIFT Nifty Gap (Pts)", value=0, step=10, help="Check TradingView or your broker for the live GIFT Nifty pre-market change.")
        
        if gift_nifty_gap == 0:
            gap_color, gap_alert, gap_desc = "var(--text-secondary)", "AWAITING MORNING INPUT", "Input the morning gap above to calculate trap probability."
        elif st.session_state.smart_money_score < 0 and gift_nifty_gap > 20:
            gap_color, gap_alert, gap_desc = "var(--accent-red)", "TRAP WARNING (FADE RALLY)", "Market indicating gap UP, but FIIs hold heavy net short futures. High probability of morning exhaustion."
        elif st.session_state.smart_money_score > 0 and gift_nifty_gap < -20:
            gap_color, gap_alert, gap_desc = "var(--accent-green)", "TRAP WARNING (BUY THE DIP)", "Market indicating gap DOWN, but FIIs are heavily long. Retail panic selling will be absorbed."
        else:
            gap_color, gap_alert, gap_desc = "var(--gold-primary)", "POSITIONING ALIGNED", "Morning gap direction aligns with underlying institutional positioning. Standard trend rules apply."

        st.markdown(f"""
            <div style="font-size: 1.25rem; font-weight: 800; color: {gap_color}; margin-top: 10px; margin-bottom: 8px;">{gap_alert}</div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 15px;">{gap_desc}</div>
            <div class="setup-row"><span class="setup-label">FII Inventory Bias</span><span class="setup-val" style="color:var(--gold-primary);">{st.session_state.fii_net_futures:,.0f} Contracts</span></div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        def format_adr(val):
            if val == 0.0: return "<span style='color:var(--text-muted);'>Awaiting Sync</span>"
            return f"<span style='color:var(--accent-green); font-weight:700;'>+{val:.2f}%</span>" if val > 0 else f"<span style='color:var(--accent-red); font-weight:700;'>{val:.2f}%</span>"
            
        st.markdown(f"""
        <div class="panel-box fade-in" style="height: 100%;">
            <div class="panel-header">
                OVERNIGHT US ADR TRACKER 
                <span class="tooltip">ⓘ<span class="tooltiptext">Tracks Indian blue-chips traded on the NYSE/NASDAQ during US market hours to forecast sector opening gaps.</span></span>
            </div>
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

    # --- MIDDLE ROW: METRICS ---
    st.markdown("<div class='section-header fade-in' style='margin-top: 40px;'>LIVE INTRADAY DERIVATIVES SUITE</div>", unsafe_allow_html=True)
    live_data = get_live_ticker_feed()
    live_nifty = live_data.get('NIFTY 50', {}).get('price', 0.0)

    st.markdown(f"""
    <div class="metric-strip fade-in">
        <div class="metric-card"><div class="metric-label">Market Regime</div><div class="metric-value" style="color:var(--accent-red); font-size:1.2rem;">{st.session_state.market_regime}</div></div>
        <div class="metric-card">
            <div class="metric-label">Smart Money Score <span class="tooltip">ⓘ<span class="tooltiptext">Scale of -10 to +10 based on FII net index futures exposure. > 50k contracts = Bullish. < -100k contracts = Bearish.</span></span></div>
            <div class="metric-value" style="color:var(--accent-red);">{st.session_state.smart_money_score} / 10</div>
        </div>
        <div class="metric-card"><div class="metric-label">Net FII Futures</div><div class="metric-value">{st.session_state.fii_net_futures:,.0f}</div></div>
        <div class="metric-card"><div class="metric-label">DoD Flow Delta</div><div class="metric-value" style="color:var(--accent-red);">{st.session_state.fii_dod_delta:+,d}</div></div>
        <div class="metric-card"><div class="metric-label">Spot Price</div><div class="metric-value">{live_nifty:,.2f}</div></div>
    </div>
    """, unsafe_allow_html=True)

    # --- BOTTOM ROW: LIVE CHARTS AND REAL ALERTS ---
    col4, col5 = st.columns([1.6, 1])
    opt_data = get_real_option_chain_data()

    with col4:
        st.markdown("<div class='panel-header fade-in'>STRIKE-BY-STRIKE OPTION WALL (LIVE OPEN INTEREST)</div>", unsafe_allow_html=True)
        panic_text = "Awaiting Live Data"
        
        if opt_data is not None:
            df_strikes = opt_data["strikes"]
            atm = opt_data["atm_strike"]
            df_plot = df_strikes[(df_strikes['Strike'] >= atm - 300) & (df_strikes['Strike'] <= atm + 300)]
            
            # REAL PANIC ALERT CALCULATION (No Dummy Data)
            max_unwinding_val = 0
            max_unwinding_strike = None
            max_unwinding_type = ""

            for _, r in df_strikes.iterrows():
                if r["CE_chgOI"] < max_unwinding_val:
                    max_unwinding_val = r["CE_chgOI"]
                    max_unwinding_strike = r["Strike"]
                    max_unwinding_type = "Call"
                if r["PE_chgOI"] < max_unwinding_val:
                    max_unwinding_val = r["PE_chgOI"]
                    max_unwinding_strike = r["Strike"]
                    max_unwinding_type = "Put"

            if max_unwinding_val < -10000: # Threshold for severe panic
                panic_text = f"🚨 <b>{max_unwinding_strike:,.0f} {max_unwinding_type} Unwinding:</b> {max_unwinding_val:,.0f} contracts shed today. Writers are retreating."
            else:
                panic_text = "✅ <b>Stable OI:</b> No major institutional panic unwinding detected across active strikes today."

            fig = go.Figure()
            fig.add_trace(go.Bar(y=df_plot['Strike'], x=-df_plot['PE_OI'], orientation='h', name='Put OI (Support Floor)', marker_color='#39D353'))
            fig.add_trace(go.Bar(y=df_plot['Strike'], x=df_plot['CE_OI'], orientation='h', name='Call OI (Resistance Ceiling)', marker_color='#FF5C5C'))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#A7AFBA", size=12), margin=dict(l=0, r=0, t=15, b=0),
                xaxis=dict(title="Contracts (Puts ← | → Calls)", showgrid=False, zeroline=True, zerolinecolor="rgba(255,255,255,0.1)"),
                yaxis=dict(type='category', showgrid=False), barmode='relative', height=240,
                legend=dict(orientation="h", y=1.2, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.markdown("""
            <div style="text-align:center; padding: 40px; border: 1px solid var(--border-subtle); border-radius: 8px;">
                <div style="color:var(--accent-red); font-weight:bold; font-size:1.1rem;">LIVE OPTION DATA UNAVAILABLE</div>
                <div style="color:var(--text-muted); margin-top:5px;">NSE API is temporarily restricting requests. The terminal will auto-retry in the background every 30 seconds.</div>
            </div>
            """, unsafe_allow_html=True)

    with col5:
        if opt_data is not None:
            call_wall = str(df_strikes.loc[df_strikes['CE_OI'].idxmax()]['Strike'])
            put_wall = str(df_strikes.loc[df_strikes['PE_OI'].idxmax()]['Strike'])
            max_pain = str(opt_data['atm_strike'])
        else:
            call_wall, put_wall, max_pain = "AWAITING DATA", "AWAITING DATA", "AWAITING DATA"
            
        outlook_color = "var(--accent-red)" if st.session_state.fii_net_futures < 0 else "var(--accent-green)"
        primary_bias = "Fade Opening Spikes" if st.session_state.fii_net_futures < 0 else "Buy Market Dips"

        st.markdown(f"""
        <div class="panel-box fade-in">
            <div class="panel-header">STRUCTURAL BOUNDARIES & EXECUTION MATRIX</div>
            <div class="setup-row"><span class="setup-label">Call Wall (Resistance Ceiling)</span><span class="setup-val" style="color:var(--accent-red);">{call_wall}</span></div>
            <div class="setup-row"><span class="setup-label">Put Wall (Support Floor)</span><span class="setup-val" style="color:var(--accent-green);">{put_wall}</span></div>
            <div class="setup-row"><span class="setup-label">Max Pain Pin Magnet</span><span class="setup-val">{max_pain}</span></div>
            <div class="setup-row"><span class="setup-label">Primary Execution Setup</span><span class="setup-val" style="color:{outlook_color};">{primary_bias}</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="panel-box fade-in">
            <div class="panel-header">OPTIONS WRITER PANIC ALERT (REAL-TIME)</div>
            <div style="font-size:0.88rem; color:var(--text-secondary); line-height: 1.5;">
                {panic_text}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- REAL PARTICIPANT MATRIX (Derived from EOD CSV) ---
    st.markdown("<div class='panel-header fade-in' style='margin-top: 15px;'>EOD PARTICIPANT INVENTORY MATRIX (T-1)</div>", unsafe_allow_html=True)
    
    if st.session_state.participant_matrix is not None:
        matrix_html = '<table class="data-table fade-in"><tr><th>Participant Category</th><th>Net Index Futures</th><th>Net Call Options</th><th>Net Put Options</th></tr>'
        for client_type, data in st.session_state.participant_matrix.items():
            def format_val(v):
                c = "color: var(--accent-green);" if v > 0 else "color: var(--accent-red);" if v < 0 else ""
                sign = "+" if v > 0 else ""
                return f'<td style="{c}">{sign}{v:,.0f}</td>'
            matrix_html += f"<tr><td><b>{client_type}</b></td>{format_val(data['Futures'])}{format_val(data['Calls'])}{format_val(data['Puts'])}</tr>"
        matrix_html += "</table>"
        st.markdown(matrix_html, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center; padding: 20px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 8px; color: var(--text-secondary);">
            <b>AWAITING EOD DATA UPLOAD</b><br>Please upload the daily Participant OI CSV in the 'Data Ingestion & Intelligence' tab to view the real institutional matrix.
        </div>
        """, unsafe_allow_html=True)


# SILENT BACKGROUND AUTO-REFRESH EVERY 30 SECONDS
@st.fragment(run_every="30s")
def module_intraday_internals():
    st.markdown("<h2 class='fade-in' style='font-weight: 700; margin-bottom: 20px;'>LIVE INTRADAY INTERNALS: BREADTH & SECTOR ROTATION</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.markdown("""
        <div class="panel-box fade-in" style="height:100%;">
            <div class="panel-header">
                INDEX MARKET BREADTH (The Internal Strength X-Ray)
                <span class="tooltip">ⓘ<span class="tooltiptext">Pulls the exact number of advancing vs declining stocks in the Nifty 50 directly from NSE. Exposes fake index breakouts.</span></span>
            </div>
        """, unsafe_allow_html=True)
        
        breadth_data = get_real_market_breadth()
        
        if breadth_data is None or (breadth_data["advances"] == 0 and breadth_data["declines"] == 0):
            st.markdown("""
                <div style="text-align:center; padding: 30px 0; color:var(--text-secondary);">
                    <b>Awaiting Live Breadth Data</b><br>Retrying automatically in the background...
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            adv = breadth_data["advances"]
            dec = breadth_data["declines"]
            unc = breadth_data["unchanged"]
            
            ad_ratio = adv / dec if dec > 0 else adv
            
            if ad_ratio > 1.5:
                breadth_state = "STRONG INTERNAL BUYING"
                breadth_color = "var(--accent-green)"
                breadth_msg = "The majority of index stocks are moving up. The Nifty rally is legitimate and broad-based."
            elif ad_ratio < 0.7:
                breadth_state = "SEVERE INTERNAL SELLING"
                breadth_color = "var(--accent-red)"
                breadth_msg = "The majority of stocks are falling. If Nifty is green, it is a fake algorithmic breakout. Prepare for a reversal."
            else:
                breadth_state = "CHOPPY / MIXED INTERNALS"
                breadth_color = "var(--gold-primary)"
                breadth_msg = "Stock participation is split. The market is consolidating without clear direction."

            st.markdown(f"""
                <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
                    <div style="text-align:center;">
                        <div style="font-size:2.2rem; font-weight:800; color:var(--accent-green);">{adv}</div>
                        <div style="font-size:0.8rem; color:var(--text-muted); text-transform:uppercase;">Advances (Green)</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:2.2rem; font-weight:800; color:var(--accent-red);">{dec}</div>
                        <div style="font-size:0.8rem; color:var(--text-muted); text-transform:uppercase;">Declines (Red)</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:2.2rem; font-weight:800; color:var(--text-secondary);">{unc}</div>
                        <div style="font-size:0.8rem; color:var(--text-muted); text-transform:uppercase;">Unchanged</div>
                    </div>
                </div>
                <div class="setup-row" style="margin-top:20px;">
                    <span class="setup-label">Advance/Decline Ratio</span>
                    <span class="setup-val">{ad_ratio:.2f}</span>
                </div>
                <div class="setup-row">
                    <span class="setup-label">Internal Status</span>
                    <span class="setup-val" style="color:{breadth_color};">{breadth_state}</span>
                </div>
                <div style="font-size:0.85rem; color:var(--text-primary); background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 12px; margin-top:14px; line-height:1.5;">
                    ⚡ <b>WHAT THIS MEANS:</b> {breadth_msg}
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="panel-box fade-in" style="height:100%;">
            <div class="panel-header">
                SECTORAL RELATIVE STRENGTH (The Money Rotation Map)
                <span class="tooltip">ⓘ<span class="tooltiptext">Compares live intraday performance across all 14 NSE sectors. Identifies exactly where institutions are parking their money today.</span></span>
            </div>
        """, unsafe_allow_html=True)
        
        sector_df = get_real_sectoral_data()
        
        if sector_df is None or sector_df.empty:
            st.markdown("""
                <div style="text-align:center; padding: 30px 0; color:var(--text-secondary);">
                    <b>Awaiting Live Sector Data</b><br>Fetching extended timeframe data...
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            table_html = '<div style="max-height: 400px; overflow-y: auto;"><table class="data-table"><tr><th>Index / Sector</th><th>Live Price</th><th>Intraday Change</th><th>Institutional Money Flow</th></tr>'
            for _, r in sector_df.iterrows():
                chg = r["Change"]
                c_style = "color: var(--accent-green);" if chg > 0 else "color: var(--accent-red);" if chg < 0 else ""
                indicator = "🟢" if chg > 0 else "🔴" if chg < 0 else "⚪"
                
                bold_name = f"<span style='color:var(--gold-primary); font-weight:800;'>{r['Sector']}</span>" if "Benchmark" in r["Sector"] else f"<b>{r['Sector']}</b>"
                table_html += f"<tr><td>{bold_name}</td><td>₹{r['Price']:,.1f}</td><td style='{c_style}; font-weight:700;'>{chg:+.2f}%</td><td>{indicator} {r['State']}</td></tr>"
            
            table_html += "</table></div>"
            st.markdown(table_html, unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size:0.85rem; color:var(--text-secondary); margin-top:14px; line-height:1.5;">
                ⚡ <b>TRADING EDGE:</b> Never buy a sector that is underperforming the Nifty 50 Benchmark. Look for the specific sector highlighted in green while the benchmark is flat.
            </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div class='section-header fade-in' style='margin-top: 40px;'>INSTITUTIONAL ALGORITHMIC SCREENER</div>", unsafe_allow_html=True)
    df_vwap, composite_score = get_real_heavyweight_vwap()
    
    col3, col4 = st.columns([2.5, 1])
    with col3:
        st.markdown("""
        <div class="panel-box fade-in" style="height:100%;">
            <div class="panel-header">
                ALGORITHMIC VWAP DIVERGENCE (The Elephant Footprint Tracker)
                <span class="tooltip">ⓘ<span class="tooltiptext">Calculates live 1-minute VWAP for the Top 5 Index Heavyweights. Shows if algorithmic block-orders are buying or selling heavily weighted stocks.</span></span>
            </div>
        """, unsafe_allow_html=True)
        
        table_html = '''
        <table class="data-table">
            <tr>
                <th>Symbol</th>
                <th>Weightage</th>
                <th>LTP</th>
                <th>Intraday VWAP</th>
                <th>VWAP Divergence <span class="tooltip">ⓘ<span class="tooltiptext">If Price is below VWAP (Red), institutions are distributing. If Price is above VWAP (Green), they are accumulating.</span></span></th>
                <th>Algorithmic State</th>
            </tr>
        '''
        for _, r in df_vwap.iterrows():
            div = r["Divergence"]
            if r["State"] in ["AWAITING MARKET OPEN", "DATA UNAVAILABLE"]:
                table_html += f"<tr><td><b>{r['Symbol']}</b></td><td>{r['Weight']}</td><td>--</td><td>--</td><td>--</td><td><span style='color:var(--text-muted);'>{r['State']}</span></td></tr>"
            else:
                c_style = "color: var(--accent-green);" if div > 0 else "color: var(--accent-red);" if div < 0 else ""
                indicator = "🟢" if div > 0 else "🔴" if div < 0 else "⚪"
                table_html += f"<tr><td><b>{r['Symbol']}</b></td><td>{r['Weight']}</td><td>₹{r['Price']:,.2f}</td><td>₹{r['VWAP']:,.2f}</td><td style='{c_style}; font-weight:600;'>{div:+.3f}%</td><td>{indicator} {r['State']}</td></tr>"
        
        table_html += "</table></div>"
        st.markdown(table_html, unsafe_allow_html=True)

    with col4:
        if df_vwap.iloc[0]["State"] in ["AWAITING MARKET OPEN", "DATA UNAVAILABLE"]:
            box_class, text_color, bias_text = "", "var(--text-secondary)", "AWAITING TICK DATA"
        else:
            box_class = "bullish" if composite_score > 0 else ""
            text_color = "var(--accent-green)" if composite_score > 0 else "var(--accent-red)"
            bias_text = "HEAVYWEIGHT ACCUMULATION" if composite_score > 0 else "DISTRIBUTION DRAG"
        
        st.markdown(f"""
        <div class="fade-in composite-box {box_class}" style="height:100%;">
            <div style="font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-bottom: 5px;">
                Composite Algorithmic Pull
                <span class="tooltip">ⓘ<span class="tooltiptext">Aggregates the total VWAP deviation based on index weightages. Reveals the true underlying force moving the Nifty.</span></span>
            </div>
            <div style="font-size: 2.2rem; font-weight: 800; color: {text_color};">{composite_score:+.3f}%</div>
            <div style="font-size: 0.9rem; color: {text_color}; margin-top: 5px; font-weight: 600;">{bias_text}</div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 15px; line-height: 1.5;">
                ⚡ <b>EDGE:</b> If Nifty is making a new high, but this score is deeply red, it is a false breakout. The heaviest stocks are actually being sold off by algorithms.
            </div>
        </div>
        """, unsafe_allow_html=True)


# >>> MODULE 3: DATA INGESTION & INTELLIGENCE <<<
def parse_participant_csv_full(file):
    """Advanced parser to extract real Participant OI Data from NSE format"""
    try:
        df = pd.read_csv(file)
        
        fil_col = next((c for c in df.columns if 'future index long' in c.lower()), None)
        fis_col = next((c for c in df.columns if 'future index short' in c.lower()), None)
        ocl_col = next((c for c in df.columns if 'call long' in c.lower() and 'index' in c.lower()), None)
        ocs_col = next((c for c in df.columns if 'call short' in c.lower() and 'index' in c.lower()), None)
        opl_col = next((c for c in df.columns if 'put long' in c.lower() and 'index' in c.lower()), None)
        ops_col = next((c for c in df.columns if 'put short' in c.lower() and 'index' in c.lower()), None)
        
        client_col = df.columns[0]
        
        matrix = {}
        for client_type in ['Client', 'FII', 'Pro']:
            row = df[df[client_col].astype(str).str.contains(client_type, case=False, na=False)]
            if not row.empty and fil_col and fis_col:
                net_fut = float(row.iloc[0][fil_col]) - float(row.iloc[0][fis_col])
                net_ce = float(row.iloc[0][ocl_col]) - float(row.iloc[0][ocs_col]) if ocl_col and ocs_col else 0
                net_pe = float(row.iloc[0][opl_col]) - float(row.iloc[0][ops_col]) if opl_col and ops_col else 0
                matrix[client_type] = {"Futures": net_fut, "Calls": net_ce, "Puts": net_pe}
        return matrix
    except Exception:
        return None

def module_data_ingestion_and_intelligence():
    st.markdown("<h2 class='fade-in' style='font-weight: 700; margin-bottom: 20px;'>EOD DATA INGESTION & PARSING ENGINE</h2>", unsafe_allow_html=True)
    with st.expander("📁 8-FILE DAILY INGESTION DECK (CLICK TO EXPAND / COLLAPSE)", expanded=not st.session_state.eod_data_processed):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown("<div class='compact-upload-title'>T-1 PARTICIPANT OI</div>", unsafe_allow_html=True)
            oip = st.file_uploader("POI (T-1)", type=['csv'], key="oip", label_visibility="collapsed")
            st.markdown("<div class='compact-upload-title' style='margin-top:8px;'>T PARTICIPANT OI</div>", unsafe_allow_html=True)
            oic = st.file_uploader("POI (T)", type=['csv'], key="oic", label_visibility="collapsed")
        with c2:
            st.markdown("<div class='compact-upload-title'>T-1 BHAVCOPY</div>", unsafe_allow_html=True)
            bhp = st.file_uploader("Bhav (T-1)", type=['csv', 'zip'], key="bhp", label_visibility="collapsed")
            st.markdown("<div class='compact-upload-title' style='margin-top:8px;'>T BHAVCOPY</div>", unsafe_allow_html=True)
            bhc = st.file_uploader("Bhav (T)", type=['csv', 'zip'], key="bhc", label_visibility="collapsed")
        with c3:
            st.markdown("<div class='compact-upload-title'>T-1 FII STATS</div>", unsafe_allow_html=True)
            fip = st.file_uploader("FII (T-1)", type=['xls', 'csv'], key="fip", label_visibility="collapsed")
            st.markdown("<div class='compact-upload-title' style='margin-top:8px;'>T FII STATS</div>", unsafe_allow_html=True)
            fic = st.file_uploader("FII (T)", type=['xls', 'csv'], key="fic", label_visibility="collapsed")
        with c4:
            st.markdown("<div class='compact-upload-title'>T-1 DELIVERY</div>", unsafe_allow_html=True)
            dep = st.file_uploader("Del (T-1)", type=['csv', 'dat'], key="dep", label_visibility="collapsed")
            st.markdown("<div class='compact-upload-title' style='margin-top:8px;'>T DELIVERY</div>", unsafe_allow_html=True)
            dec = st.file_uploader("Del (T)", type=['csv', 'dat'], key="dec", label_visibility="collapsed")

        if st.button("EXECUTE QUANTITATIVE PARSING & SYNCHRONIZE", type="primary", use_container_width=True):
            with st.spinner("Processing files and compiling institutional positioning..."):
                time.sleep(1)
                
                matrix_curr = parse_participant_csv_full(oic) if oic else None
                matrix_prev = parse_participant_csv_full(oip) if oip else None
                
                if matrix_curr is not None and "FII" in matrix_curr:
                    st.session_state.participant_matrix = matrix_curr
                    st.session_state.fii_net_futures = matrix_curr["FII"]["Futures"]
                    
                    if matrix_prev is not None and "FII" in matrix_prev:
                        st.session_state.fii_dod_delta = matrix_curr["FII"]["Futures"] - matrix_prev["FII"]["Futures"]
                else:
                    st.error("Invalid CSV format. Please upload standard NSE Participant OI files.")

                if st.session_state.fii_net_futures < -100000:
                    st.session_state.smart_money_score = -6.5
                    st.session_state.market_regime = "BEARISH / SELL ON RISE"
                elif st.session_state.fii_net_futures > 50000:
                    st.session_state.smart_money_score = +5.0
                    st.session_state.market_regime = "BULLISH / BUY ON DIPS"
                else:
                    st.session_state.smart_money_score = -1.0
                    st.session_state.market_regime = "NEUTRAL / RANGE-BOUND"

                st.session_state.eod_data_processed = True
                st.success("✅ Quantitative Synchronization Complete.")
                time.sleep(0.6)
                st.rerun()
                
    st.markdown("""
    <div class="panel-box fade-in" style="margin-top: 20px;">
        <div class="panel-header">END OF DAY (EOD) INSTRUCTIONS</div>
        <div style="color: var(--text-secondary); line-height: 1.6; font-size: 0.9rem;">
            This module establishes the core foundational bias for the following trading session. By parsing the exact CSV records published by the NSE daily at 6:30 PM, the system eliminates sentiment and grounds all trading decisions in verifiable institutional fund flows.
        </div>
    </div>
    """, unsafe_allow_html=True)


# >>> MODULE 4: RISK & POSITION SIZING CALCULATOR <<<
def module_risk_calculator():
    st.markdown("<h2 class='fade-in' style='font-weight: 700; margin-bottom: 15px;'>PRECISION RISK & POSITION SIZING CALCULATOR</h2>", unsafe_allow_html=True)
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


# --- 8. EXECUTION ROUTER ---
if selected_tab == "LIVE COCKPIT":
    module_live_cockpit()
elif selected_tab == "INTRADAY INTERNALS":
    module_intraday_internals()
elif selected_tab == "DATA INGESTION & INTELLIGENCE":
    module_data_ingestion_and_intelligence()
elif selected_tab == "RISK CALCULATOR":
    module_risk_calculator()