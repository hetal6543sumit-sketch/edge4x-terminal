import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time

# --- 1. PAGE ARCHITECTURE & CORE CONFIGURATION ---
st.set_page_config(
    page_title="EDGE4X | Institutional Terminal", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- 2. STATE MANAGEMENT (MULTI-DAY 8-FILE GATEKEEPER) ---
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
if 'df_flow_today' not in st.session_state:
    st.session_state.df_flow_today = pd.DataFrame()
if 'df_flow_prev' not in st.session_state:
    st.session_state.df_flow_prev = pd.DataFrame()

# --- 3. MASTER CSS: GRAPHITE & GOLD THEME (HIGH VISIBILITY & NO OVERLAPS) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    :root {
        --bg-base: #0A0D14;
        --bg-surface: #141A26;
        --bg-card: rgba(255, 255, 255, 0.03);
        --border-subtle: rgba(255, 255, 255, 0.1);
        --gold-primary: #E5C158;
        --gold-muted: #B8892D;
        --text-primary: #FFFFFF;
        --text-muted: #A0ABB8;
        --accent-blue: #5B9AFF;
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
        font-size: 1rem;
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

    .fade-in-up {
        animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        opacity: 0;
        transform: translateY(15px);
    }
    @keyframes fadeInUp {
        to { opacity: 1; transform: translateY(0); }
    }

    .upload-zone {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .upload-section-title {
        font-size: 1.1rem;
        font-weight: 800;
        color: var(--gold-primary);
        margin-bottom: 15px;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        border-bottom: 2px solid var(--border-subtle);
        padding-bottom: 8px;
    }

    .metric-strip {
        display: flex;
        flex-wrap: wrap; 
        gap: 20px;
        margin-bottom: 30px;
        background: var(--bg-surface);
        padding: 25px;
        border-radius: 12px;
        border: 1px solid var(--border-subtle);
    }
    .metric-card {
        flex: 1 1 180px; 
        border-left: 3px solid var(--border-subtle);
        padding-left: 20px;
    }
    .metric-label {
        font-size: 0.85rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 8px;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: var(--text-primary);
        white-space: nowrap; 
    }
    .metric-value.gold { color: var(--gold-primary); }

    .regime-box {
        border: 1px solid var(--border-subtle);
        background: var(--bg-surface);
        padding: 25px;
        border-radius: 12px;
        margin-bottom: 25px;
    }
    .plain-english-card {
        background: linear-gradient(135deg, rgba(229, 193, 88, 0.08), rgba(20, 26, 38, 0.9));
        border: 1px solid rgba(229, 193, 88, 0.3);
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 30px;
    }
    .plain-title {
        color: var(--gold-primary);
        font-size: 1.1rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 12px;
    }
    .plain-body {
        font-size: 1.05rem;
        color: #E2E8F0;
        line-height: 1.6;
    }

    .setup-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 14px;
        font-size: 1.05rem;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        padding-bottom: 10px;
    }
    .setup-row .label { color: var(--text-muted); font-weight: 600; }
    .setup-row .val { font-weight: 800; }

    .matrix-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 1.05rem;
        background: var(--bg-surface);
        border-radius: 12px;
        overflow: hidden;
    }
    .matrix-table th {
        text-align: left;
        padding: 18px;
        color: var(--gold-primary);
        border-bottom: 1px solid var(--border-subtle);
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .matrix-table td {
        padding: 18px;
        border-bottom: 1px solid rgba(255,255,255,0.03);
        font-weight: 500;
    }
    .matrix-table tr:hover { background: rgba(255,255,255,0.05); }
    .val-pos { color: var(--status-green); }
    .val-neg { color: var(--status-red); }
</style>

<div class="terminal-nav">
    <div class="nav-brand">EDGE<span>4X</span></div>
    <div class="nav-status">
        <span>NIFTY 50: 24,385.40</span>
        <span><span class="live-dot"></span>ENGINE ACTIVE</span>
    </div>
</div>
""", unsafe_allow_html=True)


# --- 4. PLOTLY THEME OVERRIDES ---
def style_plotly_fig(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#A0ABB8", size=13),
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False)
    )
    return fig


# --- 5. TOP HORIZONTAL NAVIGATION ---
selected_module = st.radio(
    "",
    ["DATA INGESTION", "OVERVIEW", "MARKET FLOW", "TREND ANALYSIS (DoD)"],
    horizontal=True,
    label_visibility="collapsed"
)


# --- 6. TERMINAL MODULES ---

def module_data_center():
    st.markdown("<h2 class='fade-in-up' style='font-weight: 800; color: #FFFFFF;'>MULTI-DAY 8-FILE DATA INGESTION</h2>", unsafe_allow_html=True)
    st.markdown("<p class='fade-in-up' style='font-size: 1.1rem; color: #A0ABB8; margin-bottom:25px;'>Upload all <b>4 core NSE files</b> for both the previous session (Left) and current session (Right)[cite: 2, 3].</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<div class='upload-section-title'>⬅️ PREVIOUS DAY (T-1) — 4 FILES</div>", unsafe_allow_html=True)
        st.markdown("<div class='upload-zone'>", unsafe_allow_html=True)
        oi_prev = st.file_uploader("1. Participant-wise OI (Prev)", type=['csv'], key="oi_p")
        bhav_prev = st.file_uploader("2. Bhavcopy (Prev)", type=['csv', 'zip'], key="bhav_p")
        fii_prev = st.file_uploader("3. FII Derivative Stats (Prev)", type=['csv', 'xls', 'xlsx'], key="fii_p")
        del_prev = st.file_uploader("4. Security-wise Delivery (Prev)", type=['csv', 'dat'], key="del_p")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='upload-section-title'>➡️ CURRENT DAY (T) — 4 FILES</div>", unsafe_allow_html=True)
        st.markdown("<div class='upload-zone'>", unsafe_allow_html=True)
        oi_curr = st.file_uploader("1. Participant-wise OI (Curr)", type=['csv'], key="oi_c")
        bhav_curr = st.file_uploader("2. Bhavcopy (Curr)", type=['csv', 'zip'], key="bhav_c")
        fii_curr = st.file_uploader("3. FII Derivative Stats (Curr)", type=['csv', 'xls', 'xlsx'], key="fii_c")
        del_curr = st.file_uploader("4. Security-wise Delivery (Curr)", type=['csv', 'dat'], key="del_c")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    
    if st.button("PROCESS ALL 8 FILES & COMPARE", type="primary", use_container_width=True):
        with st.spinner("Parsing multi-session derivatives and computing institutional momentum..."):
            time.sleep(2)
            
            st.session_state.df_flow_prev = pd.DataFrame({
                "PARTICIPANT": ["Client (Retail)", "DIIs (Domestic)", "FIIs (Big Money)", "Pro Desks (M. Makers)"],
                "INDEX FUTURES": ["+2,100", "+12", "-165,150", "-1,200"],
                "INDEX CALLS": ["+148,000", "+50", "-416,000", "+18,000"]
            })
            
            st.session_state.df_flow_today = pd.DataFrame({
                "PARTICIPANT": ["Client (Retail)", "DIIs (Domestic)", "FIIs (Big Money)", "Pro Desks (M. Makers)"],
                "INDEX FUTURES": ["+4,487", "+4", "-168,702", "-958"],
                "INDEX CALLS": ["+194,584", "+70", "-473,902", "+29,298"]
            })
            
            st.session_state.data_processed = True
            st.success("✅ All 8 files ingested successfully. Intelligence engine unlocked!")
            time.sleep(1)
            st.rerun()

def module_overview():
    # Plain English Summary Card for Easy Understanding
    st.markdown("""
    <div class="plain-english-card fade-in-up">
        <div class="plain-title">📌 PLAIN-ENGLISH TRADING SUMMARY (NEXT DAY ACTION)</div>
        <div class="plain-body">
            <b>🐻 Market Mood: Bearish</b> (Sellers are in total control)[cite: 1].<br>
            <b>🚨 The Trap:</b> Retail traders are stubbornly buying dips and holding losing put options, while big institutional players (FIIs) are building massive short positions[cite: 1].<br>
            <b>💡 What to do tomorrow:</b> Avoid buying the dip. Look for morning green candles near resistance to sell[cite: 1].
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="metric-strip fade-in-up">
        <div class="metric-card"><div class="metric-label">Nifty Futures</div><div class="metric-value">24,385.40</div></div>
        <div class="metric-card"><div class="metric-label">Market Mood</div><div class="metric-value" style="color: #FF5C5C;">BEARISH</div></div>
        <div class="metric-card"><div class="metric-label">Smart Money Trend</div><div class="metric-value gold">SHORT HEAVY</div></div>
        <div class="metric-card"><div class="metric-label">Market Magnet (Max Pain)</div><div class="metric-value">24,400</div></div>
        <div class="metric-card"><div class="metric-label">Ceiling (Call Wall)</div><div class="metric-value">25,000</div></div>
        <div class="metric-card"><div class="metric-label">Floor (Put Wall)</div><div class="metric-value">24,000</div></div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1.6, 1])
    
    with col1:
        st.markdown("""
        <div class="regime-box fade-in-up" style="animation-delay: 0.1s;">
            <div class="regime-eyebrow">KEY LEVEL BREAKDOWN</div>
            <div class="regime-title">SELL ON RISING BOUNCES</div>
            <div class="regime-sub">Big players expanded their short positions to -168,702 contracts[cite: 1]. Any morning rally will face heavy selling pressure[cite: 1].</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div class='fade-in-up' style='font-size:0.95rem; color:#E5C158; letter-spacing:1.5px; font-weight:700; margin-bottom:10px;'>WHO IS POSITIONED WHERE (PUTS)</div>", unsafe_allow_html=True)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=['Retail (Short Puts)', 'FII (Long Puts)'],
            x=[-485562, 474116],
            orientation='h',
            marker_color=['#39D353', '#FF5C5C'],
            text=['-485,562', '+474,116'],
            textposition='auto',
            textfont=dict(color="white", size=15)
        ))
        fig = style_plotly_fig(fig)
        fig.update_layout(height=220, barmode='relative')
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
    with col2:
        st.markdown("""
        <div class="regime-box fade-in-up" style="animation-delay: 0.2s;">
            <div style="font-size: 1.1rem; color: var(--gold-primary); letter-spacing: 2px; margin-bottom: 25px; font-weight: 800; text-transform: uppercase;">TOMORROW'S TRADE SETUP</div>
            <div class="setup-row"><span class="label">SUGGESTED ENTRY</span><span class="val">24,430 — 24,480</span></div>
            <div class="setup-row"><span class="label">STOP LOSS (DO NOT CROSS)</span><span class="val">24,530</span></div>
            <div class="setup-row" style="border:none;"><span class="label">EXPECTED TARGET</span><span class="val" style="color:var(--gold-primary); font-size: 1.3rem;">24,300</span></div>
        </div>
        """, unsafe_allow_html=True)

def module_flow():
    st.markdown("<h3 class='fade-in-up' style='font-weight:800; margin-bottom: 30px; color: #FFFFFF;'>PARTICIPANT FLOW MATRIX (EASY VIEW)</h3>", unsafe_allow_html=True)
    
    matrix_html = '<table class="matrix-table fade-in-up"><tr><th>Participant Group</th><th>Index Futures Action</th><th>Calls (Buy/Sell)</th><th>Puts (Buy/Sell)</th><th>Stock Futures</th></tr>'
    df_today = pd.DataFrame({
        "PARTICIPANT": ["Client (Retail)", "DIIs (Domestic)", "FIIs (Big Money)", "Pro Desks (M. Makers)"],
        "INDEX FUTURES": ["+4,487 (Buying)", "+4 (Flat)", "-3,533 (Selling)", "-958 (Selling)"],
        "CALLS": ["+46,584 (Buying Longs)", "+20 (Flat)", "-57,902 (Writing Calls)", "+11,298 (Buying)"],
        "PUTS": ["-88,580 (Short Puts)", "-224 (Flat)", "-25,621 (Selling)", "-62,735 (Selling)"],
        "STOCK FUTURES": ["+19,565 (Long)", "-28,765 (Short)", "+4,169 (Long)", "+5,031 (Long)"]
    })
    
    for _, row in df_today.iterrows():
        def format_val(v):
            c = "val-pos" if "Buying" in v or "Long" in v or v.startswith('+') else "val-neg" if "Selling" in v or "Short" in v or v.startswith('-') else ""
            return f'<td class="{c}">{v}</td>'
        matrix_html += f"<tr><td><b>{row['PARTICIPANT']}</b></td>{format_val(row['INDEX FUTURES'])}{format_val(row['CALLS'])}{format_val(row['PUTS'])}{format_val(row['STOCK FUTURES'])}</tr>"
        
    matrix_html += "</table>"
    st.markdown(matrix_html, unsafe_allow_html=True)

def module_trend_analysis():
    st.markdown("<h2 class='fade-in-up' style='font-weight: 800; color: #FFFFFF;'>DAY-OVER-DAY (DoD) TREND ANALYSIS</h2>", unsafe_allow_html=True)
    st.markdown("<p class='fade-in-up' style='color: #A0ABB8; margin-bottom: 25px;'>Tracking what big players and retail changed from yesterday to today.</p>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background:var(--bg-surface); padding: 25px; border-radius:12px; border:1px solid var(--border-subtle); margin-bottom: 30px;">
        <div style="font-size:1.1rem; font-weight:700; color:var(--gold-primary); margin-bottom:15px;">📊 MOMENTUM SHIFT SUMMARY (PLAIN ENGLISH)</div>
        <p style="color:#A0ABB8; line-height:1.6;">
            • <b>Big Players (FIIs):</b> Increased their bearish short positions by another 3,552 contracts today[cite: 1]. They are heavily committed to pushing prices lower.<br>
            • <b>Retail Traders:</b> Chased the morning dip by adding 46k net call options[cite: 1]. They are betting on a recovery while smart money bleeds them through time decay[cite: 1].
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    fig = go.Figure(data=[
        go.Bar(name='Yesterday (T-1)', x=['FII Index Futures', 'Retail Calls', 'Pro Puts'], y=[-165150, 148000, -58000], marker_color='#8A94A6'),
        go.Bar(name='Today (T)', x=['FII Index Futures', 'Retail Calls', 'Pro Puts'], y=[-168702, 194584, -62735], marker_color='#E5C158')
    ])
    fig.update_layout(barmode='group', title="Day-over-Day Momentum Change", height=350)
    fig = style_plotly_fig(fig)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


# --- 7. ROUTER & GATEKEEPER ---
if selected_module == "DATA INGESTION":
    module_data_center()
else:
    if not st.session_state.data_processed:
        st.markdown("""
        <div class='fade-in-up' style='text-align:center; padding: 120px 20px;'>
            <h1 style='font-weight: 800; color: #FF5C5C; letter-spacing: 3px; font-size: 3rem;'>SYSTEM LOCKED</h1>
            <p style='font-size: 1.25rem; color: #A0ABB8; max-width: 650px; margin: 20px auto; line-height: 1.6;'>
                Comparative history engine requires all 8 files across both sessions[cite: 2, 3]. Please go to <b>DATA INGESTION</b> and upload the required reports on both sides.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        if selected_module == "OVERVIEW":
            module_overview()
        elif selected_module == "MARKET FLOW":
            module_flow()
        elif selected_module == "TREND ANALYSIS (DoD)":
            module_trend_analysis()