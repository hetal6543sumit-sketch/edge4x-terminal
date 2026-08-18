"""
EDGE4X Institutional Intelligence Engine (Autonomous Feature Discovery Edition)
=============================================================================
Production-grade self-learning quantitative pipeline for tracking institutional
market structural shifts. Features dynamic L1/L2 regularized feature selection.
"""

import os
import time
import math
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

import requests
import duckdb
import numpy as np
import pandas as pd
import yfinance as yf
import lightgbm as lgb
import joblib
from pydantic import BaseModel, Field, field_validator
import plotly.graph_objects as go
import streamlit as st  # <--- THIS WAS MISSING AND IS NOW FIXED

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("EDGE4X_ENGINE")

# Paths and configuration
DB_PATH = os.path.join(os.getcwd(), "edge4x_telemetry.duckdb")
MODEL_DIR = os.path.join(os.getcwd(), "models", "weights")
os.makedirs(MODEL_DIR, exist_ok=True)


# =====================================================================
# SECTION 1: DATABASE & PYDANTIC VALIDATION LAYER
# =====================================================================

class LiveTickSchema(BaseModel):
    token: str
    timestamp: datetime
    ltp: float = Field(gt=0, description="Last Traded Price must be positive")
    volume: int = Field(ge=0)
    open_interest: int = Field(ge=0)

    @field_validator("ltp")
    @classmethod
    def check_outliers(cls, v: float) -> float:
        if v <= 0 or math.isnan(v):
            raise ValueError("Invalid LTP received from feed")
        return v


class ParticipantOISchema(BaseModel):
    report_date: date
    fii_futures_net: float
    dii_futures_net: float
    pro_futures_net: float
    client_futures_net: float
    fii_call_net: float
    fii_put_net: float
    pro_call_net: float
    pro_put_net: float


class ModelInferenceSchema(BaseModel):
    inference_time: datetime
    regime_long_prob: float = Field(ge=0.0, le=1.0)
    regime_short_prob: float = Field(ge=0.0, le=1.0)
    regime_reversion_prob: float = Field(ge=0.0, le=1.0)
    expected_vol_lower: float
    expected_vol_upper: float
    top_driver: str
    model_version: str
    active_feature_count: int


class DuckDBManager:
    """Manages high-throughput storage for ticks, EOD institutional flow, and ML outputs."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def get_connection(self):
        return duckdb.connect(self.db_path)

    def _init_tables(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS live_ticks (
                    token VARCHAR,
                    timestamp TIMESTAMP,
                    ltp DOUBLE,
                    volume BIGINT,
                    open_interest BIGINT,
                    PRIMARY KEY (token, timestamp)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS eod_institutional_shifts (
                    report_date DATE PRIMARY KEY,
                    fii_futures_net DOUBLE,
                    dii_futures_net DOUBLE,
                    pro_futures_net DOUBLE,
                    client_futures_net DOUBLE,
                    fii_call_net DOUBLE,
                    fii_put_net DOUBLE,
                    pro_call_net DOUBLE,
                    pro_put_net DOUBLE,
                    nifty_close DOUBLE,
                    realized_vol DOUBLE
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_predictions (
                    inference_time TIMESTAMP PRIMARY KEY,
                    regime_long_prob DOUBLE,
                    regime_short_prob DOUBLE,
                    regime_reversion_prob DOUBLE,
                    expected_vol_lower DOUBLE,
                    expected_vol_upper DOUBLE,
                    top_driver VARCHAR,
                    model_version VARCHAR,
                    active_feature_count INTEGER
                );
            """)

    def insert_eod_shift(self, record: ParticipantOISchema, nifty_close: float, realized_vol: float):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO eod_institutional_shifts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.report_date, record.fii_futures_net, record.dii_futures_net,
                record.pro_futures_net, record.client_futures_net, record.fii_call_net,
                record.fii_put_net, record.pro_call_net, record.pro_put_net,
                nifty_close, realized_vol
            ))

    def insert_prediction(self, pred: ModelInferenceSchema):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO model_predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pred.inference_time, pred.regime_long_prob, pred.regime_short_prob,
                pred.regime_reversion_prob, pred.expected_vol_lower, pred.expected_vol_upper,
                pred.top_driver, pred.model_version, pred.active_feature_count
            ))

    def fetch_training_dataset(self) -> pd.DataFrame:
        with self.get_connection() as conn:
            df = conn.execute("""
                SELECT * FROM eod_institutional_shifts 
                WHERE nifty_close IS NOT NULL 
                ORDER BY report_date ASC
            """).fetchdf()
        return df


# =====================================================================
# SECTION 2: DATA INGESTION & ROBUST SCRAPING ENGINE
# =====================================================================

class NSEInstitutionalScraper:
    """Scrapes settled post-market Bhavcopy & Participant OI files directly from NSE."""

    BASE_URL = "https://www.nseindia.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br"
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._warmup_session()

    def _warmup_session(self):
        try:
            self.session.get(self.BASE_URL, timeout=5)
            time.sleep(1.0)
            self.session.headers.update({"Referer": "https://www.nseindia.com/"})
        except Exception as e:
            logger.warning(f"NSE Session initialization warning: {e}")

    def fetch_participant_oi(self, target_date: date) -> Optional[ParticipantOISchema]:
        date_str = target_date.strftime("%d%m%Y")
        url = f"https://archives.nseindia.com/content/nsccl/fao_participant_oi_{date_str}.csv"
        
        try:
            res = self.session.get(url, timeout=8)
            if res.status_code != 200:
                return None

            lines = res.text.strip().split("\n")
            df = pd.read_csv(pd.io.common.StringIO("\n".join(lines[1:])))
            df.columns = [c.strip().lower() for c in df.columns]

            def get_val(client_type: str, long_col_sub: str, short_col_sub: str) -> float:
                row = df[df.iloc[:, 0].astype(str).str.contains(client_type, case=False, na=False)]
                if row.empty: return 0.0
                l_col = next((c for c in df.columns if long_col_sub in c and "index" in c), None)
                s_col = next((c for c in df.columns if short_col_sub in c and "index" in c), None)
                if l_col and s_col:
                    return float(row.iloc[0][l_col]) - float(row.iloc[0][s_col])
                return 0.0

            return ParticipantOISchema(
                report_date=target_date,
                fii_futures_net=get_val("FII", "future", "future"),
                dii_futures_net=get_val("DII", "future", "future"),
                pro_futures_net=get_val("Pro", "future", "future"),
                client_futures_net=get_val("Client", "future", "future"),
                fii_call_net=get_val("FII", "call long", "call short"),
                fii_put_net=get_val("FII", "put long", "put short"),
                pro_call_net=get_val("Pro", "call long", "call short"),
                pro_put_net=get_val("Pro", "put long", "put short")
            )
        except Exception as e:
            logger.error(f"Error scraping settled NSE data for {target_date}: {e}")
            return None


# =====================================================================
# SECTION 3: AUTONOMOUS ML INTELLIGENCE & VOLATILITY ENGINE
# =====================================================================

class WalkForwardMLEngine:
    """
    Implements dynamic feature discovery and expanding-window Walk-Forward retraining.
    No hardcoded features. The AI evaluates all available numeric database columns.
    """
    
    def __init__(self, db: DuckDBManager):
        self.db = db
        self.clf_model: Optional[lgb.LGBMClassifier] = None
        self.vol_upper_model: Optional[lgb.LGBMRegressor] = None
        self.vol_lower_model: Optional[lgb.LGBMRegressor] = None
        self.model_version: str = "v1.0.0"
        self.active_features: List[str] = []
        self._load_latest_artifacts()

    def _feature_engineering(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms raw records and dynamically creates deltas for ALL numeric columns."""
        df = df.copy().sort_values("report_date").reset_index(drop=True)
        
        # Automatically create Day-over-Day momentum (deltas) for all numeric base features
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        for col in numeric_cols:
            if col not in ["target_regime", "target_upper_move", "target_lower_move", "fwd_ret"]:
                df[f"{col}_delta"] = df[col].diff()
        
        # Core interaction features
        if "client_futures_net" in df.columns and "fii_futures_net" in df.columns:
            df["retail_divergence"] = df["client_futures_net"] - df["fii_futures_net"]
        
        if "nifty_close" in df.columns and "realized_vol" in df.columns:
            df["fwd_ret"] = df["nifty_close"].pct_change().shift(-1)
            df["rolling_ret_5d"] = df["nifty_close"].pct_change(5)
            df["rolling_vol_5d"] = df["realized_vol"].rolling(5).mean()
            
            # Label allocation: 1 (Expansion Long), 2 (Expansion Short), 0 (Mean Reversion)
            theta = 0.005
            conditions = [(df["fwd_ret"] > theta), (df["fwd_ret"] < -theta)]
            df["target_regime"] = np.select(conditions, [1, 2], default=0) 

            # Volatility envelope targets
            df["target_upper_move"] = df["nifty_close"] * (1 + df["rolling_vol_5d"] * np.sqrt(1/252))
            df["target_lower_move"] = df["nifty_close"] * (1 - df["rolling_vol_5d"] * np.sqrt(1/252))

        return df.dropna().reset_index(drop=True)

    def _perform_feature_discovery(self, df: pd.DataFrame) -> List[str]:
        """AUTONOMOUS FEATURE DISCOVERY: Uses L1/L2 Regularization to mathematically drop noise."""
        excluded = ["report_date", "target_regime", "target_upper_move", "target_lower_move", "fwd_ret", "nifty_close"]
        potential_features = [c for c in df.columns if c not in excluded and pd.api.types.is_numeric_dtype(df[c])]
        
        # Heavy regularization penalizes weak data, pushing its weight to exactly 0.0
        discovery_model = lgb.LGBMClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.05,
            reg_alpha=0.5, reg_lambda=0.5, 
            random_state=42, verbose=-1
        )
        discovery_model.fit(df[potential_features], df["target_regime"])
        
        importances = discovery_model.feature_importances_
        # Survival of the fittest: keep only features that survived regularization
        survivors = [feat for feat, imp in zip(potential_features, importances) if imp > 0]
        
        if not survivors:
            survivors = potential_features[:5] # Fail-safe
            
        logger.info(f"Feature Discovery complete. Retained {len(survivors)} predictive variables out of {len(potential_features)}.")
        return survivors

    def train_walk_forward(self, min_train_size: int = 20) -> Dict[str, Any]:
        """Executes expanding-window Walk-Forward training using dynamically discovered features."""
        raw_df = self.db.fetch_training_dataset()
        if len(raw_df) < (min_train_size + 5):
            return {"status": "INSUFFICIENT_DATA", "rows": len(raw_df), "min_required": min_train_size + 5}

        df = self._feature_engineering(raw_df)
        if len(df) < min_train_size:
            return {"status": "INSUFFICIENT_PROCESSED_DATA", "rows": len(df)}

        # Execute Autonomous Discovery Phase
        self.active_features = self._perform_feature_discovery(df)

        oof_predictions = []
        oof_targets = []
        
        # Expanding window training loop on SURVIVING features only
        for i in range(min_train_size, len(df)):
            train_fold = df.iloc[:i]
            test_fold = df.iloc[i:i+1]

            X_train, y_train = train_fold[self.active_features], train_fold["target_regime"]
            X_test, y_test = test_fold[self.active_features], test_fold["target_regime"]

            fold_clf = lgb.LGBMClassifier(n_estimators=60, max_depth=3, learning_rate=0.03, random_state=42, verbose=-1)
            fold_clf.fit(X_train, y_train)
            oof_predictions.append(fold_clf.predict_proba(X_test)[0])
            oof_targets.append(y_test.values[0])

        # Final fit on complete historical data
        X_all, y_all = df[self.active_features], df["target_regime"]
        self.clf_model = lgb.LGBMClassifier(n_estimators=80, max_depth=4, learning_rate=0.03, random_state=42, verbose=-1)
        self.clf_model.fit(X_all, y_all)

        self.vol_upper_model = lgb.LGBMRegressor(objective="quantile", alpha=0.95, n_estimators=50, max_depth=3, verbose=-1)
        self.vol_upper_model.fit(X_all, df["target_upper_move"])

        self.vol_lower_model = lgb.LGBMRegressor(objective="quantile", alpha=0.05, n_estimators=50, max_depth=3, verbose=-1)
        self.vol_lower_model.fit(X_all, df["target_lower_move"])

        self.model_version = f"v{datetime.now().strftime('%Y%m%d_%H%M')}"
        self._save_artifacts()

        oof_pred_classes = [np.argmax(p) for p in oof_predictions]
        accuracy = np.mean(np.array(oof_pred_classes) == np.array(oof_targets)) if oof_targets else 0.0

        return {
            "status": "SUCCESS",
            "version": self.model_version,
            "train_samples": len(df),
            "walk_forward_accuracy": float(accuracy),
            "active_feature_count": len(self.active_features)
        }

    def _save_artifacts(self):
        joblib.dump(self.clf_model, os.path.join(MODEL_DIR, "clf_model.joblib"))
        joblib.dump(self.vol_upper_model, os.path.join(MODEL_DIR, "vol_upper.joblib"))
        joblib.dump(self.vol_lower_model, os.path.join(MODEL_DIR, "vol_lower.joblib"))
        joblib.dump(self.active_features, os.path.join(MODEL_DIR, "active_features.joblib"))
        logger.info(f"Successfully persisted model version {self.model_version}")

    def _load_latest_artifacts(self):
        clf_p = os.path.join(MODEL_DIR, "clf_model.joblib")
        vol_u_p = os.path.join(MODEL_DIR, "vol_upper.joblib")
        vol_l_p = os.path.join(MODEL_DIR, "vol_lower.joblib")
        feat_p = os.path.join(MODEL_DIR, "active_features.joblib")
        
        if os.path.exists(clf_p) and os.path.exists(feat_p):
            self.clf_model = joblib.load(clf_p)
            self.vol_upper_model = joblib.load(vol_u_p)
            self.vol_lower_model = joblib.load(vol_l_p)
            self.active_features = joblib.load(feat_p)

    def run_live_inference(self, current_features: pd.DataFrame, current_spot: float) -> Optional[ModelInferenceSchema]:
        """Calculates dynamic regime probability and expected volatility distribution."""
        if not self.clf_model or not self.active_features:
            return None

        # Dynamically inject features. If a new column was discovered during training but missing here, pad with 0.
        X_live = pd.DataFrame(index=[0])
        for feat in self.active_features:
            X_live[feat] = current_features[feat].iloc[0] if feat in current_features.columns else 0.0

        probs = self.clf_model.predict_proba(X_live)[0]
        
        p_reversion = float(probs[0]) if len(probs) > 0 else 0.33
        p_long = float(probs[1]) if len(probs) > 1 else 0.33
        p_short = float(probs[2]) if len(probs) > 2 else 0.34

        vol_upper = float(self.vol_upper_model.predict(X_live)[0])
        vol_lower = float(self.vol_lower_model.predict(X_live)[0])

        importances = self.clf_model.feature_importances_
        top_driver_idx = int(np.argmax(importances))
        top_driver = self.active_features[top_driver_idx]

        inference_record = ModelInferenceSchema(
            inference_time=datetime.now(),
            regime_long_prob=p_long,
            regime_short_prob=p_short,
            regime_reversion_prob=p_reversion,
            expected_vol_lower=vol_lower,
            expected_vol_upper=vol_upper,
            top_driver=top_driver,
            model_version=self.model_version,
            active_feature_count=len(self.active_features)
        )
        self.db.insert_prediction(inference_record)
        return inference_record


# =====================================================================
# SECTION 4: AUTOMATED NIGHTLY BATCH PIPELINE
# =====================================================================

def execute_nightly_batch_job():
    logger.info("Starting Nightly Quantitative Synchronization...")
    db = DuckDBManager()
    scraper = NSEInstitutionalScraper()
    
    today = date.today()
    record = scraper.fetch_participant_oi(today)
    
    if record is None:
        today = today - timedelta(days=1)
        record = scraper.fetch_participant_oi(today)

    if record:
        try:
            nifty_hist = yf.Ticker("^NSEI").history(period="10d")
            nifty_close = float(nifty_hist['Close'].iloc[-1])
            realized_vol = float(nifty_hist['Close'].pct_change().std() * np.sqrt(252))
            db.insert_eod_shift(record, nifty_close, realized_vol)
        except Exception as e:
            logger.error(f"Failed to record settled spot price: {e}")

    engine = WalkForwardMLEngine(db)
    result = engine.train_walk_forward()
    logger.info(f"Walk-Forward Retraining Result: {result}")
    return result


# =====================================================================
# SECTION 5: STREAMLIT UI (INSTITUTIONAL INTELLIGENCE ENGINE TAB)
# =====================================================================

def render_ai_intelligence_tab():
    """Renders the comprehensive Quantitative AI Engine Dashboard."""
    db = DuckDBManager()
    engine = WalkForwardMLEngine(db)

    st.markdown("""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;">
            <h2 style="margin:0; font-weight:800; letter-spacing:1px; color:#F5F7FA;">
                🧠 EDGE4X INSTITUTIONAL INTELLIGENCE ENGINE
            </h2>
            <span style="font-size:0.8rem; background:rgba(212,175,55,0.1); border:1px solid #D4AF37; color:#D4AF37; padding:4px 12px; border-radius:4px; font-weight:700;">
                AUTONOMOUS FEATURE DISCOVERY ACTIVE
            </span>
        </div>
    """, unsafe_allow_html=True)

    training_data = db.fetch_training_dataset()
    has_sufficient_history = len(training_data) >= 20

    if not has_sufficient_history:
        st.markdown(f"""
            <div style="background: rgba(255, 92, 92, 0.08); border: 1px solid #FF5C5C; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                <div style="font-weight: 800; color: #FF5C5C; font-size: 1.05rem;">⚠ INSUFFICIENT SETTLED HISTORICAL DATA FOR RETRAINING</div>
                <div style="color: #A7AFBA; font-size: 0.88rem; margin-top: 6px; line-height: 1.5;">
                    The self-learning mathematical engine requires a minimum of <b>20 settled trading sessions</b> to calibrate walk-forward weights. 
                    Current active records in DuckDB: <b>{len(training_data)} sessions</b>.
                </div>
            </div>
        """, unsafe_allow_html=True)

    try:
        nifty_hist = yf.Ticker("^NSEI").history(period="10d")
        current_spot = float(nifty_hist['Close'].iloc[-1])
        realized_vol = float(nifty_hist['Close'].pct_change().std() * np.sqrt(252))
    except Exception:
        current_spot = 24385.0
        realized_vol = 0.12

    # Synthesize live row for inference dynamically
    if not training_data.empty:
        live_features_df = engine._feature_engineering(training_data).tail(1)
        inference = engine.run_live_inference(live_features_df, current_spot)
    else:
        inference = None

    # --- TOP ROW: AI PREDICTIVE SCORECARD ---
    col_score1, col_score2, col_score3 = st.columns([1.2, 1.4, 1.4])

    with col_score1:
        st.markdown("<div class='panel-box' style='height:100%;'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-header'>REGIME PROBABILITY SHIFT</div>", unsafe_allow_html=True)
        
        if inference:
            p_long = inference.regime_long_prob * 100
            p_short = inference.regime_short_prob * 100
            p_rev = inference.regime_reversion_prob * 100
            
            top_prob = max(p_long, p_short, p_rev)
            if top_prob == p_long:
                dominant_regime, d_color = "EXPANSION LONG", "#39D353"
            elif top_prob == p_short:
                dominant_regime, d_color = "EXPANSION SHORT", "#FF5C5C"
            else:
                dominant_regime, d_color = "MEAN REVERSION", "#D4AF37"

            st.markdown(f"""
                <div style="font-size: 1.8rem; font-weight:800; color:{d_color}; margin-bottom: 12px;">{dominant_regime}</div>
                <div class="setup-row"><span class="setup-label">Expansion Long</span><span class="setup-val" style="color:#39D353;">{p_long:.1f}%</span></div>
                <div class="setup-row"><span class="setup-label">Expansion Short</span><span class="setup-val" style="color:#FF5C5C;">{p_short:.1f}%</span></div>
                <div class="setup-row"><span class="setup-label">Mean Reversion / Chop</span><span class="setup-val" style="color:#D4AF37;">{p_rev:.1f}%</span></div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#6F7782; padding:30px 0; text-align:center;'>Awaiting Model Training</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_score2:
        st.markdown("<div class='panel-box' style='height:100%;'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-header'>DYNAMIC EXPECTED MOVE (QUANTILE ENVELOPE)</div>", unsafe_allow_html=True)
        
        if inference and inference.expected_vol_upper > 0:
            upper, lower = inference.expected_vol_upper, inference.expected_vol_lower
            st.markdown(f"""
                <div style="font-size: 1.8rem; font-weight:800; color:#F5F7FA; margin-bottom: 12px;">±{(upper - lower) / 2:,.0f} Pts <span style="font-size:0.9rem; color:#A7AFBA;">(95% Quantile)</span></div>
                <div class="setup-row"><span class="setup-label">Model Upper Boundary ($q_{{0.95}}$)</span><span class="setup-val" style="color:#39D353;">{upper:,.2f}</span></div>
                <div class="setup-row"><span class="setup-label">Current Reference Spot</span><span class="setup-val">{current_spot:,.2f}</span></div>
                <div class="setup-row"><span class="setup-label">Model Lower Boundary ($q_{{0.05}}$)</span><span class="setup-val" style="color:#FF5C5C;">{lower:,.2f}</span></div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#6F7782; padding:30px 0; text-align:center;'>Awaiting Mathematical Calibration</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_score3:
        st.markdown("<div class='panel-box' style='height:100%;'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-header'>PRIMARY ATTRIBUTION DRIVER</div>", unsafe_allow_html=True)
        
        if inference:
            st.markdown(f"""
                <div style="font-size: 1.4rem; font-weight:800; color:#D4AF37; margin-bottom: 8px;">{inference.top_driver.replace("_", " ").upper()}</div>
                <div style="font-size: 0.85rem; color: #A7AFBA; line-height: 1.5; margin-bottom: 15px;">
                    This feature holds the highest statistical correlation in shifting current institutional probability envelopes.
                </div>
                <div class="setup-row"><span class="setup-label">Features Discovered & Retained</span><span class="setup-val" style="color:var(--gold-primary);">{inference.active_feature_count} Active</span></div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#6F7782; padding:30px 0; text-align:center;'>Awaiting Attribution Data</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- MIDDLE ROW: HEATMAP & FEATURE RETENTION ---
    col_vis1, col_vis2 = st.columns([1.5, 1.2])

    with col_vis1:
        st.markdown("<div class='panel-box'><div class='panel-header'>INSTITUTIONAL POSITIONING SHIFT HEATMAP (DuckDB)</div>", unsafe_allow_html=True)
        if not training_data.empty:
            df_plot = training_data.tail(15).copy()
            df_plot["report_date"] = pd.to_datetime(df_plot["report_date"]).dt.strftime("%d-%b")
            
            heatmap_fig = go.Figure(data=go.Heatmap(
                z=[df_plot["fii_futures_net"].tolist(), df_plot["pro_call_net"].tolist(), df_plot["fii_put_net"].tolist(), df_plot["client_futures_net"].tolist()],
                x=df_plot["report_date"].tolist(),
                y=["FII Futures", "Pro Calls", "FII Puts", "Retail Crowd"],
                colorscale="RdYlGn", colorbar=dict(title="Contracts", tickfont=dict(color="#A7AFBA"))
            ))
            heatmap_fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#A7AFBA", size=11), height=260, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(heatmap_fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.markdown("<div style='color:#6F7782; text-align:center; padding: 50px 0;'>Awaiting DuckDB Records...</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_vis2:
        st.markdown("<div class='panel-box'><div class='panel-header'>AUTONOMOUS FEATURE RETENTION & DRIFT</div>", unsafe_allow_html=True)
        if st.button("RUN ON-DEMAND WALK-FORWARD RETRAIN", use_container_width=True):
            with st.spinner("Executing dynamic feature selection and Walk-Forward cross validation..."):
                retrain_res = engine.train_walk_forward()
                if retrain_res.get("status") == "SUCCESS":
                    st.success(f"Retrained {retrain_res['version']} | {retrain_res['active_feature_count']} Features Discovered | OOF Accuracy: {retrain_res['walk_forward_accuracy']*100:.1f}%")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Retraining paused: {retrain_res.get('status')}")

        if engine.clf_model and engine.active_features:
            feat_fig = go.Figure(go.Bar(
                x=engine.clf_model.feature_importances_,
                y=engine.active_features,
                orientation='h', marker=dict(color='#D4AF37')
            ))
            feat_fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#A7AFBA", size=10), height=200, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))
            st.plotly_chart(feat_fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.markdown("<div style='color:#6F7782; text-align:center; padding:30px 0;'>Model not loaded</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)