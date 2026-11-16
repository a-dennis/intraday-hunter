import os
from datetime import datetime, time as dtime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
JOURNAL = "journal.csv"
COLS = ["id", "date", "time", "symbol", "side", "entry", "stop", "target", "qty", "status",
        "exit", "exit_time", "gross", "costs", "net", "r", "score", "setup", "note"]
DEFAULT_LIST = ("RELIANCE, TCS, HDFCBANK, ICICIBANK, INFY, BHARTIARTL, ITC, SBIN, LT, KOTAKBANK, "
                "HINDUNILVR, AXISBANK, BAJFINANCE, ASIANPAINT, MARUTI, SUNPHARMA, TITAN, ULTRACEMCO, "
                "NTPC, ONGC, POWERGRID, TATASTEEL, JSWSTEEL, HCLTECH, WIPRO, TECHM, ADANIPORTS, "
                "COALINDIA, BAJAJFINSV, NESTLEIND, GRASIM, HINDALCO, CIPLA, DRREDDY, EICHERMOT, BPCL, "
                "HEROMOTOCO, INDUSINDBK, TATACONSUM, APOLLOHOSP, SBILIFE, HDFCLIFE, BRITANNIA, DIVISLAB, "
                "SHRIRAMFIN, TRENT, BEL, PNB, BANKBARODA, CANBK, IOC, GAIL, VEDL, DLF, HAL, RECLTD, PFC, "
                "SAIL, NMDC, IDFCFIRSTB, M&M")

st.set_page_config(page_title="Intraday Hunter", page_icon="🎯", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:3.5rem;max-width:1250px}
.hero{background:linear-gradient(120deg,#0f2027,#1c3d5a 55%,#2c5364);border-radius:16px;padding:20px 26px;color:#fff;margin-bottom:14px}
.hero h1{margin:0;font-size:30px;color:#fff}
.hero p{margin:4px 0 0;color:#cfe3f1;font-size:15px}
.kpi{border:1px solid rgba(128,128,128,.3);border-radius:14px;padding:12px 16px}
.kpi b{font-size:26px;display:block}
.kpi span{font-size:13px;opacity:.75}
.up{color:#14a44d}.dn{color:#e03131}
.card{border:1px solid rgba(128,128,128,.3);border-radius:14px;padding:12px 16px;margin-bottom:10px}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;color:#fff}
.pill.up{background:#14a44d;color:#fff}.pill.dn{background:#e03131;color:#fff}
.warn{border-left:4px solid #f08c00;background:rgba(240,140,0,.1);padding:10px 14px;border-radius:8px;font-size:14px}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- login gate (owner only)
import hmac
import time as _time


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


# ---------------------------------------------------------------- data
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


@st.cache_data(ttl=60, show_spinner=False)
def fetch(symbols, interval):
    tick = [s + ".NS" for s in symbols]
    raw = yf.download(tick, period="5d", interval=interval, group_by="ticker",
                      auto_adjust=False, progress=False, threads=True)
    out = {}
    for s, t in zip(symbols, tick):
        d = clean(raw, t, len(tick) > 1)
        if d is not None:
            out[s] = d
    return out


def add_ind(d):
    d = d.copy()
    d["EMA9"] = d.Close.ewm(span=9, adjust=False).mean()
    d["EMA21"] = d.Close.ewm(span=21, adjust=False).mean()
    ch = d.Close.diff()
    up, dn = ch.clip(lower=0), -ch.clip(upper=0)
    rs = up.ewm(alpha=1 / 14, adjust=False).mean() / dn.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
    d["RSI"] = 100 - 100 / (1 + rs)
    day = d.index.date
    typ = (d.High + d.Low + d.Close) / 3
    pv = (typ * d.Volume).groupby(day).cumsum()
    vv = d.Volume.groupby(day).cumsum()
    d["VWAP"] = pv / vv.replace(0, np.nan)
    return d


def analyze(sym, d, look, plan):
    d = add_ind(d)
    ld = d.index[-1].date()
    t = d[d.index.date == ld]
    if len(t) < 4 or t.VWAP.isna().all():
        return None
    prev = d[d.index.date < ld]
    pc = prev.Close.iloc[-1] if len(prev) else np.nan
    side = np.sign((t.Close - t.VWAP).values)
    n = len(t)
    cross = None
    for j in range(n - 1, max(n - 1 - look, 0), -1):
        if side[j - 1] < 0 and side[j] > 0 and side[-1] > 0:
            cross = ("UP", j)
            break
        if side[j - 1] > 0 and side[j] < 0 and side[-1] < 0:
            cross = ("DOWN", j)
            break
    if cross is None:
        return None
    dirn, j = cross
    long = dirn == "UP"
    ltp, vw = float(t.Close.iloc[-1]), float(t.VWAP.iloc[-1])
    turnover = float(((t.High + t.Low + t.Close) / 3 * t.Volume).sum()) / 1e7
    mv = t.Volume.mean()
    vr = float(t.Volume.iloc[-3:].mean() / mv) if mv > 0 else np.nan
    or_hi, or_lo = t.High.iloc[:3].max(), t.Low.iloc[:3].min()
    rsi, e9, e21 = t.RSI.iloc[-1], t.EMA9.iloc[-1], t.EMA21.iloc[-1]
    checks = [
        e9 > e21 if long else e9 < e21,
        50 <= rsi <= 75 if long else 25 <= rsi <= 50,
        vr >= 1.3,
        ltp > pc if long else ltp < pc,
        ltp > or_hi if long else ltp < or_lo,
    ]
    score = int(sum(bool(c) for c in checks))
    stop = vw * (0.999 if long else 1.001)
    if (long and stop >= ltp) or ((not long) and stop <= ltp):
        stop = ltp * (0.995 if long else 1.005)
    rps = abs(ltp - stop)
    target = ltp + plan["rr"] * rps if long else ltp - plan["rr"] * rps
    qty = int(max(0, min(plan["risk"] // rps, plan["capital"] * plan["lev"] // ltp))) if rps > 0 else 0
    return {
        "Symbol": sym, "Direction": dirn, "LTP": round(ltp, 2),
        "Chg %": round((ltp / pc - 1) * 100, 2) if pc == pc else np.nan,
        "VWAP": round(vw, 2), "Gap to VWAP %": round((ltp / vw - 1) * 100, 2),
        "Crossed at": t.index[j].strftime("%H:%M"), "Candles ago": n - 1 - j,
        "Vol x": round(vr, 2) if vr == vr else np.nan, "RSI": round(float(rsi), 1),
        "Score /5": score, "Turnover Cr": round(turnover, 1),
        "Entry": round(ltp, 2), "Stop": round(stop, 2), "Target": round(target, 2), "Qty": qty,
        "_last": t.index[-1],
    }


# ---------------------------------------------------------------- journal
def norm(df):
    for c in COLS:
        if c not in df.columns:
            df[c] = np.nan
    df = df[COLS].copy()
    for c in ("setup", "note", "status", "side", "symbol", "date", "time", "exit_time"):
        df[c] = df[c].fillna("").astype(str)
    for c in ("id", "entry", "stop", "target", "qty", "exit", "gross", "costs", "net", "r", "score"):
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
    new = {"id": nid, "date": last.strftime("%Y-%m-%d"), "time": last.strftime("%H:%M"),
           "symbol": r["Symbol"], "side": "LONG" if r["Direction"] == "UP" else "SHORT",
           "entry": r["Entry"], "stop": r["Stop"], "target": r["Target"], "qty": r["Qty"],
           "status": "OPEN", "score": r["Score /5"], "setup": setup, "note": note}
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
        if not hit:
            latest_day = d.index[-1].date()
            if day < latest_day or dd.index[-1].time() >= dtime(15, 10):
                hit = (float(dd.Close.iloc[-1]), "EOD", dd.index[-1])
        if hit:
            close_trade(i, hit[0], hit[1], hit[2].strftime("%H:%M"), cfg)
            done += 1
    return done


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    wl = st.text_area("Stocks to scan (NSE symbols, comma separated)", DEFAULT_LIST, height=140)
    interval = st.selectbox("Candle size", ["5m", "15m"], index=0)
    look = st.slider("'Just crossed' means within last N candles", 1, 6, 3)
    min_score = st.slider("Minimum score (out of 5)", 0, 5, 2)
    min_turn = st.number_input("Minimum turnover today (Rs crore)", 0.0, 500.0, 5.0, 1.0)
    st.subheader("Paper trading")
    capital = st.number_input("Paper capital (Rs)", 5000, 10000000, 50000, 5000)
    risk = st.number_input("Risk per trade (Rs)", 50, 100000, 250, 50)
    rr = st.number_input("Target = risk x", 0.5, 5.0, 1.5, 0.5)
    lev = st.number_input("Leverage (1 = none)", 1, 5, 1, 1)
    flat = st.number_input("Brokerage per order (Rs)", 0.0, 100.0, 20.0, 5.0)
    pct = st.number_input("Taxes and charges (% of turnover)", 0.0, 0.5, 0.04, 0.01)
    if st.button("Refresh data now", width="stretch"):
        st.cache_data.clear()
        st.rerun()

plan = {"capital": capital, "risk": risk, "rr": rr, "lev": lev}
cfg = {"flat": flat, "pct": pct}
symbols = tuple(dict.fromkeys(s.strip().upper() for s in wl.replace("\n", ",").split(",") if s.strip()))
if "journal" not in st.session_state:
    st.session_state.journal = load_journal()

# ---------------------------------------------------------------- header
st.markdown("""<div class="hero"><h1>🎯 Intraday Hunter</h1>
<p>Stocks that have just crossed VWAP, with trend, volume and risk levels. Practice on paper, keep a journal.</p></div>""",
            unsafe_allow_html=True)

with st.spinner("Getting prices..."):
    try:
        data = fetch(symbols, interval)
    except Exception as e:
        data = {}
        st.error(f"Could not get prices: {e}")

rows = []
for s, d in data.items():
    try:
        r = analyze(s, d, look, plan)
    except Exception:
        r = None
    if r:
        rows.append(r)
scan = pd.DataFrame(rows)
last_candle = max((d.index[-1] for d in data.values()), default=None)

c1, c2, c3, c4 = st.columns(4)
n_up = int((scan.Direction == "UP").sum()) if len(scan) else 0
n_dn = int((scan.Direction == "DOWN").sum()) if len(scan) else 0
for col, val, lab in ((c1, len(data), "Stocks scanned"), (c2, n_up, "Just crossed above VWAP"),
                      (c3, n_dn, "Just crossed below VWAP"),
                      (c4, last_candle.strftime("%d %b, %H:%M") if last_candle is not None else "-", "Latest candle (IST)")):
    col.markdown(f'<div class="kpi"><b>{val}</b><span>{lab}</span></div>', unsafe_allow_html=True)
if last_candle is not None:
    lag = (now_ist() - last_candle).total_seconds() / 60
    if lag > 20:
        st.markdown(f'<div class="warn">The latest price candle is about {int(lag)} minutes old. The market may be closed, '
                    f'or Yahoo data may be delayed. Do not treat these levels as live.</div>', unsafe_allow_html=True)

if not len(st.session_state.journal):
    st.info("Journal is empty. This free host can wipe saved files when it restarts or sleeps. If you have an earlier "
            "journal, restore it in the Paper trades tab (Restore journal). Download a copy after every session.")
tab1, tab2, tab3, tab4 = st.tabs(["🔍 VWAP cross scanner", "📈 Chart", "📒 Paper trades & journal", "ℹ️ How it works"])

SHOW = ["Symbol", "LTP", "Chg %", "VWAP", "Gap to VWAP %", "Crossed at", "Candles ago", "Vol x", "RSI",
        "Score /5", "Entry", "Stop", "Target", "Qty"]
if len(scan):
    scan = scan[(scan["Score /5"] >= min_score) & (scan["Turnover Cr"] >= min_turn)]

# ---------------------------------------------------------------- scanner
with tab1:
    if not len(scan):
        st.info("No stock has just crossed VWAP with these settings. Try lowering the minimum score, or press Refresh.")
    else:
        for name, cls, label in (("UP", "up", "Crossed ABOVE VWAP (possible buy side)"),
                                 ("DOWN", "dn", "Crossed BELOW VWAP (possible sell side)")):
            sub = scan[scan.Direction == name].sort_values(["Score /5", "Candles ago"], ascending=[False, True])
            st.markdown(f'<span class="pill {cls}">{label}</span>  &nbsp; {len(sub)} stock(s)', unsafe_allow_html=True)
            if len(sub):
                st.dataframe(sub[SHOW], hide_index=True, width="stretch")
            else:
                st.caption("None right now.")
        st.markdown("##### Log a paper trade")
        opts = [f"{r.Symbol} - {r.Direction}" for r in scan.sort_values("Score /5", ascending=False).itertuples()]
        a, b, c = st.columns([2, 2, 3])
        pick = a.selectbox("Stock", opts)
        setup = b.text_input("Setup tag", "VWAP cross")
        note = c.text_input("Why are you taking it? (optional)")
        if st.button("Take paper trade", type="primary"):
            sym = pick.split(" - ")[0]
            rr_ = scan[scan.Symbol == sym].iloc[0].to_dict()
            j = st.session_state.journal
            if len(j[(j.symbol == sym) & (j.status == "OPEN")]):
                st.warning(f"{sym} already has an open paper trade.")
            elif rr_["Qty"] < 1:
                st.warning("Quantity comes to 0 with your risk and capital settings. Increase risk or capital.")
            else:
                add_trade(rr_, setup, note)
                st.success(f"Logged {sym} ({rr_['Direction']}) at {rr_['Entry']}. See the Paper trades tab.")
        st.caption("Stop is just beyond VWAP. Qty keeps the loss near your risk amount if the stop is hit. This is for practice only.")

# ---------------------------------------------------------------- chart
with tab2:
    if not data:
        st.info("No data yet.")
    else:
        names = list(scan.Symbol) if len(scan) else []
        names += [s for s in data if s not in names]
        sym = st.selectbox("Stock", names)
        d = add_ind(data[sym])
        days = sorted(set(d.index.date))[-2:]
        d = d[[x in days for x in d.index.date]]
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close, name="Price"))
        fig.add_trace(go.Scatter(x=d.index, y=d.VWAP, name="VWAP", line=dict(color="#f08c00", width=2)))
        fig.add_trace(go.Scatter(x=d.index, y=d.EMA9, name="EMA 9", line=dict(color="#1c7ed6", width=1)))
        fig.add_trace(go.Scatter(x=d.index, y=d.EMA21, name="EMA 21", line=dict(color="#ae3ec9", width=1)))
        j = st.session_state.journal
        for r in j[(j.symbol == sym)].itertuples():
            fig.add_hline(y=r.entry, line_dash="dot", annotation_text=f"{r.side} entry #{r.id}")
        fig.update_layout(height=560, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=20, b=10),
                          xaxis=dict(rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[15.5, 9.25], pattern="hour")]))
        st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- journal
with tab3:
    j = st.session_state.journal
    top = st.columns([1, 1, 2])
    if top[0].button("Check open trades (stop / target)", type="primary"):
        n = check_open(data, cfg)
        st.success(f"{n} trade(s) closed.") if n else st.info("No open trade hit its stop or target yet.")
        j = st.session_state.journal

    op = j[j.status == "OPEN"]
    st.markdown(f"##### Open trades ({len(op)})")
    if len(op):
        ltp = {s: float(d.Close.iloc[-1]) for s, d in data.items()}
        o = op[["id", "date", "time", "symbol", "side", "entry", "stop", "target", "qty"]].copy()
        o["LTP"] = o.symbol.map(ltp)
        o["Open P&L"] = ((o.LTP - o.entry) * o.qty * o.side.map({"LONG": 1, "SHORT": -1})).round(0)
        st.dataframe(o, hide_index=True, width="stretch")
        a, b, c = st.columns([1, 1, 1])
        cid = a.selectbox("Close trade #", list(op.id.astype(int)))
        px = b.number_input("Exit price", 0.0, 1000000.0, float(ltp.get(op[op.id == cid].symbol.iloc[0], 0.0)), 0.05)
        if c.button("Close it now"):
            idx = j.index[j.id == cid][0]
            close_trade(idx, px, "MANUAL", now_ist().strftime("%H:%M"), cfg)
            st.rerun()
    else:
        st.caption("No open trades.")

    cl = j[j.status != "OPEN"].copy()
    st.markdown(f"##### Closed trades ({len(cl)})")
    if len(cl):
        for c in ("net", "gross", "costs", "r"):
            cl[c] = pd.to_numeric(cl[c], errors="coerce")
        wins = int((cl.net > 0).sum())
        m = st.columns(5)
        m[0].metric("Trades", len(cl))
        m[1].metric("Win rate", f"{wins / len(cl) * 100:.0f}%")
        m[2].metric("Net P&L (Rs)", f"{cl.net.sum():,.0f}")
        m[3].metric("Costs paid (Rs)", f"{cl.costs.sum():,.0f}")
        m[4].metric("Average R", f"{cl.r.mean():.2f}")
        cum = cl.sort_values(["date", "time"]).net.cumsum().reset_index(drop=True)
        st.line_chart(cum, height=200)
        edited = st.data_editor(cl.sort_values("id", ascending=False), hide_index=True, width="stretch",
                                disabled=[c for c in COLS if c not in ("setup", "note")], key="ed")
        if st.button("Save my setup / note edits"):
            jj = st.session_state.journal
            for _, r in edited.iterrows():
                k = jj.index[jj.id == r["id"]]
                jj.loc[k, "setup"] = r["setup"]
                jj.loc[k, "note"] = r["note"]
            st.session_state.journal = jj
            save_journal()
            st.success("Saved.")
    else:
        st.caption("No closed trades yet.")

    st.markdown("##### Keep your journal safe")
    d1, d2 = st.columns(2)
    d1.download_button("Download journal (CSV)", st.session_state.journal.to_csv(index=False), "journal.csv", "text/csv")
    up = d2.file_uploader("Restore journal (CSV)", type="csv")
    if up is not None and st.button("Load this file"):
        st.session_state.journal = norm(pd.read_csv(up))
        save_journal()
        st.rerun()
    st.caption("Streamlit Cloud can reset saved files when the app restarts. Please download your journal at the end of every day.")

# ---------------------------------------------------------------- guide
with tab4:
    st.markdown("""
**What the scanner does**
1. Gets 5-minute (or 15-minute) prices for your stock list from Yahoo Finance.
2. Works out **VWAP** (the day's volume-weighted average price) from the 9:15 open.
3. Finds stocks whose price **just crossed VWAP** in the last few candles and is still on that side.

**Score out of 5** (how many of these agree with the direction):
EMA 9 vs EMA 21 trend, RSI zone, volume surge (last 3 candles vs day average), price vs yesterday's close, price beyond the first 15-minute range.
A higher score means more signals agree. It does **not** mean the trade will work.

**Paper trade plan:** entry at the last price, stop just beyond VWAP, target at your chosen multiple of the risk,
quantity so that the loss at the stop is about your risk amount. Costs are estimated from the settings.

**Rules to keep in mind**
- Paper trade for at least 3-4 weeks and read the journal before using real money.
- Intraday cash trades must be squared off the same day. The app closes open paper trades at about 3:15 pm.
- Yahoo data can be delayed or have gaps. Always compare with your broker screen.
- This is a practice and learning tool, not investment advice.
""")
