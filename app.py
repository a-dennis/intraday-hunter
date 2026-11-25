"""
Intraday Hunter v3 - SCORING version (NSE cash segment, Yahoo Finance data)

What changed from v2:
  * The old 5-stage strict funnel (a stock had to pass every stage) is gone.
  * Every stock now gets a score from 0 to 100 and the best ones are ranked.
    The list is never empty, even on a quiet day.
Kept as before: login, professional look, paper trading, journal, chart.
Everything is in this one file: replace app.py on GitHub and reboot the app.
"""
import os
import hmac
import time as _time
from datetime import datetime, time as dtime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
JOURNAL = "journal.csv"
BTST_JOURNAL = "btst_journal.csv"
COLS = ["id", "date", "time", "symbol", "side", "entry", "stop", "target", "qty", "status", "exit", "exit_time",
        "gross", "costs", "net", "r", "relvol", "rank", "setup", "note"]

# Liquid universe (roughly Nifty 200). If Yahoo does not know a symbol it is simply skipped.
# You can edit this list in the sidebar.
UNIVERSE = """RELIANCE TCS HDFCBANK ICICIBANK INFY BHARTIARTL ITC SBIN LT KOTAKBANK HINDUNILVR AXISBANK BAJFINANCE
ASIANPAINT MARUTI SUNPHARMA TITAN ULTRACEMCO NTPC ONGC POWERGRID TATASTEEL JSWSTEEL HCLTECH WIPRO TECHM ADANIPORTS
COALINDIA BAJAJFINSV NESTLEIND GRASIM HINDALCO CIPLA DRREDDY EICHERMOT BPCL HEROMOTOCO INDUSINDBK TATACONSUM APOLLOHOSP
SBILIFE HDFCLIFE BRITANNIA DIVISLAB SHRIRAMFIN TRENT BEL PNB BANKBARODA CANBK IOC GAIL VEDL DLF HAL RECLTD PFC SAIL NMDC
IDFCFIRSTB M&M BAJAJ-AUTO TATAMOTORS ADANIENT ADANIPOWER ADANIGREEN ADANIENSOL AMBUJACEM ACC SHREECEM DABUR GODREJCP
MARICO COLPAL PIDILITIND HAVELLS SIEMENS ABB CGPOWER POLYCAB DIXON VOLTAS CUMMINS BHEL BDL MAZDOCK COCHINSHIP
BHARATFORG MOTHERSON BOSCHLTD ASHOKLEY TVSMOTOR BALKRISIND MRF APOLLOTYRE SONACOMS UNOMINDA TIINDIA
JINDALSTEL JSWENERGY TATAPOWER NHPC SJVN IREDA TORNTPOWER NTPCGREEN OIL PETRONET IGL MGL GUJGASLTD HINDPETRO CHENNPETRO
LUPIN AUROPHARMA ZYDUSLIFE TORNTPHARM ALKEM MANKIND BIOCON GLENMARK LAURUSLABS MAXHEALTH FORTIS SYNGENE
PERSISTENT COFORGE MPHASIS LTIM OFSS KPITTECH TATAELXSI LTTS TATATECH CYIENT
AUBANK BANDHANBNK FEDERALBNK RBLBANK YESBANK IDBI UNIONBANK INDIANB BANKINDIA MAHABANK IOB
CHOLAFIN MUTHOOTFIN MANAPPURAM LICHSGFIN PNBHOUSING CANFINHOME SBICARD HDFCAMC ICICIGI ICICIPRULI LICI
JIOFIN BAJAJHFL ABCAPITAL M&MFIN POONAWALLA PAYTM POLICYBZR NAUKRI NYKAA ZOMATO ETERNAL SWIGGY DMART
JUBLFOOD DEVYANI VBL UNITDSPR UBL RADICO PGHH PATANJALI
INDIGO IRCTC IRFC RVNL RAILTEL CONCOR TITAGARH JSL NATIONALUM HINDZINC APLAPOLLO WELSPUNLIV
GMRAIRPORT LODHA OBEROIRLTY GODREJPROP PRESTIGE PHOENIXLTD BRIGADE
PAGEIND KALYANKJIL BATAINDIA RELAXO ABFRL CROMPTON WHIRLPOOL BLUESTARCO
UPL PIIND SRF DEEPAKNTR NAVINFLUOR TATACHEM COROMANDEL CHAMBLFERT GNFC
CESC ASTRAL SUPREMEIND DELHIVERY INDUSTOWER IDEA TATACOMM HFCL
IEX CDSL BSE MCX ANGELONE KFINTECH CAMS""".split()

st.set_page_config(page_title="Intraday Hunter", page_icon="🎯", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:3.5rem;max-width:1280px}
.hero{background:linear-gradient(120deg,#0b1f33,#15405f 55%,#1d6a7a);border-radius:18px;padding:22px 28px;color:#fff;margin-bottom:16px;
 box-shadow:0 6px 24px rgba(0,0,0,.18)}
.hero h1{margin:0;font-size:31px;color:#fff;letter-spacing:.3px}
.hero p{margin:5px 0 0;color:#cfe6f2;font-size:15px}
.kpi{border:1px solid rgba(128,128,128,.28);border-radius:14px;padding:12px 16px;background:rgba(128,128,128,.05)}
.kpi b{font-size:25px;display:block;line-height:1.2}.kpi span{font-size:12.5px;opacity:.7;letter-spacing:.3px}
.pick{border:1px solid rgba(128,128,128,.3);border-radius:16px;padding:14px 16px;margin-bottom:8px;background:rgba(128,128,128,.05)}
.pick.long{border-top:4px solid #14a44d}.pick.short{border-top:4px solid #e03131}
.pick h3{margin:0;font-size:21px}.pick .sub{font-size:12.5px;opacity:.7}
.pill{display:inline-block;border-radius:999px;padding:2px 11px;font-size:12px;font-weight:700;color:#fff;margin-left:6px}
.pill.long{background:#14a44d}.pill.short{background:#e03131}.pill.rank{background:#495a6e}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}
.grid div{background:rgba(128,128,128,.08);border-radius:10px;padding:6px 9px;font-size:12px}
.grid b{display:block;font-size:15px}
.chips span{display:inline-block;font-size:11.5px;border-radius:8px;padding:2px 7px;margin:2px 3px 0 0;background:rgba(20,164,77,.16);color:inherit}
.chips span.no{background:rgba(224,49,49,.16)}
.warn{border-left:4px solid #f08c00;background:rgba(240,140,0,.1);padding:10px 14px;border-radius:8px;font-size:14px;margin:8px 0}
.note{border-left:4px solid #1c7ed6;background:rgba(28,126,214,.08);padding:10px 14px;border-radius:8px;font-size:14px;margin:8px 0}
.pill.label{background:#1c7ed6}.pill.score{background:#14a44d}
.bar{height:7px;border-radius:5px;background:rgba(128,128,128,.2);margin:6px 0 2px}.bar i{display:block;height:7px;border-radius:5px;background:linear-gradient(90deg,#1d6a7a,#14a44d)}
.why{margin-top:8px;padding:8px 10px;border-radius:10px;background:rgba(28,126,214,.08);font-size:12.5px}.why .nw{margin-top:4px}.why .tg{background:rgba(240,140,0,.2);border-radius:6px;padding:0 5px;font-size:11px;font-style:normal}.why a{color:inherit}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- login gate (owner only)


def _gate():
    try:
        want_user, want_pw = str(st.secrets["APP_USER"]), str(st.secrets["APP_PASSWORD"])
    except Exception:
        st.error("Login is not set up, so the app is locked.")
        st.stop()
    if st.session_state.get("auth_ok"):
        return
    st.markdown('<div class="hero"><h1>Intraday Hunter</h1><p>Private. Please log in.</p></div>', unsafe_allow_html=True)
    if st.session_state.get("fails", 0) >= 5 and _time.time() < st.session_state.get("lock_until", 0):
        st.error("Too many tries. Wait a minute and try again.")
        st.stop()
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("Log in")
    if ok:
        good = hmac.compare_digest(u.strip().lower().encode(), want_user.lower().encode()) & \
            hmac.compare_digest(p.encode(), want_pw.encode())
        if good:
            st.session_state.auth_ok = True
            st.session_state.fails = 0
            st.rerun()
        st.session_state.fails = st.session_state.get("fails", 0) + 1
        if st.session_state.fails >= 5:
            st.session_state.lock_until = _time.time() + 60
        st.error("Wrong username or password.")
    st.stop()


_gate()

# ============================================================ data

def now_ist():
    return datetime.now(IST)

def clean(raw, t, many):
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            lv0 = raw.columns.get_level_values(0)
            if t in lv0:
                d = raw[t]
            elif "Close" in lv0 and not many:
                d = raw.droplevel(1, axis=1)
            else:
                return None
        else:
            d = raw
        d = d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
        if d.empty:
            return None
        d.index = pd.to_datetime(d.index)
        d.index = d.index.tz_localize(IST) if d.index.tz is None else d.index.tz_convert(IST)
        return d
    except Exception:
        return None


CHUNK = 40  # download in small batches so Yahoo does not block us


@st.cache_data(ttl=90, show_spinner=False)
def fetch(symbols):
    """5-minute candles for about one month (enough for the 20-day high and normal volume).
    A failed batch or a bad symbol is skipped, never a crash."""
    out = {}
    for i in range(0, len(symbols), CHUNK):
        part = symbols[i:i + CHUNK]
        tick = [s + ".NS" for s in part]
        try:
            raw = yf.download(tick, period="1mo", interval="5m", group_by="ticker",
                              auto_adjust=False, progress=False, threads=True)
        except Exception:
            continue
        for s, t in zip(part, tick):
            d = clean(raw, t, len(tick) > 1)
            if d is not None and len(d) > 20:
                out[s] = d
    return out


# ============================================================ scoring
def ramp(x, xs, ys):
    """Straight-line points between the anchors (below the first anchor = first value, above the last = last value)."""
    return float(np.interp(x, xs, ys))


def breakout_points(age):
    """Full 30 points if the breakout is within the last 5 candles, fewer as it gets older."""
    return ramp(age, [4, 12, 30], [30, 12, 0])


def score_stock(sym, d, P, side):
    """Score one stock for one side. side = +1 (buy) or -1 (sell).
    For the sell side we flip the prices (negate them) and reuse the buy logic, so
    'breakdown below low' is just 'breakout above high' on flipped prices."""
    d = d.copy()
    d["date"] = d.index.date
    days = sorted(d["date"].unique())
    if len(days) < 6:
        return None
    D = days[-1]
    prior_days = days[-21:-1]
    t = d[d["date"] == D]
    pr = d[d["date"].isin(prior_days)]
    if len(t) < 2 or pr.empty:
        return None
    prev = pr[pr["date"] == prior_days[-1]]
    pc = float(prev.Close.iloc[-1])
    ltp = float(t.Close.iloc[-1])
    if pc <= 0 or ltp <= 0:
        return None

    # --- Step 1: light filter (price range and enough volume to get in and out)
    daily_vol = pr.groupby("date").Volume.sum()
    avg_vol = float(daily_vol.mean())
    if not (P["pmin"] <= ltp <= P["pmax"]) or avg_vol < P["min_vol"]:
        return None

    s = side
    o, h, l, c = (s * t[x].to_numpy(float) for x in ("Open", "High", "Low", "Close"))
    if s == -1:
        o, h, l, c = o, -t.Low.to_numpy(float), -t.High.to_numpy(float), c  # flipped high = -low, flipped low = -high
    n = len(t)
    pct = (ltp / pc - 1) * 100 * s

    # --- Fast move (25): 1% = low, 2% = medium, 3%+ = full
    p_move = ramp(pct, [0, 1, 2, 3], [0, 8, 17, 25])

    # --- Volume surge (25): volume so far today vs the average for the SAME time of day
    cut = t.index[-1].time()
    same_time = pr[pr.index.time <= cut].groupby("date").Volume.sum()
    typical = float(same_time.mean()) if len(same_time) else 0.0
    vx = float(t.Volume.sum() / typical) if typical > 0 else 0.0
    p_vol = ramp(vx, [0, 1, 1.5, 2, 3], [0, 0, 8, 17, 25])

    # --- Fresh breakout (30): crossed today's high so far, yesterday's high or the 20-day high
    pdh = s * float(prev.High.max() if s == 1 else prev.Low.min())
    d20 = s * float(pr.High.max() if s == 1 else pr.Low.min())
    pcs = s * pc
    best = (0.0, None, None, None, 99)  # points, level, level name, candle index, age
    names = "high" if s == 1 else "low"
    static = [(d20, f"20-day {names}", 3), (pdh, f"Yesterday's {names}", 2)]
    for lvl, nm, prio in static:
        cross = None
        for j in range(n):
            before = pcs if j == 0 else c[j - 1]
            if c[j] > lvl and before <= lvl:
                cross = j
        if cross is not None and c[-1] > lvl:  # must still be holding above the level
            age = n - 1 - cross
            pts = breakout_points(age)
            if pts > best[0]:
                best = (pts, lvl, nm, cross, age)
    cross = None
    for j in range(3, n):  # today's high so far (ignore the very first candles, they are just noise)
        lvl_j = h[:j].max()
        if c[j] > lvl_j:
            cross = (j, lvl_j)
    if cross is not None and c[-1] >= cross[1]:
        j, lvl_j = cross
        age = n - 1 - j
        pts = breakout_points(age)
        if pts > best[0]:
            best = (pts, lvl_j, f"Day {names}", j, age)
    p_brk, lvl, lvl_name, jb, age = best

    # --- VWAP (10): above VWAP (buy side) or below VWAP (sell side)
    typ = (t.High + t.Low + t.Close) / 3
    cumv = t.Volume.cumsum().replace(0, np.nan)
    vwap = float((typ * t.Volume).cumsum().iloc[-1] / cumv.iloc[-1]) if cumv.iloc[-1] == cumv.iloc[-1] else ltp
    p_vwap = 10.0 if s * (ltp - vwap) > 0 else 0.0

    # --- Strong candle (10): closes near its high, good body, short upper wick
    rng = h[-1] - l[-1]
    if rng > 0:
        closepos = (c[-1] - l[-1]) / rng
        body = (c[-1] - o[-1]) / rng
        wick = (h[-1] - max(c[-1], o[-1])) / rng
        p_can = 5 * np.clip((closepos - 0.5) / 0.4, 0, 1) + 5 * np.clip(body / 0.5, 0, 1)
        if wick > 0.3:
            p_can *= 0.5
    else:
        p_can = 0.0

    total = p_move + p_vol + p_brk + p_vwap + p_can

    # --- Label
    if p_brk >= 24:
        label = "Fresh breakout" if s == 1 else "Fresh breakdown"
    elif p_move >= 17:
        label = "Fast mover"
    elif p_vol >= 17:
        label = "Volume surge"
    elif p_brk > 0:
        label = "Older breakout" if s == 1 else "Older breakdown"
    else:
        label = "Watchlist"

    # --- Step 4: simple trade plan (works on real prices, so convert back from flipped numbers)
    if lvl is None:  # no breakout: use today's high (buy) / low (sell) so far as the level
        lvl = h.max()
    lvl_real = s * lvl
    last_low_real = float(t.Low.iloc[-1]) if s == 1 else float(t.High.iloc[-1])
    entry = lvl_real * (1 + 0.001 * s)           # just above (buy) / below (sell) the level
    if s * (ltp - entry) > 0:
        entry = ltp                               # price has already moved past it: enter at the market
    below = lvl_real * (1 - 0.001 * s)            # just below (buy) / above (sell) the level
    stop = below
    if s * (last_low_real - entry) < 0 and s * (last_low_real - below) > 0:
        stop = last_low_real                      # last candle low is tighter than the level
    risk = abs(entry - stop)
    risk = max(risk, entry * 0.003)               # never plan a stop tighter than 0.3%
    stop = entry - s * risk
    target = entry + s * 2 * risk                 # risk : reward = 1 : 2
    qty = int(max(0, min(P["risk"] // risk, P["capital"] * P["lev"] // entry)))

    return {
        "Symbol": sym, "Side": "LONG" if s == 1 else "SHORT", "LTP": round(ltp, 2), "Chg %": round((ltp / pc - 1) * 100, 2),
        "VolX": round(vx, 2), "Score": round(float(total), 1), "Label": label,
        "Break time": t.index[jb].strftime("%H:%M") if jb is not None else "-",
        "Break level": f"{lvl_name} {lvl_real:.2f}" if lvl_name else "none yet",
        "Move": round(p_move, 1), "Volume": round(p_vol, 1), "Breakout": round(p_brk, 1),
        "VWAP": round(p_vwap, 1), "Candle": round(float(p_can), 1),
        "Entry": round(entry, 2), "Stop": round(stop, 2), "Target": round(target, 2), "Qty": qty,
        "Risk/sh": round(risk, 2), "_last": t.index[-1], "_age": age,
        "PrevClose": round(pc, 2), "PrevDate": prior_days[-1].strftime("%a %d %b"),
    }


def run_scan(data, P, both):
    """Score every stock. A bad stock is skipped, the scan continues."""
    rows, skipped = [], []
    for sym, d in data.items():
        try:
            cands = [score_stock(sym, d, P, 1)]
            if both:
                cands.append(score_stock(sym, d, P, -1))
            cands = [x for x in cands if x]
            if not cands:
                skipped.append(sym)
                continue
            rows.append(max(cands, key=lambda x: x["Score"]))
        except Exception:
            skipped.append(sym)
    df = pd.DataFrame(rows)
    if len(df):
        df = df.sort_values("Score", ascending=False).reset_index(drop=True)
    return df, skipped


# ============================================================ journal
def norm(df):
    for c in COLS:
        if c not in df.columns:
            df[c] = np.nan
    df = df[COLS].copy()
    for c in ("setup", "note", "status", "side", "symbol", "date", "time", "exit_time"):
        df[c] = df[c].fillna("").astype(str)
    for c in ("id", "entry", "stop", "target", "qty", "exit", "gross", "costs", "net", "r", "relvol", "rank"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_journal():
    if os.path.exists(JOURNAL):
        try:
            return norm(pd.read_csv(JOURNAL))
        except Exception:
            pass
    return norm(pd.DataFrame(columns=COLS))


def save_journal():
    try:
        st.session_state.journal.to_csv(JOURNAL, index=False)
    except Exception:
        pass


def add_trade(r, setup, note):
    j = st.session_state.journal
    nid = int(pd.to_numeric(j["id"], errors="coerce").max() + 1) if len(j) else 1
    last = r["_last"]
    new = {"id": nid, "date": last.strftime("%Y-%m-%d"), "time": last.strftime("%H:%M"), "symbol": r["Symbol"],
           "side": r["Side"], "entry": r["Entry"], "stop": r["Stop"], "target": r["Target"], "qty": r["Qty"],
           "status": "OPEN", "relvol": r["VolX"], "rank": r["Score"], "setup": setup, "note": note}
    st.session_state.journal = norm(pd.concat([j, pd.DataFrame([new])], ignore_index=True))
    save_journal()


def close_trade(i, price, status, when, cfg):
    j = st.session_state.journal
    r = j.loc[i]
    m = 1 if r.side == "LONG" else -1
    q = float(r.qty)
    gross = (price - r.entry) * q * m
    costs = 2 * cfg["flat"] + cfg["pct"] / 100 * (r.entry + price) * q
    risk = abs(r.entry - r.stop) * q
    j.loc[i, ["status", "exit", "exit_time"]] = [status, round(price, 2), when]
    j.loc[i, "gross"] = round(gross, 2)
    j.loc[i, "costs"] = round(costs, 2)
    j.loc[i, "net"] = round(gross - costs, 2)
    j.loc[i, "r"] = round((gross - costs) / risk, 2) if risk > 0 else np.nan
    st.session_state.journal = j
    save_journal()


def check_open(data, cfg):
    j = st.session_state.journal
    done = 0
    for i in j.index[j.status == "OPEN"]:
        r = j.loc[i]
        d = data.get(r.symbol)
        if d is None:
            continue
        day = pd.Timestamp(r.date).date()
        dd = d[d.index.date == day]
        if dd.empty:
            continue
        sub = dd[dd.index > pd.Timestamp(f"{r.date} {r.time}", tz=IST)]
        hit = None
        for ts, c in sub.iterrows():
            if r.side == "LONG":
                if c.Low <= r.stop:
                    hit = (r.stop, "STOP", ts)
                elif c.High >= r.target:
                    hit = (r.target, "TARGET", ts)
            else:
                if c.High >= r.stop:
                    hit = (r.stop, "STOP", ts)
                elif c.Low <= r.target:
                    hit = (r.target, "TARGET", ts)
            if hit:
                break
        if not hit and (day < d.index[-1].date() or dd.index[-1].time() >= dtime(15, 10)):
            hit = (float(dd.Close.iloc[-1]), "EOD", dd.index[-1])
        if hit:
            close_trade(i, hit[0], hit[1], hit[2].strftime("%H:%M"), cfg)
            done += 1
    return done


# ============================================================ sidebar
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    min_score = st.slider("Minimum score (Intraday)", 0, 100, 40, 5)
    both = st.radio("Side", ["Buy side only", "Buy and Sell side"], index=0) == "Buy and Sell side"
    risk_amt = st.number_input("Risk per trade (Rs)", 50, 100000, 500, 50)
    st.markdown("**BTST Scanner**")
    btst_min = st.slider("Minimum score (BTST)", 0, 100, 50, 5)
    brisk_amt = st.number_input("Risk per BTST trade (Rs)", 50, 100000, 500, 50)
    auto = st.checkbox("Auto refresh during market hours", True)
    show_why = st.checkbox("Show news and move reason", True)
    every = st.selectbox("Refresh every", ["1 minute", "2 minutes"], index=1)
    if st.button("Refresh now", width="stretch"):
        st.cache_data.clear()
        st.rerun(scope="app")
    with st.expander("Step 1 · Basic filter"):
        pmin = st.number_input("Price at least (Rs)", 1.0, 10000.0, 50.0, 10.0)
        pmax = st.number_input("Price at most (Rs)", 100.0, 100000.0, 5000.0, 100.0)
        min_vol = st.number_input("Average daily volume at least (shares)", 10000, 100000000, 500000, 50000)
        bmin_price = st.number_input("BTST: price at least (Rs)", 1.0, 10000.0, 100.0, 10.0)
        bmin_vol = st.number_input("BTST: average daily volume at least (shares)", 10000, 100000000, 1000000, 100000)
        wl = st.text_area("Stocks to scan (NSE symbols)", " ".join(UNIVERSE), height=120)
    with st.expander("Paper money"):
        capital = st.number_input("Paper capital (Rs)", 5000, 10000000, 100000, 5000)
        lev = st.number_input("Leverage (1 = none)", 1, 5, 1, 1)
        flat = st.number_input("Brokerage per order (Rs)", 0.0, 100.0, 20.0, 5.0)
        pct = st.number_input("Taxes and charges (% of turnover)", 0.0, 0.5, 0.04, 0.01)

P = dict(pmin=pmin, pmax=pmax, min_vol=min_vol, risk=risk_amt, capital=capital, lev=lev)
cfg = {"flat": flat, "pct": pct}
symbols = tuple(dict.fromkeys(s.strip().upper() for s in wl.replace("\n", " ").replace(",", " ").split() if s.strip()))
if "journal" not in st.session_state:
    st.session_state.journal = load_journal()

st.markdown("""<div class="hero"><h1>🎯 Intraday Hunter</h1>
<p>Every stock gets a score from 0 to 100. The best ones are always shown, even on a quiet day.</p></div>""",
            unsafe_allow_html=True)


def market_open():
    n = now_ist()
    return n.weekday() < 5 and dtime(9, 15) <= n.time() <= dtime(15, 30)


# ============================================================ page body (re-runs by itself during market hours)
def body():
    with st.expander("ℹ️ How it works", expanded=False):
        st.markdown("""
Each stock gets up to **100 points**:
- **Fast move (25):** how much it is up from yesterday's close. 1% = a little, 2% = medium, 3% or more = full.
- **Volume surge (25):** today's volume so far versus the normal volume at this same time of day. 1.5x = a little, 2x = medium, 3x or more = full.
- **Fresh breakout (30):** price just went above today's high so far, yesterday's high or the 20-day high. Full points if it happened in the last 5 candles (5 minutes each). Older breakouts get fewer points.
- **VWAP (10):** full points when price is above VWAP (below it on the sell side).
- **Strong candle (10):** the latest candle closes near its high with a good body and a short upper wick.

Only a light filter is used (price Rs 50 to 5000 and enough volume). The top 10 by score are shown. If none reach your minimum score, the best 5 are shown anyway.
**Trade plan:** entry just above the breakout level, stop just below it (or the last candle low), target 2x the risk. Shares = your risk amount divided by the risk per share.
Data is from Yahoo Finance and can be a few minutes late, so check your broker screen before acting. This is a learning tool, not advice.
""")

    with st.spinner("Getting prices (first load takes a little while)..."):
        try:
            data = fetch(symbols)
        except Exception as e:
            data = {}
            st.error(f"Could not get prices: {e}")
    if not data:
        st.warning("No price data came back from Yahoo Finance. Press Refresh now in a minute.")
        return

    last_candle = max(d.index[-1] for d in data.values())
    lag = (now_ist() - last_candle).total_seconds() / 60
    live = lag <= 20
    df, skipped = run_scan(data, P, both)

    c = st.columns(4)
    for col, val, lab in zip(c, [len(data), len(df), int((df.Score >= min_score).sum()) if len(df) else 0,
                                 now_ist().strftime("%H:%M:%S")],
                             ["Stocks scanned", "Passed basic filter", f"Score {min_score}+", "Last updated (IST)"]):
        col.markdown(f'<div class="kpi"><b>{val}</b><span>{lab.upper()}</span></div>', unsafe_allow_html=True)
    st.caption(f"Latest candle: {last_candle.strftime('%d %b, %H:%M')} IST"
               + (" · auto refresh is on" if (auto and live and market_open()) else ""))
    if not live:
        st.markdown(f'<div class="note">The market looks closed (latest candle is {int(lag)} minutes old). You are looking at the '
                    f'last session as a review. Levels are not live.</div>', unsafe_allow_html=True)

    tabs = st.tabs(["🏆 Top 10", "📋 All scores", "📈 Chart", "📒 Paper trades"])

    # -------------------------------------------------------- top 10
    with tabs[0]:
        if not len(df):
            st.info("No stock passed the basic filter. Try lowering the volume filter in the sidebar.")
        else:
            good = df[df.Score >= min_score].head(10)
            if len(good):
                top = good
            else:
                top = df.head(5)
                st.markdown('<div class="warn">Quiet market, showing best available.</div>', unsafe_allow_html=True)
            why = why_map(top, data, "intraday")
            cols = st.columns(3)
            for idx, (_, r) in enumerate(top.iterrows()):
                cls = "long" if r.Side == "LONG" else "short"
                chips = "".join(f"<span>{nm} {v:.0f}/{mx}</span>" for nm, v, mx in
                                [("Move", r.Move, 25), ("Volume", r.Volume, 25), ("Breakout", r.Breakout, 30),
                                 ("VWAP", r.VWAP, 10), ("Candle", r.Candle, 10)])
                brk = f"Breakout at {r['Break time']} ({r['Break level']})" if r["Break time"] != "-" else "No fresh breakout yet"
                html = f"""<div class="pick {cls}"><h3>#{idx + 1} {r.Symbol}<span class="pill {cls}">{r.Side}</span><span class="pill score">{r.Score:.0f}/100</span></h3>
                <div class="bar"><i style="width:{min(r.Score, 100):.0f}%"></i></div>
                <div class="sub"><span class="pill label" style="margin-left:0">{r.Label}</span> {brk}</div>
                <div class="grid"><div>Price<b>{r.LTP:.2f}</b></div><div>Change<b>{r["Chg %"]:+.2f}%</b></div><div>Volume<b>{r.VolX:.1f}x</b></div>
                <div>Entry<b>{r.Entry:.2f}</b></div><div>Stop<b>{r.Stop:.2f}</b></div><div>Target<b>{r.Target:.2f}</b></div></div>
                <div class="sub">Shares for Rs {risk_amt:,} risk: <b>{int(r.Qty)}</b> (risk Rs {r["Risk/sh"]:.2f} per share, reward 2x)</div>
                <div class="sub">Prev close: {r.PrevClose:.2f} ({r.PrevDate})</div>
                <div class="chips">{chips}</div>{why.get(r.Symbol, "")}</div>"""
                with cols[idx % 3]:
                    st.markdown(html, unsafe_allow_html=True)
                    if st.button("Paper trade this", key=f"pt_{r.Symbol}_{idx}"):
                        j = st.session_state.journal
                        if len(j[(j.symbol == r.Symbol) & (j.status == "OPEN")]):
                            st.warning("Already open.")
                        elif int(r.Qty) < 1:
                            st.warning("Quantity is 0 with your risk and capital settings.")
                        else:
                            add_trade(r.to_dict(), r.Label, "")
                            st.success("Saved. See the Paper trades tab.")
            st.caption("Score is for ranking only. It is not a chance of winning. Where the price has already moved past the level, entry is the current price.")
            why_notes()

    # -------------------------------------------------------- all scores
    with tabs[1]:
        if len(df):
            show = ["Symbol", "Side", "Score", "Label", "LTP", "Chg %", "VolX", "Break time", "Break level",
                    "Move", "Volume", "Breakout", "VWAP", "Candle"]
            st.dataframe(df[show], hide_index=True, width="stretch")
        if skipped:
            with st.expander(f"{len(skipped)} stock(s) skipped (filter or missing Yahoo data)"):
                st.write(", ".join(skipped))

    # -------------------------------------------------------- chart
    with tabs[2]:
        names = list(df.Symbol) if len(df) else []
        if not names:
            st.info("No data yet.")
        else:
            sym = st.selectbox("Stock", names)
            d = data[sym].copy()
            d["date"] = d.index.date
            days = sorted(set(d["date"]))[-2:]
            d = d[d["date"].isin(days)]
            t = d[d["date"] == days[-1]]
            typ = (d.High + d.Low + d.Close) / 3
            d["VWAP"] = (typ * d.Volume).groupby(d["date"]).cumsum() / d.Volume.groupby(d["date"]).cumsum().replace(0, np.nan)
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close, name="Price"))
            fig.add_trace(go.Scatter(x=d.index, y=d.VWAP, name="VWAP", line=dict(color="#f08c00", width=2)))
            row = df[df.Symbol == sym].iloc[0]
            for nm, col_ in (("Entry", "#1c7ed6"), ("Stop", "#e03131"), ("Target", "#14a44d")):
                fig.add_hline(y=float(row[nm]), line_dash="dash", line_color=col_, annotation_text=nm)
            fig.update_layout(height=580, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=20, b=10),
                              xaxis=dict(rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[15.5, 9.25], pattern="hour")]))
            st.plotly_chart(fig, width="stretch")

    # -------------------------------------------------------- paper trades and journal
    with tabs[3]:
        j = st.session_state.journal
        if st.button("Check open trades (stop / target)", type="primary"):
            n_ = check_open(data, cfg)
            if n_:
                st.success(f"{n_} trade(s) closed.")
            else:
                st.info("No open trade hit its stop or target yet.")
            j = st.session_state.journal
        op = j[j.status == "OPEN"]
        st.markdown(f"##### Open trades ({len(op)})")
        if len(op):
            ltp = {s: float(d.Close.iloc[-1]) for s, d in data.items()}
            o = op[["id", "date", "time", "symbol", "side", "entry", "stop", "target", "qty", "rank", "setup"]].copy()
            o["LTP"] = o.symbol.map(ltp)
            o["Open P&L"] = ((o.LTP - o.entry) * o.qty * o.side.map({"LONG": 1, "SHORT": -1})).round(0)
            st.dataframe(o.rename(columns={"rank": "score"}), hide_index=True, width="stretch")
            a, b, c_ = st.columns(3)
            cid = a.selectbox("Close trade #", list(op.id.astype(int)))
            px = b.number_input("Exit price", 0.0, 1000000.0, float(ltp.get(op[op.id == cid].symbol.iloc[0], 0.0)), 0.05)
            if c_.button("Close it now"):
                close_trade(j.index[j.id == cid][0], px, "MANUAL", now_ist().strftime("%H:%M"), cfg)
                st.rerun()
        else:
            st.caption("No open trades.")
        cl = j[j.status != "OPEN"].copy()
        st.markdown(f"##### Closed trades ({len(cl)})")
        if len(cl):
            for c_ in ("net", "gross", "costs", "r", "relvol", "rank"):
                cl[c_] = pd.to_numeric(cl[c_], errors="coerce")
            m = st.columns(6)
            m[0].metric("Trades", len(cl))
            m[1].metric("Wins", int((cl.net > 0).sum()))
            m[2].metric("Losses", int((cl.net <= 0).sum()))
            m[3].metric("Win rate", f"{(cl.net > 0).mean() * 100:.0f}%")
            m[4].metric("Net P&L (Rs)", f"{cl.net.sum():,.0f}")
            m[5].metric("Average R", f"{cl.r.mean():.2f}")
            st.line_chart(cl.sort_values(["date", "time"]).net.cumsum().reset_index(drop=True), height=200)
            # Which setup worked best (Fresh breakout, Fast mover, ...)
            cl["setup"] = cl["setup"].replace("", "Other")
            g = cl.groupby("setup").agg(Trades=("net", "size"), Wins=("net", lambda x: int((x > 0).sum())),
                                        Net_PnL=("net", "sum"), Avg_R=("r", "mean")).reset_index()
            g["Win rate %"] = (g.Wins / g.Trades * 100).round(0)
            g = g.sort_values("Net_PnL", ascending=False)
            st.markdown("##### Which setup worked best")
            st.dataframe(g.rename(columns={"setup": "Setup", "Net_PnL": "Net P&L (Rs)", "Avg_R": "Avg R"}).round(2),
                         hide_index=True, width="stretch")
            if len(g):
                st.success(f"Best so far: {g.iloc[0]['setup']} (net Rs {g.iloc[0]['Net_PnL']:,.0f} over {int(g.iloc[0]['Trades'])} trade(s)).")
            edited = st.data_editor(cl.sort_values("id", ascending=False), hide_index=True, width="stretch",
                                    disabled=[c_ for c_ in COLS if c_ not in ("setup", "note")], key="ed")
            if st.button("Save my setup / note edits"):
                jj = st.session_state.journal
                for _, r in edited.iterrows():
                    kx = jj.index[jj.id == r["id"]]
                    jj.loc[kx, "setup"], jj.loc[kx, "note"] = r["setup"], r["note"]
                st.session_state.journal = jj
                save_journal()
                st.success("Saved.")
        st.markdown("##### Keep your journal safe")
        d1, d2 = st.columns(2)
        d1.download_button("Download journal (CSV)", st.session_state.journal.to_csv(index=False), "journal.csv", "text/csv")
        up = d2.file_uploader("Restore journal (CSV)", type="csv")
        if up is not None and st.button("Load this file"):
            st.session_state.journal = norm(pd.read_csv(up))
            save_journal()
            st.rerun()
        st.caption("Streamlit Cloud can reset saved files when the app restarts. Download your journal every evening.")


# ============================================================ BTST SCANNER (Buy Today, Sell Tomorrow)
# Uses DAILY candles. Best used between 2:30 PM and 3:25 PM IST, when today's candle is almost complete.
BTST_UNIVERSE = """RELIANCE TCS HDFCBANK ICICIBANK INFY BHARTIARTL ITC SBIN LT KOTAKBANK HINDUNILVR AXISBANK BAJFINANCE
ASIANPAINT MARUTI SUNPHARMA TITAN ULTRACEMCO NTPC ONGC POWERGRID TATASTEEL JSWSTEEL HCLTECH WIPRO TECHM ADANIPORTS
COALINDIA BAJAJFINSV NESTLEIND GRASIM HINDALCO CIPLA DRREDDY EICHERMOT BPCL HEROMOTOCO INDUSINDBK TATACONSUM APOLLOHOSP
SBILIFE HDFCLIFE BRITANNIA DIVISLAB SHRIRAMFIN TRENT BEL PNB BANKBARODA CANBK IOC GAIL VEDL DLF HAL RECLTD PFC
M&M BAJAJ-AUTO TATAMOTORS ADANIENT ADANIPOWER ADANIGREEN AMBUJACEM DABUR GODREJCP MARICO PIDILITIND HAVELLS SIEMENS ABB
CGPOWER POLYCAB BHARATFORG MOTHERSON BOSCHLTD ASHOKLEY TVSMOTOR JINDALSTEL JSWENERGY TATAPOWER NHPC LUPIN AUROPHARMA
ZYDUSLIFE TORNTPHARM MAXHEALTH PERSISTENT COFORGE MPHASIS LTIM FEDERALBNK AUBANK IDFCFIRSTB CHOLAFIN MUTHOOTFIN
HDFCAMC ICICIGI ICICIPRULI LICI JIOFIN SBICARD ZOMATO ETERNAL DMART VBL UNITDSPR INDIGO IRCTC IRFC LODHA GODREJPROP
OBEROIRLTY UPL SRF PIIND NAUKRI MAZDOCK COCHINSHIP BDL BHEL CUMMINS VOLTAS DIXON UNIONBANK INDIANB""".split()
BTST_COLS = ["id", "date", "symbol", "buy", "stop", "target", "qty", "score", "status", "exit", "exit_date", "gross",
             "costs", "net", "r", "label", "note"]


def _clean_daily(raw, t, many):
    """Same cleaning as the intraday data, but daily candles keep plain dates."""
    d = clean(raw, t, many)
    return d


@st.cache_data(ttl=300, show_spinner=False)
def fetch_daily(symbols):
    """About 6 months of daily candles (enough for the 50-day average). Bad batches or symbols are skipped."""
    out = {}
    for i in range(0, len(symbols), CHUNK):
        part = symbols[i:i + CHUNK]
        tick = [s + ".NS" for s in part]
        try:
            raw = yf.download(tick, period="6mo", interval="1d", group_by="ticker",
                              auto_adjust=False, progress=False, threads=True)
        except Exception:
            continue
        for s, t in zip(part, tick):
            d = clean(raw, t, len(tick) > 1)
            if d is not None:
                d = d.dropna(subset=["Open", "High", "Low", "Close"]).copy()
                d["Volume"] = d["Volume"].fillna(0)
            if d is not None and len(d) > 55:
                out[s] = d
    return out


@st.cache_data(ttl=300, show_spinner=False)
def fetch_nifty():
    """Nifty 50 daily candles for the market mood score. Returns None if Yahoo fails."""
    try:
        raw = yf.download("^NSEI", period="6mo", interval="1d", auto_adjust=False, progress=False)
        return clean(raw, "^NSEI", False)
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def result_due(sym, today_str):
    """True if Yahoo shows results (earnings) today or on the next trading day. If the data is not available
    (common for Indian stocks) we return False, which means 'ignore this rule'."""
    try:
        cal = yf.Ticker(sym + ".NS").calendar
        dates = cal.get("Earnings Date", []) if isinstance(cal, dict) else []
        today = pd.Timestamp(today_str).date()
        nxt = (pd.Timestamp(today) + pd.offsets.BDay(1)).date()
        return any(pd.Timestamp(x).date() in (today, nxt) for x in dates)
    except Exception:
        return False


def late_day(d5, chg):
    """Late-day strength penalties from today's 5-minute candles. Returns None when 5-minute data is not usable."""
    try:
        if d5 is None or len(d5) < 25:
            return None
        day = d5.index[-1].date()
        t = d5[[i.date() == day for i in d5.index]]
        if len(t) < 13:
            return None
        c = t.Close.to_numpy(float)
        h = t.High.to_numpy(float)
        o = t.Open.to_numpy(float)
        last = float(c[-1])
        pen, notes = 0, []
        vol = t.Volume.to_numpy(float)
        typ = (t.High.to_numpy(float) + t.Low.to_numpy(float) + c) / 3
        vwap = float((typ * vol).sum() / vol.sum()) if vol.sum() > 0 else float(typ.mean())
        if last < vwap:
            pen += 15
            notes.append("below VWAP -15")
        ma20 = float(d5.Close.to_numpy(float)[-20:].mean())
        if last < ma20:
            pen += 10
            notes.append("below 5-min 20 MA -10")
        h12 = h[-12:]
        lower_highs = h12[:4].max() > h12[4:8].max() > h12[8:].max()
        hour_down = c[-1] < o[-12]
        if lower_highs or hour_down:
            pen += 10
            notes.append("last hour weak -10")
        day_high = float(h.max())
        off = (day_high - last) / day_high * 100 if day_high > 0 else 0.0
        if off > 3:
            pen += 20
            notes.append(f"{off:.1f}% below day high -20")
        elif off > 1.5:
            pen += 10
            notes.append(f"{off:.1f}% below day high -10")
        ext = chg > 6
        if ext:
            pen += 5
            notes.append("extended move -5")
        core = pen - (5 if ext else 0)
        tag = "Closing strong" if core == 0 else ("Fading" if core <= 20 else "Weak close")
        return {"pen": pen, "tag": tag, "ext": ext, "notes": ", ".join(notes)}
    except Exception:
        return None


def btst_score(sym, d, P, mood_pts):
    """Score one stock 0-100 on its daily candles. Returns None if it fails the light filter."""
    d = d.copy()
    if len(d) < 52:
        return None
    c, h, l, v = (d[x].to_numpy(float) for x in ("Close", "High", "Low", "Volume"))
    close, hi, lo = c[-1], h[-1], l[-1]
    avg_vol = float(np.mean(v[-21:-1]))
    # Step 1: liquid and above Rs 100 only
    if close < P["bmin_price"] or avg_vol < P["bmin_vol"] or close <= 0:
        return None
    chg = (close / c[-2] - 1) * 100

    # Strong close (25): top 20% of the day's range or better. Closer to the high = more points.
    rng = hi - lo
    pos = (close - lo) / rng if rng > 0 else 0.0
    p_close = ramp(pos, [0.6, 0.8, 1.0], [0, 15, 25])

    # Volume expansion (25): today's volume vs the 20-day average (before today)
    vx = float(v[-1] / avg_vol) if avg_vol > 0 else 0.0
    p_vol = ramp(vx, [0, 1, 1.5, 2, 3], [0, 0, 8, 17, 25])

    # Breakout (25): at or above the 20-day high = fresh today. Yesterday's breakout = a bit less, older = less.
    # Broke above the highest high of the last 5 sessions today = smaller 'recent resistance' breakout.
    h20 = h[-21:-1].max()
    p_brk, brk_txt = 0.0, "no breakout"
    if close >= h20:
        p_brk, brk_txt = 25.0, f"at 20-day high {h20:.2f} (today)"
    else:
        h20_y = h[-22:-2].max()
        if c[-2] >= h20_y and close >= h20_y:
            p_brk, brk_txt = 20.0, f"broke 20-day high {h20_y:.2f} yesterday"
        else:
            for back in range(3, 7):  # 3 to 6 sessions ago = older breakout, only if still holding above it
                lvl = h[-21 - back + 1:-1 - back + 1].max()
                if c[-back] >= lvl and close >= lvl:
                    p_brk, brk_txt = 10.0, f"20-day high {lvl:.2f} broken {back - 1} days ago"
                    break
    if p_brk < 12 and close > h[-6:-1].max():
        p_brk, brk_txt = max(p_brk, 12.0), f"above 5-day resistance {h[-6:-1].max():.2f} today"

    # Trend support (15): above the 20-day and 50-day averages
    sma20, sma50 = c[-20:].mean(), c[-50:].mean()
    p_trend = (7.5 if close > sma20 else 0.0) + (7.5 if close > sma50 else 0.0)

    total = p_close + p_vol + p_brk + p_trend + mood_pts

    if p_brk >= 20 and p_vol >= 17:
        label = "Breakout + volume"
    elif p_brk >= 20:
        label = "Fresh breakout"
    elif p_close >= 15 and p_vol >= 17:
        label = "Strong close + volume"
    elif p_close >= 15:
        label = "Strong close"
    else:
        label = "Weak setup"

    # Trade plan: stop = below today's low or 2% below buy, whichever is closer to the buy price
    buy = close
    stop = max(lo, buy * 0.98)
    if stop >= buy:
        stop = buy * 0.98
    risk = buy - stop
    target = buy + 2 * risk
    qty = int(max(0, min(P["brisk"] // risk, P["capital"] * P["lev"] // buy))) if risk > 0 else 0
    return {"Symbol": sym, "PrevClose": round(float(c[-2]), 2), "PrevDate": d.index[-2].strftime("%a %d %b"),
            "Close": round(float(close), 2), "Chg %": round(float(chg), 2), "VolX": round(vx, 2),
            "Range %": round(float(pos * 100), 0), "Score": round(float(total), 1), "Label": label, "Breakout": brk_txt,
            "Close pts": round(p_close, 1), "Volume pts": round(p_vol, 1), "Break pts": round(p_brk, 1),
            "Trend pts": round(p_trend, 1), "Mood pts": mood_pts,
            "Buy": round(float(buy), 2), "Stop": round(float(stop), 2), "Target": round(float(target), 2),
            "Qty": qty, "Risk/sh": round(float(risk), 2), "_date": d.index[-1].strftime("%Y-%m-%d")}


# ============================================================ "WHY IS IT MOVING?" (market vs stock check + news)
# Part 1 compares the stock with the Nifty and with its sector peers. Part 2 reads free public headlines.
# Everything here is wrapped so a failure only hides the section; the card itself always loads.
import html as _html
import re
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from datetime import timezone

NSE_ANN = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"

# Peer groups (used for the sector check). A stock not listed here simply skips the sector part.
SECTORS = {
    "Bank": "HDFCBANK ICICIBANK SBIN KOTAKBANK AXISBANK INDUSINDBK PNB BANKBARODA CANBK FEDERALBNK AUBANK IDFCFIRSTB BANDHANBNK UNIONBANK INDIANB RBLBANK YESBANK",
    "IT": "TCS INFY HCLTECH WIPRO TECHM LTIM PERSISTENT COFORGE MPHASIS OFSS KPITTECH TATAELXSI LTTS",
    "FMCG": "HINDUNILVR ITC NESTLEIND BRITANNIA DABUR GODREJCP MARICO COLPAL TATACONSUM VBL UBL PGHH PATANJALI",
    "Auto": "MARUTI M&M BAJAJ-AUTO EICHERMOT HEROMOTOCO TVSMOTOR ASHOKLEY TATAMOTORS BALKRISIND MRF BOSCHLTD MOTHERSON",
    "Pharma": "SUNPHARMA CIPLA DRREDDY LUPIN AUROPHARMA ZYDUSLIFE TORNTPHARM DIVISLAB ALKEM MANKIND BIOCON GLENMARK LAURUSLABS",
    "Metal": "TATASTEEL JSWSTEEL HINDALCO VEDL JINDALSTEL SAIL NMDC NATIONALUM HINDZINC APLAPOLLO JSL",
    "Energy": "RELIANCE ONGC BPCL IOC GAIL COALINDIA NTPC POWERGRID TATAPOWER ADANIPOWER ADANIGREEN NHPC JSWENERGY OIL HINDPETRO PETRONET",
    "Finance": "BAJFINANCE BAJAJFINSV SHRIRAMFIN CHOLAFIN MUTHOOTFIN RECLTD PFC SBILIFE HDFCLIFE ICICIGI ICICIPRULI HDFCAMC SBICARD LICI JIOFIN",
    "Realty": "DLF LODHA GODREJPROP OBEROIRLTY PRESTIGE PHOENIXLTD BRIGADE",
    "Capital goods": "LT SIEMENS ABB CGPOWER POLYCAB HAVELLS BHEL CUMMINS BEL HAL BDL MAZDOCK COCHINSHIP VOLTAS DIXON",
}
SECTOR_OF = {s: sec for sec, names in SECTORS.items() for s in names.split()}

NAMES = {
    "RELIANCE": "Reliance Industries", "TCS": "TCS Tata Consultancy", "HDFCBANK": "HDFC Bank", "ICICIBANK": "ICICI Bank",
    "INFY": "Infosys", "BHARTIARTL": "Bharti Airtel", "ITC": "ITC Ltd", "SBIN": "State Bank of India", "LT": "Larsen & Toubro",
    "KOTAKBANK": "Kotak Mahindra Bank", "HINDUNILVR": "Hindustan Unilever", "AXISBANK": "Axis Bank", "BAJFINANCE": "Bajaj Finance",
    "ASIANPAINT": "Asian Paints", "MARUTI": "Maruti Suzuki", "SUNPHARMA": "Sun Pharma", "TITAN": "Titan Company",
    "ULTRACEMCO": "UltraTech Cement", "NTPC": "NTPC", "ONGC": "ONGC", "POWERGRID": "Power Grid", "TATASTEEL": "Tata Steel",
    "JSWSTEEL": "JSW Steel", "HCLTECH": "HCL Technologies", "WIPRO": "Wipro", "TECHM": "Tech Mahindra", "ADANIPORTS": "Adani Ports",
    "COALINDIA": "Coal India", "BAJAJFINSV": "Bajaj Finserv", "NESTLEIND": "Nestle India", "GRASIM": "Grasim", "HINDALCO": "Hindalco",
    "CIPLA": "Cipla", "DRREDDY": "Dr Reddys", "EICHERMOT": "Eicher Motors", "BPCL": "BPCL", "HEROMOTOCO": "Hero MotoCorp",
    "INDUSINDBK": "IndusInd Bank", "TATACONSUM": "Tata Consumer", "APOLLOHOSP": "Apollo Hospitals", "SBILIFE": "SBI Life",
    "HDFCLIFE": "HDFC Life", "BRITANNIA": "Britannia", "DIVISLAB": "Divis Laboratories", "SHRIRAMFIN": "Shriram Finance",
    "TRENT": "Trent", "BEL": "Bharat Electronics", "PNB": "Punjab National Bank", "BANKBARODA": "Bank of Baroda", "CANBK": "Canara Bank",
    "IOC": "Indian Oil", "GAIL": "GAIL India", "VEDL": "Vedanta", "DLF": "DLF", "HAL": "Hindustan Aeronautics", "RECLTD": "REC Ltd",
    "PFC": "Power Finance Corporation", "SAIL": "SAIL Steel Authority", "NMDC": "NMDC", "IDFCFIRSTB": "IDFC First Bank",
    "M&M": "Mahindra & Mahindra", "BAJAJ-AUTO": "Bajaj Auto", "TATAMOTORS": "Tata Motors", "ADANIENT": "Adani Enterprises",
    "ADANIPOWER": "Adani Power", "ADANIGREEN": "Adani Green", "AMBUJACEM": "Ambuja Cements", "DABUR": "Dabur", "GODREJCP": "Godrej Consumer",
    "MARICO": "Marico", "PIDILITIND": "Pidilite", "HAVELLS": "Havells", "SIEMENS": "Siemens India", "ABB": "ABB India",
    "CGPOWER": "CG Power", "POLYCAB": "Polycab", "BHARATFORG": "Bharat Forge", "MOTHERSON": "Samvardhana Motherson",
    "BOSCHLTD": "Bosch Ltd", "ASHOKLEY": "Ashok Leyland", "TVSMOTOR": "TVS Motor", "JINDALSTEL": "Jindal Steel", "JSWENERGY": "JSW Energy",
    "TATAPOWER": "Tata Power", "NHPC": "NHPC", "LUPIN": "Lupin", "AUROPHARMA": "Aurobindo Pharma", "ZYDUSLIFE": "Zydus Lifesciences",
    "TORNTPHARM": "Torrent Pharma", "MAXHEALTH": "Max Healthcare", "PERSISTENT": "Persistent Systems", "COFORGE": "Coforge",
    "MPHASIS": "Mphasis", "LTIM": "LTIMindtree", "FEDERALBNK": "Federal Bank", "AUBANK": "AU Small Finance Bank", "CHOLAFIN": "Chola Finance",
    "MUTHOOTFIN": "Muthoot Finance", "HDFCAMC": "HDFC AMC", "ICICIGI": "ICICI Lombard", "ICICIPRULI": "ICICI Prudential Life",
    "LICI": "LIC India", "JIOFIN": "Jio Financial", "SBICARD": "SBI Cards", "ZOMATO": "Zomato", "ETERNAL": "Eternal Zomato", "DMART": "DMart Avenue Supermarts",
    "VBL": "Varun Beverages", "UNITDSPR": "United Spirits", "INDIGO": "InterGlobe IndiGo", "IRCTC": "IRCTC", "IRFC": "IRFC",
    "LODHA": "Lodha Macrotech", "GODREJPROP": "Godrej Properties", "OBEROIRLTY": "Oberoi Realty", "UPL": "UPL", "SRF": "SRF",
    "PIIND": "PI Industries", "NAUKRI": "Info Edge Naukri", "MAZDOCK": "Mazagon Dock", "COCHINSHIP": "Cochin Shipyard", "BDL": "Bharat Dynamics",
    "BHEL": "BHEL", "CUMMINS": "Cummins India", "VOLTAS": "Voltas", "DIXON": "Dixon Technologies", "UNIONBANK": "Union Bank of India",
    "INDIANB": "Indian Bank", "JUBLFOOD": "Jubilant FoodWorks", "KALYANKJIL": "Kalyan Jewellers", "PAYTM": "Paytm One97", "NYKAA": "Nykaa FSN",
    "TATAELXSI": "Tata Elxsi", "OFSS": "Oracle Financial Services", "ABCAPITAL": "Aditya Birla Capital", "YESBANK": "Yes Bank",
    "RBLBANK": "RBL Bank", "BANDHANBNK": "Bandhan Bank", "IDEA": "Vodafone Idea", "TATACOMM": "Tata Communications", "PATANJALI": "Patanjali Foods",
}

# keyword -> label (simple matching, first match wins)
TAGS = [
    ("Results/Earnings", r"result|earnings|q[1-4]\b|quarter|profit|net income|revenue|ebitda"),
    ("Order win/Contract", r"order|contract|bags|wins|secures|awarded|deal worth"),
    ("Upgrade/Target price", r"upgrade|target price|raises target|buy rating|initiates coverage|outperform|overweight"),
    ("Downgrade", r"downgrade|cuts target|sell rating|underperform|underweight"),
    ("Block/Bulk deal", r"block deal|bulk deal|stake sale|offloads|picks up stake"),
    ("Dividend/Bonus/Split", r"dividend|bonus|stock split|record date|buyback"),
    ("Acquisition/Merger", r"acqui|merger|takeover|buys stake|demerger"),
    ("Regulatory/Fraud/Probe", r"sebi|probe|fraud|penalty|raid|investigation|notice|ed |cbi|ban\b"),
    ("Management change", r"resign|appoints|appointed|steps down|new ceo|new md|cfo|chairman"),
]

_NEWS_CACHE = {}
_NEWS_LOCK = threading.Lock()
NEWS_TTL = 600  # cache news for 10 minutes


def tag_headline(title):
    t = title.lower()
    for label, pat in TAGS:
        if re.search(pat, t):
            return label
    return ""


def _http_get(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; IntradayHunter/3)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _relevant(title, sym, name):
    t = title.lower()
    first = name.split()[0].lower() if name else ""
    return (len(first) >= 3 and first in t) or sym.lower() in t


def _google_news(sym, name):
    q = f'"{name}" (NSE OR share OR stock) when:2d'
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    root = ET.fromstring(_http_get(url))
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src = (it.findtext("source") or "").strip()
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        pub = it.findtext("pubDate")
        when = parsedate_to_datetime(pub).astimezone(timezone.utc) if pub else None
        if title and when is not None and _relevant(title, sym, name):
            out.append({"title": title, "link": it.findtext("link") or "", "source": src or "Google News", "when": when})
    return out


def _yahoo_news(sym, name):
    items = yf.Ticker(sym + ".NS").news or []
    out = []
    for it in items:
        c = it.get("content") or it
        title = (c.get("title") or "").strip()
        link = ((c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or c.get("link") or "")
        src = (c.get("provider") or {}).get("displayName") or c.get("publisher") or "Yahoo Finance"
        pub = c.get("pubDate") or c.get("displayTime")
        if pub:
            when = pd.Timestamp(pub).tz_convert("UTC") if pd.Timestamp(pub).tzinfo else pd.Timestamp(pub, tz="UTC")
        elif c.get("providerPublishTime"):
            when = pd.Timestamp(int(c["providerPublishTime"]), unit="s", tz="UTC")
        else:
            continue
        if title:
            out.append({"title": title, "link": link, "source": src, "when": when.to_pydatetime()})
    return out


def get_news(sym):
    """Top 3 headlines from the last 48 hours. Google News first, then Yahoo. Any failure is skipped silently.
    Results are cached for 10 minutes. Runs in worker threads, so it does not use st.* calls."""
    now = _time.time()
    with _NEWS_LOCK:
        hit = _NEWS_CACHE.get(sym)
        if hit and now - hit[0] < NEWS_TTL:
            return hit[1]
    name = NAMES.get(sym, sym)
    items = []
    for fn in (_google_news, _yahoo_news):
        try:
            items = fn(sym, name)
        except Exception:
            items = []
        cutoff = datetime.now(timezone.utc).timestamp() - 48 * 3600
        items = [i for i in items if i["when"].timestamp() >= cutoff]
        if items:
            break
    items.sort(key=lambda i: i["when"], reverse=True)
    seen, res = set(), []
    for i in items:
        key = i["title"].lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        age_h = (datetime.now(timezone.utc).timestamp() - i["when"].timestamp()) / 3600
        res.append({"title": i["title"], "link": i["link"], "source": i["source"], "age_h": max(age_h, 0),
                    "tag": tag_headline(i["title"])})
        if len(res) == 3:
            break
    with _NEWS_LOCK:
        _NEWS_CACHE[sym] = (now, res)
    return res


def ago(h):
    if h < 1:
        return f"{max(int(h * 60), 1)}m ago"
    if h < 48:
        return f"{int(h)}h ago"
    return f"{int(h // 24)}d ago"


def pct_change_map(data, kind):
    """Today's % change for every loaded stock (used for the sector peer check)."""
    out = {}
    for sym, d in data.items():
        try:
            if kind == "daily":
                c = d.Close.to_numpy(float)
                out[sym] = (c[-1] / c[-2] - 1) * 100
            else:
                days = d.index.date
                prev = d.Close[days != days[-1]]
                out[sym] = (float(d.Close.iloc[-1]) / float(prev.iloc[-1]) - 1) * 100
        except Exception:
            continue
    return out


def nifty_pct():
    try:
        n = fetch_nifty()
        c = n.Close.to_numpy(float)
        return float((c[-1] / c[-2] - 1) * 100)
    except Exception:
        return None


def sector_pct(sym, pmap):
    """Median % change of the other stocks in the same sector (needs at least 2 peers)."""
    sec = SECTOR_OF.get(sym)
    if not sec:
        return None, None
    peers = [pmap[p] for p in SECTORS[sec].split() if p != sym and p in pmap]
    if len(peers) < 2:
        return None, None
    return float(np.median(peers)), sec


def classify(c, n, s):
    """Market-driven / Sector-driven / Stock-specific. d = +1 for an up move, -1 for a down move."""
    if n is None:
        return "Mixed signals"
    d = 1 if c >= 0 else -1
    if abs(c - n) <= 1.0:
        return "Market-driven"
    if s is not None and d * s >= 1.0 and d * (c - s) < 1.0:
        return "Sector-driven"
    if d * (c - n) >= 2.0 and (s is None or d * (c - s) >= 1.0):
        return "Stock-specific"
    return "Mixed signals"


def why_html(sym, c, n, s, sec, news, show_news=True):
    label = classify(c, n, s)
    nums = [f"Stock {c:+.1f}%"]
    if n is not None:
        nums.append(f"Nifty {n:+.1f}%")
    if s is not None:
        nums.append(f"{sec} peers {s:+.1f}%")
    if news:
        top = next((x for x in news if x["tag"]), news[0])
        reason = top["tag"] or _html.escape(top["title"][:70])
        reason = f"{reason} headline ({ago(top['age_h'])})" if top["tag"] else f"{reason} ({ago(top['age_h'])})"
        summary = f"{label} move. Possible reason: {reason}."
    elif label == "Stock-specific":
        summary = "Stock-specific move, but no news found. Check NSE announcements before trading."
    elif label in ("Market-driven", "Sector-driven"):
        summary = f"{label} move. No fresh news found."
    else:
        summary = "No clear driver found. No fresh news found." if show_news else "No clear driver found."
    h = f'<div class="why"><b>Why is it moving?</b> <span class="pill label" style="margin-left:4px">{label}</span>'
    h += f'<div class="sub">{" | ".join(nums)}</div><div>{summary}</div>'
    if show_news:
        if news:
            for x in news:
                tag = f'<i class="tg">{x["tag"]}</i> ' if x["tag"] else ""
                url = _html.escape(x["link"], quote=True)
                h += (f'<div class="nw">{tag}<a href="{url}" target="_blank" rel="noopener noreferrer">{_html.escape(x["title"][:110])}</a>'
                      f' <span class="sub">{_html.escape(x["source"])}, {ago(x["age_h"])}</span></div>')
        else:
            h += '<div class="sub">No fresh news found. Move may be market or sector driven.</div>'
    h += f'<div class="sub"><a href="{NSE_ANN}" target="_blank" rel="noopener noreferrer">NSE corporate announcements</a></div></div>'
    return h


def why_map(top, data, kind):
    """Build the 'Why is it moving?' block for each card in `top` (a DataFrame of the cards shown).
    News is only fetched for these top stocks. Returns {} if the switch is off or anything fails."""
    if not show_why or not len(top):
        return {}
    try:
        n = nifty_pct()
        pmap = pct_change_map(data, kind)
        syms = list(top.Symbol)
        news = {}
        try:
            with ThreadPoolExecutor(max_workers=5) as ex:
                futs = {s: ex.submit(get_news, s) for s in syms}
                for s, f in futs.items():
                    try:
                        news[s] = f.result(timeout=8)
                    except Exception:
                        news[s] = []
        except Exception:
            news = {}
        out = {}
        for _, r in top.iterrows():
            try:
                sp, sec = sector_pct(r.Symbol, pmap)
                out[r.Symbol] = why_html(r.Symbol, float(r["Chg %"]), n, sp, sec, news.get(r.Symbol, []))
            except Exception:
                continue
        return out
    except Exception:
        return {}


def why_notes():
    """Small warning note and the 'How the move reason works' box."""
    if not show_why:
        return
    st.caption("News is fetched from free public sources and can be delayed or incomplete. Always check NSE/BSE announcements "
               "and company results dates before taking a trade.")
    with st.expander("ℹ️ How the move reason works", expanded=False):
        st.markdown("""
Each top card compares the stock's move today with the **Nifty 50** and with its **sector peers** (the middle move of other stocks in the same sector in this scan):
- **Market-driven:** the stock moved within about 1 point of the Nifty.
- **Sector-driven:** its sector peers moved clearly the same way (1 point or more) and the stock is not far ahead of them.
- **Stock-specific:** the stock beat the Nifty by 2 points or more and also beat its sector by at least 1 point.
- **Mixed signals:** none of the above fits.

For the top stocks only, the latest headlines from the last 48 hours are read from Google News (then Yahoo Finance). Each headline gets a simple keyword tag, like Results or Order win. The one-line summary only says a **possible reason**, never a fact. Turn this off with the sidebar switch if the app feels slow.
""")


# ---- BTST journal (separate from the intraday journal, saved in its own file)
def btst_norm(df):
    for c_ in BTST_COLS:
        if c_ not in df.columns:
            df[c_] = np.nan
    df = df[BTST_COLS].copy()
    for c_ in ("date", "symbol", "status", "exit_date", "label", "note"):
        df[c_] = df[c_].fillna("").astype(str)
    for c_ in ("id", "buy", "stop", "target", "qty", "score", "exit", "gross", "costs", "net", "r"):
        df[c_] = pd.to_numeric(df[c_], errors="coerce")
    return df


def btst_load():
    if os.path.exists(BTST_JOURNAL):
        try:
            return btst_norm(pd.read_csv(BTST_JOURNAL))
        except Exception:
            pass
    return btst_norm(pd.DataFrame(columns=BTST_COLS))


def btst_save():
    try:
        st.session_state.btst_journal.to_csv(BTST_JOURNAL, index=False)
    except Exception:
        pass


def btst_add(r):
    j = st.session_state.btst_journal
    nid = int(pd.to_numeric(j["id"], errors="coerce").max() + 1) if len(j) else 1
    new = {"id": nid, "date": r["_date"], "symbol": r["Symbol"], "buy": r["Buy"], "stop": r["Stop"], "target": r["Target"],
           "qty": r["Qty"], "score": r["Score"], "status": "OPEN", "label": r["Label"]}
    st.session_state.btst_journal = btst_norm(pd.concat([j, pd.DataFrame([new])], ignore_index=True))
    btst_save()


def btst_close(i, price, when):
    j = st.session_state.btst_journal
    r = j.loc[i]
    q = float(r.qty)
    gross = (price - r.buy) * q
    costs = 2 * cfg["flat"] + cfg["pct"] / 100 * (r.buy + price) * q
    risk = (r.buy - r.stop) * q
    j.loc[i, ["status", "exit", "exit_date"]] = ["CLOSED", round(price, 2), when]
    j.loc[i, ["gross", "costs", "net"]] = [round(gross, 2), round(costs, 2), round(gross - costs, 2)]
    j.loc[i, "r"] = round((gross - costs) / risk, 2) if risk > 0 else np.nan
    st.session_state.btst_journal = j
    btst_save()


def _btst_body():
    if "btst_journal" not in st.session_state:
        st.session_state.btst_journal = btst_load()
    st.markdown('<div class="warn"><b>BTST carries overnight risk.</b> News or global markets can make the stock open lower '
                'than your stop-loss. Use small size.</div>', unsafe_allow_html=True)
    st.markdown('<div class="note">Use <b>CNC (delivery)</b> product to buy, and sell it the next day. Check your broker\'s BTST rules '
                'and short-delivery penalty. This tool is for paper trading and learning, and is not investment advice.</div>',
                unsafe_allow_html=True)
    with st.expander("ℹ️ How the BTST score works", expanded=False):
        st.markdown("""
Best used between **2:30 PM and 3:25 PM IST**, when today's candle is almost finished. Each stock gets up to **100 points**:
- **Strong close (25):** price is in the top 20% of today's high-low range. Closer to the day high = more points.
- **Volume expansion (25):** today's volume versus the 20-day average. 1.5x = a little, 2x = medium, 3x or more = full. (Early in the day volume looks low because the day is not finished.)
- **Breakout (25):** price is at or above the 20-day high (full points), broke it yesterday (20), broke it a few days ago and holds (10), or just cleared the last 5 days' high (12).
- **Trend support (15):** price above the 20-day average (7.5) and the 50-day average (7.5).
- **Late-day penalties (from 5-minute candles, taken off the score):** price below today's VWAP -15; below the 5-minute 20 average -10; last hour makes lower highs or closes below where it opened -10; more than 1.5% below the day high -10 (more than 3% -20); up more than 6% today -5 and tagged "Extended move". Card tag: **Closing strong** (no penalty), **Fading** (some), **Weak close** (heavy). If 5-minute data is missing for a stock, no penalty is applied and the card says so.
- **Market mood (10):** the Nifty 50 is up today or above its 20-day average. If not, 0 points and a warning.

Only large liquid stocks above Rs 100 are scanned. Stocks with results due today or tomorrow are skipped when Yahoo shows that date (it often does not for Indian stocks, so check news yourself).
**Plan:** buy near the close. Stop = below today's low or 2% under the buy price, whichever is closer. Target = 2x the risk. Plan to sell in the first 30 to 60 minutes next morning, or at the stop.
""")
    top_c = st.columns([1, 3])
    if top_c[0].button("Refresh BTST data", key="bt_refresh"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("Getting daily prices..."):
        try:
            ddata = fetch_daily(tuple(BTST_UNIVERSE))
        except Exception as e:
            ddata = {}
            st.error(f"Could not get prices: {e}")
        nifty = fetch_nifty()
    if not ddata:
        st.warning("No daily data came back from Yahoo Finance. Press Refresh BTST data in a minute.")
        return

    # Market mood (10): Nifty up today OR above its 20-day average
    mood_pts, nifty_txt = 0.0, "Nifty data not available"
    if nifty is not None and len(nifty) > 21:
        nc = nifty.Close.to_numpy(float)
        up = nc[-1] > nc[-2]
        above = nc[-1] > nc[-20:].mean()
        mood_pts = 10.0 if (up or above) else 0.0
        nifty_txt = f"Nifty {nc[-1]:,.0f} ({(nc[-1] / nc[-2] - 1) * 100:+.2f}% today, {'above' if above else 'below'} its 20-day average)"
        if mood_pts == 0:
            st.markdown('<div class="warn"><b>Market is weak today, be careful with BTST.</b></div>', unsafe_allow_html=True)
    else:
        st.info("Nifty 50 data is not available right now, so market mood gets 0 points.")

    latest = max(d.index[-1] for d in ddata.values())
    try:
        d5all = fetch(tuple(BTST_UNIVERSE))
    except Exception:
        d5all = {}
    P2 = dict(bmin_price=bmin_price, bmin_vol=bmin_vol, brisk=brisk_amt, capital=capital, lev=lev)
    rows, skipped = [], []
    for sym, d in ddata.items():
        try:
            if d.index[-1].date() != latest.date():  # stale or halted stock
                skipped.append(sym)
                continue
            r = btst_score(sym, d, P2, mood_pts)
            if r:
                r["Base score"] = r["Score"]
                r["Late pen"] = 0
                r["Late tag"] = "No 5-min data"
                r["Late notes"] = ""
                r["Extended"] = False
                d5 = d5all.get(sym)
                if d5 is not None and len(d5) and d5.index[-1].date() == d.index[-1].date():
                    ld = late_day(d5, r["Chg %"])
                    if ld:
                        r["Late pen"] = ld["pen"]
                        r["Late tag"] = ld["tag"]
                        r["Late notes"] = ld["notes"]
                        r["Extended"] = ld["ext"]
                        r["Score"] = round(max(0.0, r["Score"] - ld["pen"]), 1)
                rows.append(r)
            else:
                skipped.append(sym)
        except Exception:
            skipped.append(sym)
    if rows:
        df = pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)
    else:
        df = pd.DataFrame()

    # Skip stocks with results due (only checked for the best 20, to keep it fast)
    due = []
    if len(df):
        for sym in list(df.Symbol.head(20)):
            if result_due(sym, latest.strftime("%Y-%m-%d")):
                due.append(sym)
        df = df[~df.Symbol.isin(due)].reset_index(drop=True)

    k = st.columns(4)
    for col, val, lab in zip(k, [len(ddata), len(df), int((df.Score >= btst_min).sum()) if len(df) else 0,
                                 now_ist().strftime("%H:%M:%S")],
                             ["Stocks scanned", "Passed liquidity filter", f"Score {btst_min}+", "Last updated (IST)"]):
        col.markdown(f'<div class="kpi"><b>{val}</b><span>{lab.upper()}</span></div>', unsafe_allow_html=True)
    n_pass = len(df)
    n_good = int((df.Score >= btst_min).sum()) if n_pass else 0
    st.markdown(f"**Stocks scanned: {len(ddata)}, Passed basic filter: {n_pass}, Scored above minimum: {n_good}**")
    st.caption(f"{nifty_txt} · latest daily candle: {latest.strftime('%d %b %Y')}"
               + (f" · skipped, result due: {', '.join(due)}" if due else ""))
    n = now_ist()
    if not (n.weekday() < 5 and dtime(14, 30) <= n.time() <= dtime(15, 30)):
        st.caption("Outside the best BTST window (2:30 PM to 3:25 PM IST). Today's candle may be incomplete or from an earlier day.")

    t1, t2 = st.tabs(["🌙 Top 10 BTST", "📒 BTST paper trades"])
    with t1:
        if not len(df):
            st.info("No stock passed the filter. Try lowering the volume filter in the sidebar.")
        else:
            good = df[df.Score >= btst_min].head(10)
            if len(good):
                top, ref_only = good, False
            else:
                top, ref_only = df.head(3), True
                st.markdown('<div class="warn">No good BTST setup today. Skipping is also a good trade.<br>'
                            'Top 3 shown for reference only.</div>', unsafe_allow_html=True)
            why = why_map(top, ddata, "daily")
            cols = st.columns(3)
            for idx, (_, r) in enumerate(top.iterrows()):
                chips = "".join(f"<span>{nm} {v:.0f}/{mx}</span>" for nm, v, mx in
                                [("Close", r["Close pts"], 25), ("Volume", r["Volume pts"], 25), ("Breakout", r["Break pts"], 25),
                                 ("Trend", r["Trend pts"], 15), ("Mood", r["Mood pts"], 10)])
                late_pills = ""
                if r["Late tag"] != "No 5-min data":
                    late_pills = f'<span class="pill label">{r["Late tag"]}</span>'
                if r["Extended"]:
                    late_pills += '<span class="pill label">Extended move</span>'
                late_line = ""
                if r["Late tag"] != "No 5-min data":
                    late_line = (f'<div class="sub">Late-day penalty: <b>{("-" + str(int(r["Late pen"]))) if r["Late pen"] else "0"}</b> (score before penalty {r["Base score"]:.0f})'
                                 + (f' · {r["Late notes"]}' if r["Late notes"] else "") + '</div>')
                html = f"""<div class="pick long"><h3>#{idx + 1} {r.Symbol}<span class="pill score">{r.Score:.0f}/100</span></h3>
                <div class="bar"><i style="width:{min(r.Score, 100):.0f}%"></i></div>
                <div class="sub"><span class="pill label" style="margin-left:0">{r.Label}</span>{late_pills} Closed at {r["Range %"]:.0f}% of day range · {r.Breakout}</div>
                <div class="grid"><div>Close<b>{r.Close:.2f}</b></div><div>Change<b>{r["Chg %"]:+.2f}%</b></div><div>Volume<b>{r.VolX:.1f}x</b></div>
                <div>Entry<b>{r.Buy:.2f}</b></div><div>Stop<b>{r.Stop:.2f}</b></div><div>Target<b>{r.Target:.2f}</b></div></div>
                <div class="sub">Shares for Rs {brisk_amt:,} risk: <b>{int(r.Qty)}</b> (risk Rs {r["Risk/sh"]:.2f} per share, reward 2x)<br>
                Sell in the first 30 to 60 minutes tomorrow, or at the stop.</div>
                <div class="sub">Prev close: {r.PrevClose:.2f} ({r.PrevDate})</div>
                {late_line}<div class="chips">{chips}</div>{why.get(r.Symbol, "")}</div>"""
                with cols[idx % 3]:
                    st.markdown(html, unsafe_allow_html=True)
                    if st.button("Paper trade this BTST", key=f"bt_{r.Symbol}_{idx}"):
                        j = st.session_state.btst_journal
                        if len(j[(j.symbol == r.Symbol) & (j.status == "OPEN")]):
                            st.warning("Already open.")
                        elif int(r.Qty) < 1:
                            st.warning("Quantity is 0 with your risk and capital settings.")
                        else:
                            btst_add(r.to_dict())
                            st.success("Saved. See the BTST paper trades tab.")
            st.caption("Score is for ranking only. It is not a chance of winning. A gap down overnight can skip right past your stop.")
            why_notes()
            with st.expander("All scores"):
                show = ["Symbol", "Score", "Base score", "Late pen", "Late tag", "Label", "Close", "Chg %", "VolX", "Range %", "Breakout",
                        "Close pts", "Volume pts", "Break pts", "Trend pts", "Mood pts"]
                st.dataframe(df[show], hide_index=True, width="stretch")
                if skipped:
                    st.write("Skipped: " + ", ".join(skipped))

    with t2:
        j = st.session_state.btst_journal
        op = j[j.status == "OPEN"]
        st.markdown(f"##### Open BTST trades ({len(op)})")
        if len(op):
            ltp = {s: float(d.Close.iloc[-1]) for s, d in ddata.items()}
            o = op[["id", "date", "symbol", "buy", "stop", "target", "qty", "score", "label"]].copy()
            o["Last price"] = o.symbol.map(ltp)
            o["Open P&L"] = ((o["Last price"] - o.buy) * o.qty).round(0)
            st.dataframe(o, hide_index=True, width="stretch")
            st.markdown("**Next morning: enter your exit price**")
            a, b, c_ = st.columns(3)
            cid = a.selectbox("Close trade #", list(op.id.astype(int)), key="bt_cid")
            sym_ = op[op.id == cid].symbol.iloc[0]
            px = b.number_input("Exit price", 0.0, 1000000.0, float(ltp.get(sym_, 0.0)), 0.05, key="bt_px")
            if c_.button("Save exit", key="bt_exit"):
                btst_close(j.index[j.id == cid][0], px, now_ist().strftime("%Y-%m-%d"))
                st.rerun()
        else:
            st.caption("No open BTST trades.")
        cl = j[j.status == "CLOSED"].copy()
        st.markdown(f"##### Closed BTST trades ({len(cl)})")
        if len(cl):
            for c_ in ("net", "gross", "costs", "r"):
                cl[c_] = pd.to_numeric(cl[c_], errors="coerce")
            m = st.columns(5)
            m[0].metric("Trades", len(cl))
            m[1].metric("Wins", int((cl.net > 0).sum()))
            m[2].metric("Losses", int((cl.net <= 0).sum()))
            m[3].metric("Win rate", f"{(cl.net > 0).mean() * 100:.0f}%")
            m[4].metric("Net P&L (Rs)", f"{cl.net.sum():,.0f}")
            st.dataframe(cl.sort_values("id", ascending=False), hide_index=True, width="stretch")
        # BTST vs intraday comparison (the two journals are kept separate)
        ij = st.session_state.journal
        ic = ij[ij.status != "OPEN"].copy()
        ic["net"] = pd.to_numeric(ic["net"], errors="coerce")
        comp = pd.DataFrame([
            {"Style": "Intraday", "Trades": len(ic), "Win rate %": round((ic.net > 0).mean() * 100) if len(ic) else 0,
             "Net P&L (Rs)": round(ic.net.sum()) if len(ic) else 0},
            {"Style": "BTST", "Trades": len(cl), "Win rate %": round((cl.net > 0).mean() * 100) if len(cl) else 0,
             "Net P&L (Rs)": round(cl.net.sum()) if len(cl) else 0}])
        st.markdown("##### BTST vs Intraday")
        st.dataframe(comp, hide_index=True, width="stretch")
        st.markdown("##### Keep your BTST journal safe")
        d1, d2 = st.columns(2)
        d1.download_button("Download BTST journal (CSV)", st.session_state.btst_journal.to_csv(index=False),
                           "btst_journal.csv", "text/csv", key="bt_dl")
        up = d2.file_uploader("Upload BTST journal (CSV)", type="csv", key="bt_up")
        if up is not None and st.button("Load this BTST file", key="bt_load"):
            st.session_state.btst_journal = btst_norm(pd.read_csv(up))
            btst_save()
            st.rerun()
        st.caption("Streamlit Cloud can reset saved files when the app restarts. Download the BTST journal after each trade.")


def btst_body():
    """Safety wrapper: if the whole BTST scan fails, show a clear message instead of crashing or printing junk."""
    try:
        _btst_body()
    except Exception as e:
        st.error(f"The BTST scan failed: {type(e).__name__}: {e}. Press Refresh BTST data in a minute. The Intraday tab is not affected.")


# Two main tabs. Intraday re-runs by itself during market hours; BTST refreshes with its button.
# Auto refresh: during market hours the intraday body re-runs by itself every 1 or 2 minutes.
_run_every = ("60s" if every.startswith("1") else "120s") if (auto and market_open()) else None
main_tabs = st.tabs(["🎯 Intraday", "🌙 BTST Scanner"])
with main_tabs[0]:
    st.fragment(run_every=_run_every)(body)()
with main_tabs[1]:
    st.fragment(btst_body)()
