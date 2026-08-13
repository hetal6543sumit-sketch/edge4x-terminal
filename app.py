import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import sqlite3
import hashlib

# --- 1. PAGE ARCHITECTURE & CORE CONFIGURATION ---
st.set_page_config(
    page_title="EDGE4X | Institutional Terminal", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- 2. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('edge4x.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT,
            status TEXT
        )
    ''')
    # Create default admin if it doesn't exist
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = hashlib.sha256(b'admin123').hexdigest()
        c.execute("INSERT INTO users VALUES ('admin', ?, 'admin', 'approved')", (hashed_pw,))
    conn.commit()
    conn.close()

init_db()

# --- 3. STATE MANAGEMENT & SECRET ADMIN BYPASS ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.status = ""

if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
if 'df_flow_today' not in st.session_state:
    st.session_state.df_flow_today = pd.DataFrame()
if 'df_flow_prev' not in st.session_state:
    st.session_state.df_flow_prev = pd.DataFrame()

# 👑 THE SECRET ADMIN LINK LOGIC 👑
if "admin_key" in st.query_params:
    if st.query_params["admin_key"] == "edge4x_master":
        st.session_state.logged_in = True
        st.session_state.username = "admin"
        st.session_state.role = "admin"
        st.session_state.status = "approved"
        
        # Erase the secret key from the URL instantly so no one sees it!
        del st.query_params["admin_key"]
        st.rerun()


# --- 4. MASTER CSS: GRAPHITE & GOLD THEME ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    :root {
        --bg-base: #0A0D14;
        --bg-surface: #141A26;
        --border-subtle: rgba(255, 255, 255, 0.1);
        --gold-primary: #E5C158;
        --gold-muted: #B8892D;
        --text-primary: #FFFFFF;
        --text-muted: #A0ABB8;
        --status-red: #FF5C5C;
        --status-green: #39D353;
    }

    html, body, [class*="css"], .stApp {
        font-family: 'Inter', sans-serif !important;
        color: var(--text-primary) !important;
        font-variant-numeric: tabular-nums;
        font-size: 16px; 
    }
    
    .stApp {
        background: linear-gradient(-45deg, #0A0D14, #101520, #0A0D14, #080A0F) !important;
        background-size: 400% 400% !important;
        animation: subtleGlow 20s ease infinite !important;
    }
    @keyframes subtleGlow {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    [data-testid="stSidebar"] { display: none !important; }
    #MainMenu, header, footer {visibility: hidden;}
    .block-container {
        padding-top: 90px !important;
        padding-bottom: 30px !important;
        max-width: 1600px;
    }

    .terminal-nav {
        position: fixed;
        top: 0; left: 0; right: 0;
        height: 65px;
        background: rgba(10, 13, 20, 0.90);
        backdrop-filter: blur(16px);
        border-bottom: 1px solid var(--border-subtle);
        z-index: 999999;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 40px;
    }
    .nav-brand {
        font-weight: 800;
        letter-spacing: 2px;
        color: var(--text-primary);
        font-size: 1.4rem;
    }
    .nav-brand span { color: var(--gold-primary); }
    .nav-status {
        display: flex;
        align-items: center;
        gap: 25px;
        color: var(--text-muted);
        font-weight: 600;
        font-size: 0.9rem;
    }
    .live-dot {
        height: 8px; width: 8px;
        background-color: var(--status-green);
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        box-shadow: 0 0 10px var(--status-green);
    }

    div[role="radiogroup"] {
        display: flex !important;
        flex-direction: row !important;
        justify-content: center !important;
        gap: 15px !important;
        background: var(--bg-surface) !important;
        padding: 10px 20px !important;
        border-radius: 10px !important;
        border: 1px solid var(--border-subtle) !important;
        margin-bottom: 35px !important;
    }
    div[role="radiogroup"] label {
        background: transparent !important;
        border: none !important;
        color: var(--text-muted) !important;
        padding: 10px 18px !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        letter-spacing: 1px !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
        cursor: pointer;
    }
    div[role="radiogroup"] label:hover {
        color: var(--text-primary) !important;
        background: rgba(255, 255, 255, 0.05) !important;
    }
    div[role="radiogroup"] label[data-checked="true"] {
        color: #0A0D14 !important;
        background: var(--gold-primary) !important;
        box-shadow: 0 4px 15px rgba(229, 193, 88, 0.2) !important;
    }

    .auth-box {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 40px;
        max-width: 450px;
        margin: 50px auto;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    
    .fade-in-up {
        animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        opacity: 0;
        transform: translateY(15px);
    }
    @keyframes fadeInUp {
        to { opacity: 1; transform: translateY(0); }
    }

    .metric-strip { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; background: var(--bg-surface); padding: 25px; border-radius: 12px; border: 1px solid var(--border-subtle); }
    .metric-card { flex: 1 1 180px; border-left: 3px solid var(--border-subtle); padding-left: 20px; }
    .metric-label { font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px; font-weight: 600; }
    .metric-value { font-size: 1.8rem; font-weight: 800; color: var(--text-primary); white-space: nowrap; }
    .metric-value.gold { color: var(--gold-primary); }

    .regime-box { border: 1px solid var(--border-subtle); background: var(--bg-surface); padding: 25px; border-radius: 12px; margin-bottom: 25px; }
    .plain-english-card { background: linear-gradient(135deg, rgba(229, 193, 88, 0.08), rgba(20, 26, 38, 0.9)); border: 1px solid rgba(229, 193, 88, 0.3); border-radius: 12px; padding: 25px; margin-bottom: 30px; }
    .plain-title { color: var(--gold-primary); font-size: 1.1rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
    .plain-body { font-size: 1.05rem; color: #E2E8F0; line-height: 1.6; }
    
    .setup-row { display: flex; justify-content: space-between; margin-bottom: 14px; font-size: 1.05rem; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 10px; }
    .setup-row .label { color: var(--text-muted); font-weight: 600; }
    .setup-row .val { font-weight: 800; }
    
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 1.05rem; background: var(--bg-surface); border-radius: 12px; overflow: hidden; }
    .matrix-table th { text-align: left; padding: 18px; color: var(--gold-primary); border-bottom: 1px solid var(--border-subtle); font-weight: 700; text-transform: uppercase; }
    .matrix-table td { padding: 18px; border-bottom: 1px solid rgba(255,255,255,0.03); font-weight: 500; }
    .val-pos { color: var(--status-green); }
    .val-neg { color: var(--status-red); }
    
    .upload-zone { background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
    .upload-section-title { font-size: 1.1rem; font-weight: 800; color: var(--gold-primary); margin-bottom: 15px; text-transform: uppercase; border-bottom: 2px solid var(--border-subtle); padding-bottom: 8px; }
</style>

<div class="terminal-nav">
    <div class="nav-brand">EDGE<span>4X</span></div>
    <div class="nav-status">
        <span>NIFTY 50: 24,385.40</span>
        <span>MARKET CLOSED</span>
    </div>
</div>
""", unsafe_allow_html=True)

def style_plotly_fig(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#A0ABB8", size=13), margin=dict(l=0, r=0, t=30, b=0), xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False))
    return fig

# --- 5. AUTHENTICATION LOGIC & UI ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def auth_screen():
    st.markdown("<div class='auth-box'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#E5C158; font-weight:800; letter-spacing:2px;'>TERMINAL ACCESS</h2>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Sign In", "Request Access"])
    
    with tab1:
        st.markdown("<br>", unsafe_allow_html=True)
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        
        if st.button("AUTHENTICATE", type="primary", use_container_width=True):
            conn = sqlite3.connect('edge4x.db')
            c = conn.cursor()
            c.execute("SELECT password, role, status FROM users WHERE username=?", (login_user,))
            result = c.fetchone()
            conn.close()
            
            if result and result[0] == hash_password(login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.session_state.role = result[1]
                st.session_state.status = result[2]
                st.rerun()
            else:
                st.error("Invalid credentials.")
                
    with tab2:
        st.markdown("<br>", unsafe_allow_html=True)
        reg_user = st.text_input("Choose Username", key="reg_user")
        reg_pass = st.text_input("Choose Password", type="password", key="reg_pass")
        
        if st.button("SUBMIT REQUEST", type="primary", use_container_width=True):
            if reg_user and reg_pass:
                conn = sqlite3.connect('edge4x.db')
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=?", (reg_user,))
                if c.fetchone():
                    st.error("Username already exists.")
                else:
                    c.execute("INSERT INTO users VALUES (?, ?, 'user', 'pending')", (reg_user, hash_password(reg_pass)))
                    conn.commit()
                    st.success("Request submitted! Please wait for admin approval.")
                conn.close()
            else:
                st.warning("Please fill out all fields.")
    st.markdown("</div>", unsafe_allow_html=True)

# --- 6. ADMIN DASHBOARD ---
def module_admin():
    st.markdown("<h2 style='font-weight: 800; color: #FFFFFF;'>ADMINISTRATOR CONSOLE</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #A0ABB8;'>Approve, revoke, or permanently remove user access.</p><hr>", unsafe_allow_html=True)
    
    conn = sqlite3.connect('edge4x.db')
    c = conn.cursor()
    c.execute("SELECT username, status FROM users WHERE role='user'")
    users = c.fetchall()
    
    if not users:
        st.info("No traders found in the database.")
    else:
        for u in users:
            col1, col2, col3 = st.columns([3, 1.5, 1.5])
            col1.markdown(f"**Trader ID:** `{u[0]}` | **Status:** `{u[1].upper()}`")
            
            if u[1] == 'pending':
                if col2.button("APPROVE", key=f"app_{u[0]}", type="primary"):
                    c.execute("UPDATE users SET status='approved' WHERE username=?", (u[0],))
                    conn.commit()
                    st.rerun()
                if col3.button("REJECT (DELETE)", key=f"rej_{u[0]}"):
                    c.execute("DELETE FROM users WHERE username=?", (u[0],))
                    conn.commit()
                    st.rerun()
            elif u[1] == 'approved':
                if col2.button("REVOKE ACCESS", key=f"rev_{u[0]}"):
                    c.execute("UPDATE users SET status='pending' WHERE username=?", (u[0],))
                    conn.commit()
                    st.rerun()
                if col3.button("REMOVE USER", key=f"del_{u[0]}"):
                    c.execute("DELETE FROM users WHERE username=?", (u[0],))
                    conn.commit()
                    st.rerun()
    conn.close()

# --- 7. TERMINAL MODULES (DATA) ---
def module_data_center():
    st.markdown("<h2 style='font-weight: 800; color: #FFFFFF;'>MULTI-DAY 8-FILE DATA INGESTION</h2>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='upload-section-title'>⬅️ PREVIOUS DAY (T-1)</div>", unsafe_allow_html=True)
        st.markdown("<div class='upload-zone'>", unsafe_allow_html=True)
        st.file_uploader("1. Participant OI (Prev)", type=['csv'], key="oip")
        st.file_uploader("2. Bhavcopy (Prev)", type=['csv'], key="bhp")
        st.file_uploader("3. FII Stats (Prev)", type=['xls','csv'], key="fip")
        st.file_uploader("4. Delivery (Prev)", type=['csv','dat'], key="dep")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='upload-section-title'>➡️ CURRENT DAY (T)</div>", unsafe_allow_html=True)
        st.markdown("<div class='upload-zone'>", unsafe_allow_html=True)
        st.file_uploader("1. Participant OI (Curr)", type=['csv'], key="oic")
        st.file_uploader("2. Bhavcopy (Curr)", type=['csv'], key="bhc")
        st.file_uploader("3. FII Stats (Curr)", type=['xls','csv'], key="fic")
        st.file_uploader("4. Delivery (Curr)", type=['csv','dat'], key="dec")
        st.markdown("</div>", unsafe_allow_html=True)

    if st.button("PROCESS ALL 8 FILES", type="primary", use_container_width=True):
        with st.spinner("Parsing data..."):
            time.sleep(1.5)
            st.session_state.data_processed = True
            st.success("✅ Engine unlocked!")
            time.sleep(1)
            st.rerun()

def module_overview():
    st.markdown("""
    <div class="plain-english-card fade-in-up">
        <div class="plain-title">📌 PLAIN-ENGLISH TRADING SUMMARY</div>
        <div class="plain-body">
            <b>🐻 Market Mood: Bearish</b> (Sellers are in total control).<br>
            <b>🚨 The Trap:</b> Retail traders are stubbornly buying dips, while institutions build massive short positions.<br>
            <b>💡 Tomorrow's Plan:</b> Avoid buying. Look for morning green candles near resistance to short.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div class="metric-strip fade-in-up">
        <div class="metric-card"><div class="metric-label">Market Bias</div><div class="metric-value gold">BEARISH</div></div>
        <div class="metric-card"><div class="metric-label">Smart Money Trend</div><div class="metric-value" style="color: #FF5C5C;">SHORT HEAVY</div></div>
        <div class="metric-card"><div class="metric-label">Max Pain</div><div class="metric-value">24,400</div></div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1.6, 1])
    
    with col1:
        st.markdown("""
        <div class="regime-box fade-in-up">
            <div class="regime-eyebrow">KEY LEVEL BREAKDOWN</div>
            <div class="regime-title">SELL ON RISING BOUNCES</div>
            <div class="regime-sub">Big players expanded their short positions to -168,702 contracts. Any morning rally will face heavy selling pressure.</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="regime-box fade-in-up">
            <div style="font-size: 1.1rem; color: var(--gold-primary); letter-spacing: 2px; margin-bottom: 25px; font-weight: 800; text-transform: uppercase;">TOMORROW'S TRADE SETUP</div>
            <div class="setup-row"><span class="label">SUGGESTED ENTRY</span><span class="val">24,430 — 24,480</span></div>
            <div class="setup-row"><span class="label">STOP LOSS (DO NOT CROSS)</span><span class="val">24,530</span></div>
            <div class="setup-row" style="border:none;"><span class="label">EXPECTED TARGET</span><span class="val" style="color:var(--gold-primary); font-size: 1.3rem;">24,300</span></div>
        </div>
        """, unsafe_allow_html=True)

def module_flow():
    st.markdown("<h3 style='font-weight:800; color: #FFFFFF;'>CURRENT SESSION FLOW MATRIX</h3>", unsafe_allow_html=True)
    matrix_html = '<table class="matrix-table fade-in-up"><tr><th>Participant Group</th><th>Index Futures</th><th>Calls</th><th>Puts</th></tr>'
    df_today = pd.DataFrame({
        "P": ["Client (Retail)", "FIIs (Big Money)", "Pro Desks"],
        "IF": ["+4,487 (Buying)", "-3,533 (Selling)", "-958 (Selling)"],
        "C": ["+46,584 (Buying)", "-57,902 (Writing)", "+11,298 (Buying)"],
        "P_": ["-88,580 (Short)", "-25,621 (Selling)", "-62,735 (Selling)"]
    })
    for _, row in df_today.iterrows():
        def format_val(v):
            c = "val-pos" if "Buy" in v or v.startswith('+') else "val-neg" if "Sell" in v or "Short" in v or "Writ" in v else ""
            return f'<td class="{c}">{v}</td>'
        matrix_html += f"<tr><td><b>{row['P']}</b></td>{format_val(row['IF'])}{format_val(row['C'])}{format_val(row['P_'])}</tr>"
    matrix_html += "</table>"
    st.markdown(matrix_html, unsafe_allow_html=True)

def module_trend_analysis():
    st.markdown("<h2 style='font-weight: 800; color: #FFFFFF;'>DAY-OVER-DAY MOMENTUM</h2>", unsafe_allow_html=True)
    fig = go.Figure(data=[
        go.Bar(name='Yesterday (T-1)', x=['FII Futures', 'Retail Calls'], y=[-165150, 148000], marker_color='#A0ABB8'),
        go.Bar(name='Today (T)', x=['FII Futures', 'Retail Calls'], y=[-168702, 194584], marker_color='#E5C158')
    ])
    fig.update_layout(barmode='group', height=350)
    st.plotly_chart(style_plotly_fig(fig), use_container_width=True, config={'displayModeBar': False})

# --- 8. GATEKEEPER & ROUTING EXECUTION ---
if not st.session_state.logged_in:
    auth_screen()
elif st.session_state.status == 'pending':
    st.markdown("<div class='auth-box'>", unsafe_allow_html=True)
    st.warning("⏳ Your account is pending approval by the Administrator. Please check back later.")
    if st.button("Sign Out"):
        st.session_state.logged_in = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
else:
    menu_items = ["DATA INGESTION", "OVERVIEW", "MARKET FLOW", "TREND ANALYSIS"]
    if st.session_state.role == 'admin':
        menu_items.insert(0, "👑 ADMIN DASHBOARD")
    
    col1, col2 = st.columns([9, 1])
    with col1:
        # Create the top horizontal navigation pills
        selected_module = st.radio("", menu_items, horizontal=True, label_visibility="collapsed")
    with col2:
        if st.button("Sign Out", type="secondary"):
            st.session_state.logged_in = False
            st.rerun()

    st.markdown("---")

    if selected_module == "👑 ADMIN DASHBOARD":
        module_admin()
    elif selected_module == "DATA INGESTION":
        module_data_center()
    else:
        if not st.session_state.data_processed and st.session_state.role != 'admin':
            st.error("Engine Locked. Awaiting Data Ingestion.")
        elif not st.session_state.data_processed and st.session_state.role == 'admin':
            st.warning("⚠️ Admin Alert: The terminal requires data ingestion before analysis modules populate.")
        else:
            if selected_module == "OVERVIEW":
                module_overview()
            elif selected_module == "MARKET FLOW":
                module_flow()
            elif selected_module == "TREND ANALYSIS":
                module_trend_analysis()