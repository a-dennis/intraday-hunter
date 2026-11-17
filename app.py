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
COLS = ["id", "date", "time", "symbol", "side", "entry", "stop", "target", "qty", "status", "exit", "exit_time",
        "gross", "costs", "net", "r", "relvol", "rank", "setup", "note"]
DEFAULT_LIST = ("RELIANCE, TCS, HDFCBANK, ICICIBANK, INFY, BHARTIARTL, ITC, SBIN, LT, KOTAKBANK, "
                "HINDUNILVR, AXISBANK, BAJFINANCE, ASIANPAINT, MARUTI, SUNPHARMA, TITAN, ULTRACEMCO, "
                "NTPC, ONGC, POWERGRID, TATASTEEL, JSWSTEEL, HCLTECH, WIPRO, TECHM, ADANIPORTS, "
                "COALINDIA, BAJAJFINSV, NESTLEIND, GRASIM, HINDALCO, CIPLA, DRREDDY, EICHERMOT, BPCL, "
                "HEROMOTOCO, INDUSINDBK, TATACONSUM, APOLLOHOSP, SBILIFE, HDFCLIFE, BRITANNIA, DIVISLAB, "
                "SHRIRAMFIN, TRENT, BEL, PNB, BANKBARODA, CANBK, IOC, GAIL, VEDL, DLF, HAL, RECLTD, PFC, "
                "SAIL, NMDC, IDFCFIRSTB, M&M")
STAGES = ["Quality", "In play", "Trigger", "Momentum", "Trade plan"]

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


@st.cache_data(ttl=120, show_spinner=False)
def fetch(symbols):
    tick = [s + ".NS" for s in symbols]
    raw = yf.download(tick, period="60d", interval="5m", group_by="ticker",
                      auto_adjust=False, progress=False, threads=True)
    out = {}
    for s, t in zip(symbols, tick):
        d = clean(raw, t, len(tick) > 1)
        if d is not None:
            out[s] = d
    return out


def prep(d):
    d = d.copy()
    d["date"] = d.index.date
    d["EMA9"] = d.Close.ewm(span=9, adjust=False).mean()
    d["EMA21"] = d.Close.ewm(span=21, adjust=False).mean()
    ch = d.Close.diff()
    up, dn = ch.clip(lower=0), -ch.clip(upper=0)
    rs = up.ewm(alpha=1 / 14, adjust=False).mean() / dn.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
    d["RSI"] = 100 - 100 / (1 + rs)
    typ = (d.High + d.Low + d.Close) / 3
    d["VWAP"] = (typ * d.Volume).groupby(d["date"]).cumsum() / d.Volume.groupby(d["date"]).cumsum().replace(0, np.nan)
    return d


def daily_table(d, k):
    g = d.groupby("date")
    typ = (d.High + d.Low + d.Close) / 3
    out = pd.DataFrame({"open": g.Open.first(), "high": g.High.max(), "low": g.Low.min(), "close": g.Close.last(),
                        "turn": (typ * d.Volume).groupby(d["date"]).sum() / 1e7})
    out["ow"] = d.groupby("date").head(k).groupby("date").Volume.sum()
    pc = out.close.shift(1)
    tr = pd.concat([out.high - out.low, (out.high - pc).abs(), (out.low - pc).abs()], axis=1).max(axis=1)
    out["pc"], out["pdh"], out["pdl"] = pc, out.high.shift(1), out.low.shift(1)
    out["atr"] = tr.rolling(14).mean().shift(1)
    out["avg_turn"] = out.turn.rolling(14).mean().shift(1)
    out["avg_ow"] = out.ow.rolling(14).mean().shift(1)
    return out


def data_ok(t):
    start = t.index[0].replace(hour=9, minute=15, second=0, microsecond=0)
    if (t.index[0] - start).total_seconds() / 60 > 5:
        return False, "opening 9:15 candle missing"
    elapsed = (t.index[-1] - start).total_seconds() / 60 / 5 + 1
    if len(t) < 0.85 * elapsed:
        return False, "gaps in today's candles"
    return True, ""


def checks(side, ltp, e9, e21, rsi, v, risk, row, P):
    ema = e9 > e21 if side == 1 else e9 < e21
    rz = 50 <= rsi <= 75 if side == 1 else 25 <= rsi <= 50
    vm = v.mean()
    vx = float(v[-3:].mean() / vm) if vm > 0 else 0.0
    ext = row.pdh if side == 1 else row.pdl
    free = (side == 1 and ltp >= ext) or (side == -1 and ltp <= ext) or risk <= 0
    room = 99.0 if free else abs(ext - ltp) / risk
    return [bool(ema), bool(rz), bool(vx >= P["vol_x"]), bool(room >= 1.0)], vx, room


def qty_for(entry, risk, P):
    if risk <= 0:
        return 0
    return int(max(0, min(P["risk"] // risk, P["capital"] * P["lev"] // entry)))


def rank_score(rv, nchk, room):
    return round(40 * min(rv / 3, 1) + 30 * nchk / 4 + 30 * min(room / 3, 1), 1)


# ============================================================ live funnel
def evaluate(sym, d, daily, P, live):
    k = P["k"]
    D = daily.index[-1]
    t = d[d["date"] == D]
    n = len(t)
    r = {"Symbol": sym, "S1": False, "S2": False, "S3": False, "S4": False, "S5": False, "Why": "", "Skip": False}
    row = daily.loc[D]
    if pd.isna(row.avg_ow) or pd.isna(row.atr) or pd.isna(row.avg_turn) or row.avg_ow <= 0:
        r.update(Skip=True, Why="not enough history")
        return r
    ok, why = data_ok(t)
    if not ok:
        r.update(Skip=True, Why=why + ", VWAP would be wrong")
        return r
    ltp = float(t.Close.iloc[-1])
    r["LTP"] = round(ltp, 2)
    atrp = row.atr / ltp * 100
    r["ATR %"] = round(atrp, 2)
    if not (row.avg_turn >= P["min_turn"] and ltp >= P["min_price"] and atrp >= P["min_atr"]):
        r["Why"] = f"1: turnover {row.avg_turn:.0f} Cr, ATR {atrp:.1f}%"
        return r
    r["S1"] = True
    if n < k:
        r["Why"] = "2: waiting for the opening range to finish"
        return r
    rv = float(row.ow / row.avg_ow)
    gap = float((row.open / row.pc - 1) * 100)
    r["RelVol"], r["Gap %"] = round(rv, 2), round(gap, 2)
    if not (rv >= P["relvol"] and abs(gap) >= P["gap"]):
        r["Why"] = f"2: opening volume {rv:.1f}x, gap {gap:+.1f}%"
        return r
    r["S2"] = True
    o, h, l, c, v = (t[x].to_numpy() for x in ("Open", "High", "Low", "Close", "Volume"))
    vw, e9, e21, rsi = (t[x].to_numpy() for x in ("VWAP", "EMA9", "EMA21", "RSI"))
    or_hi, or_lo = h[:k].max(), l[:k].min()
    bias = 1 if c[k - 1] > o[0] else (-1 if c[k - 1] < o[0] else 0)
    trig = None
    for j in range(k, n):
        if c[j] > or_hi:
            trig = (1, j)
            break
        if c[j] < or_lo:
            trig = (-1, j)
            break
    r["OR High"], r["OR Low"] = round(float(or_hi), 2), round(float(or_lo), 2)
    if trig is None:
        r["Why"] = "3: no close beyond the opening range yet"
        return r
    side, j = trig
    r["Side"] = "LONG" if side == 1 else "SHORT"
    r["Trigger"], r["Ago"] = t.index[j].strftime("%H:%M"), n - 1 - j
    beyond = c[-1] > or_hi if side == 1 else c[-1] < or_lo
    stopped = l[j:].min() <= or_lo if side == 1 else h[j:].max() >= or_hi
    vwap_ok = c[-1] > vw[-1] if side == 1 else c[-1] < vw[-1]
    bias_ok = (not P["bias"]) or bias == side
    timed = (not (live and P["window"])) or t.index[-1].time() <= P["cutoff"]
    r["VWAP"] = round(float(vw[-1]), 2)
    bad = []
    if not beyond or stopped:
        bad.append("breakout failed")
    if not vwap_ok:
        bad.append("price on the wrong side of VWAP")
    if not bias_ok:
        bad.append("opening candle direction disagrees")
    if live and r["Ago"] > P["fresh"]:
        bad.append("breakout is old")
    if not timed:
        bad.append("after the entry cut-off time")
    if bad:
        r["Why"] = "3: " + ", ".join(bad)
        return r
    r["S3"] = True
    stop = float(or_lo if side == 1 else or_hi)
    risk = abs(ltp - stop)
    ck, vx, room = checks(side, ltp, e9[-1], e21[-1], rsi[-1], v, risk, row, P)
    r.update(RSI=round(float(rsi[-1]), 1), VolX=round(vx, 2), Room=round(min(room, 9.9), 1), Checks=ck)
    if sum(ck) < P["min_checks"]:
        names = ["EMA trend", "RSI zone", "volume", "room to run"]
        r["Why"] = "4: weak on " + ", ".join(nm for nm, ok_ in zip(names, ck) if not ok_)
        return r
    r["S4"] = True
    risk_pct = risk / ltp * 100
    long = side == 1
    if (long and stop >= ltp) or ((not long) and stop <= ltp):
        r["Why"] = "5: stop is on the wrong side"
        return r
    target = ltp + side * P["rr"] * risk
    qty = qty_for(ltp, risk, P)
    r.update(Entry=round(ltp, 2), Stop=round(stop, 2), Target=round(target, 2), Qty=qty, **{"Risk %": round(risk_pct, 2)})
    if not (P["min_risk"] <= risk_pct <= P["max_risk"]):
        r["Why"] = f"5: stop distance {risk_pct:.2f}% is outside {P['min_risk']}-{P['max_risk']}%"
        return r
    if P["rr"] * risk_pct < 3 * P["cost_pct"]:
        r["Why"] = "5: reward too small compared with costs"
        return r
    if qty < 1:
        r["Why"] = "5: quantity is 0 with your risk and capital settings"
        return r
    r["S5"] = True
    r["Rank"] = rank_score(rv, sum(ck), room)
    r["_last"] = t.index[-1]
    return r


# ============================================================ backtest
def backtest(datas, P, days, topk):
    k = P["k"]
    trades = []
    for sym, d0 in datas.items():
        try:
            d = prep(d0)
            daily = daily_table(d, k)
            dates = list(daily.index)[-days:]
            for D in dates:
                row = daily.loc[D]
                if pd.isna(row.avg_ow) or pd.isna(row.atr) or pd.isna(row.avg_turn) or row.avg_ow <= 0 or pd.isna(row.pc):
                    continue
                t = d[d["date"] == D]
                n = len(t)
                if n < k + 3 or not data_ok(t)[0]:
                    continue
                if row.avg_turn < P["min_turn"] or row.open < P["min_price"] or row.atr / row.open * 100 < P["min_atr"]:
                    continue
                rv = float(row.ow / row.avg_ow)
                if rv < P["relvol"] or abs((row.open / row.pc - 1) * 100) < P["gap"]:
                    continue
                o, h, l, c, v = (t[x].to_numpy() for x in ("Open", "High", "Low", "Close", "Volume"))
                vw, e9, e21, rsi = (t[x].to_numpy() for x in ("VWAP", "EMA9", "EMA21", "RSI"))
                times = t.index
                or_hi, or_lo = h[:k].max(), l[:k].min()
                bias = 1 if c[k - 1] > o[0] else (-1 if c[k - 1] < o[0] else 0)
                for j in range(k, n - 1):
                    if times[j].time() > P["cutoff"]:
                        break
                    side = 1 if c[j] > or_hi else (-1 if c[j] < or_lo else 0)
                    if side == 0 or (P["bias"] and bias != side):
                        continue
                    if (side == 1 and c[j] <= vw[j]) or (side == -1 and c[j] >= vw[j]):
                        continue
                    if (side == 1 and l[k:j + 1].min() <= or_lo) or (side == -1 and h[k:j + 1].max() >= or_hi):
                        break
                    stop = or_lo if side == 1 else or_hi
                    ent = o[j + 1]
                    risk = (ent - stop) * side
                    if risk <= 0:
                        continue
                    rp = risk / ent * 100
                    if not (P["min_risk"] <= rp <= P["max_risk"]) or P["rr"] * rp < 3 * P["cost_pct"]:
                        continue
                    ck, vx, room = checks(side, c[j], e9[j], e21[j], rsi[j], v[:j + 1], risk, row, P)
                    if sum(ck) < P["min_checks"]:
                        continue
                    target = ent + side * P["rr"] * risk
                    qty = qty_for(ent, risk, P)
                    if qty < 1:
                        continue
                    ex, why, et = c[n - 1], "EOD", times[n - 1]
                    for m in range(j + 1, n):
                        if side == 1:
                            if l[m] <= stop:
                                ex, why, et = stop, "STOP", times[m]
                                break
                            if h[m] >= target:
                                ex, why, et = target, "TARGET", times[m]
                                break
                        else:
                            if h[m] >= stop:
                                ex, why, et = stop, "STOP", times[m]
                                break
                            if l[m] <= target:
                                ex, why, et = target, "TARGET", times[m]
                                break
                    gross = (ex - ent) * side * qty
                    cost = P["cost_pct"] / 100 * ent * qty
                    trades.append({"date": str(D), "time": times[j + 1].strftime("%H:%M"), "symbol": sym,
                                   "side": "LONG" if side == 1 else "SHORT", "entry": round(float(ent), 2),
                                   "exit": round(float(ex), 2), "result": why, "qty": qty,
                                   "net": round(float(gross - cost), 2), "R": round(float((gross - cost) / (risk * qty)), 2),
                                   "relvol": round(rv, 2)})
                    break
        except Exception:
            continue
    tr = pd.DataFrame(trades)
    if tr.empty:
        return tr
    tr = tr.sort_values(["date", "time"])
    tr = tr.groupby("date").head(topk).reset_index(drop=True)
    return tr


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
           "status": "OPEN", "relvol": r["RelVol"], "rank": r["Rank"], "setup": setup, "note": note}
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
    wl = st.text_area("Stocks to scan (NSE symbols)", DEFAULT_LIST, height=120)
    with st.expander("Stage 1 · Quality"):
        min_turn = st.number_input("Average daily turnover at least (Rs crore)", 1.0, 5000.0, 50.0, 10.0)
        min_price = st.number_input("Price at least (Rs)", 1.0, 10000.0, 50.0, 10.0)
        min_atr = st.number_input("Daily range (ATR) at least (% of price)", 0.1, 10.0, 1.0, 0.1)
    with st.expander("Stage 2 · In play"):
        relvol = st.number_input("Opening volume vs 14-day average at least (x)", 1.0, 10.0, 1.5, 0.1)
        gap = st.number_input("Gap from yesterday's close at least (%)", 0.0, 5.0, 0.3, 0.1)
    with st.expander("Stage 3 · Trigger"):
        or_min = st.selectbox("Opening range length (minutes)", [5, 15, 30], index=1)
        bias = st.checkbox("Opening candle direction must agree", True)
        fresh = st.slider("Breakout must be within last N candles", 1, 30, 9)
        window = st.checkbox("Use entry time window while market is open", True)
        cutoff = st.time_input("No new entries after", dtime(14, 30))
    with st.expander("Stage 4 · Momentum"):
        vol_x = st.number_input("Recent volume vs day average at least (x)", 0.5, 5.0, 1.2, 0.1)
        min_checks = st.slider("Checks needed (of 4)", 1, 4, 3)
    with st.expander("Stage 5 · Trade plan"):
        rr = st.number_input("Target = risk x", 0.5, 5.0, 1.5, 0.5)
        min_risk = st.number_input("Stop distance at least (%)", 0.05, 5.0, 0.2, 0.05)
        max_risk = st.number_input("Stop distance at most (%)", 0.2, 10.0, 1.5, 0.1)
        cost_pct = st.number_input("Round-trip cost estimate (% of price)", 0.0, 1.0, 0.10, 0.01)
    with st.expander("Paper money"):
        capital = st.number_input("Paper capital (Rs)", 5000, 10000000, 50000, 5000)
        risk_amt = st.number_input("Risk per trade (Rs)", 50, 100000, 250, 50)
        lev = st.number_input("Leverage (1 = none)", 1, 5, 1, 1)
        flat = st.number_input("Brokerage per order (Rs)", 0.0, 100.0, 20.0, 5.0)
        pct = st.number_input("Taxes and charges (% of turnover)", 0.0, 0.5, 0.04, 0.01)
    if st.button("Refresh data now", width="stretch"):
        st.cache_data.clear()
        st.rerun()

P = dict(k=or_min // 5, min_turn=min_turn, min_price=min_price, min_atr=min_atr, relvol=relvol, gap=gap, bias=bias,
         fresh=fresh, window=window, cutoff=cutoff, vol_x=vol_x, min_checks=min_checks, rr=rr, min_risk=min_risk,
         max_risk=max_risk, cost_pct=cost_pct, capital=capital, risk=risk_amt, lev=lev)
cfg = {"flat": flat, "pct": pct}
symbols = tuple(dict.fromkeys(s.strip().upper() for s in wl.replace("\n", ",").split(",") if s.strip()))
if "journal" not in st.session_state:
    st.session_state.journal = load_journal()

# ============================================================ header + data
st.markdown("""<div class="hero"><h1>🎯 Intraday Hunter</h1>
<p>A five-stage funnel: quality, in play, trigger, momentum and trade plan. Only stocks that pass every stage reach the top.</p></div>""",
            unsafe_allow_html=True)

with st.spinner("Getting prices for the last 60 days (first load takes a little while)..."):
    try:
        data = fetch(symbols)
    except Exception as e:
        data = {}
        st.error(f"Could not get prices: {e}")

last_candle = max((d.index[-1] for d in data.values()), default=None)
lag = (now_ist() - last_candle).total_seconds() / 60 if last_candle is not None else 9999
live = lag <= 20

results, prepared = [], {}
for s, d in data.items():
    try:
        pdx = prep(d)
        dly = daily_table(pdx, P["k"])
        prepared[s] = (pdx, dly)
        results.append(evaluate(s, pdx, dly, P, live))
    except Exception:
        continue
res = pd.DataFrame(results)
skipped = res[res.Skip] if len(res) else res
valid = res[~res.Skip] if len(res) else res
cnt = [len(valid)] + [int(valid[f"S{i}"].sum()) if len(valid) else 0 for i in range(1, 6)]
final = valid[valid.S5].sort_values("Rank", ascending=False) if (len(valid) and valid.S5.any()) else valid.iloc[0:0]

c = st.columns(5)
for col, val, lab in zip(c, [len(data), cnt[2], cnt[3], len(final), last_candle.strftime("%d %b, %H:%M") if last_candle is not None else "-"],
                         ["Stocks scanned", "In play today", "Triggered (stage 3)", "Fully qualified", "Latest candle (IST)"]):
    col.markdown(f'<div class="kpi"><b>{val}</b><span>{lab.upper()}</span></div>', unsafe_allow_html=True)
if last_candle is not None and not live:
    st.markdown(f'<div class="note">The market looks closed (latest candle is {int(lag)} minutes old). You are looking at the '
                f'last session as a review. The entry time window is not applied, and levels are not live.</div>', unsafe_allow_html=True)

tabs = st.tabs(["🏆 Top picks", "🔻 Funnel", "📈 Chart", "📒 Paper trades", "🧪 Backtest", "ℹ️ Guide"])

# ------------------------------------------------------------ top picks
with tabs[0]:
    if not len(final):
        st.info("No stock has passed all five stages right now. That is normal on many days. Check the Funnel tab to see "
                "where stocks dropped out, and come back after a few minutes.")
    else:
        top = final.head(6)
        cols = st.columns(3)
        for idx, (_, r) in enumerate(top.iterrows()):
            cls = "long" if r.Side == "LONG" else "short"
            chips = "".join(f"<span>✓ {nm}</span>" for nm in STAGES)
            sub = ["EMA trend", "RSI zone", "Volume", "Room to run"]
            chips2 = "".join(f'<span class="{"" if ok else "no"}">{"✓" if ok else "✗"} {nm}</span>' for nm, ok in zip(sub, r.Checks))
            html = f"""<div class="pick {cls}"><h3>{r.Symbol}<span class="pill {cls}">{r.Side}</span><span class="pill rank">Rank {r.Rank:.0f}</span></h3>
            <div class="sub">Broke the opening range at {r.Trigger} ({int(r.Ago)} candle(s) ago) · LTP {r.LTP:.2f}</div>
            <div class="grid"><div>Entry<b>{r.Entry:.2f}</b></div><div>Stop<b>{r.Stop:.2f}</b></div><div>Target<b>{r.Target:.2f}</b></div>
            <div>Quantity<b>{int(r.Qty)}</b></div><div>Opening volume<b>{r.RelVol:.1f}x</b></div><div>Gap<b>{r["Gap %"]:+.1f}%</b></div></div>
            <div class="chips">{chips}</div><div class="chips">{chips2}</div></div>"""
            with cols[idx % 3]:
                st.markdown(html, unsafe_allow_html=True)
                if st.button("Take paper trade", key=f"pt_{r.Symbol}"):
                    j = st.session_state.journal
                    if len(j[(j.symbol == r.Symbol) & (j.status == "OPEN")]):
                        st.warning("Already open.")
                    else:
                        add_trade(r.to_dict(), "Funnel pick", "")
                        st.success("Logged. See the Paper trades tab.")
        st.caption("Rank is only for sorting (opening volume, momentum checks and room to run). It is not a probability of winning. "
                   "Stop is the other end of the opening range. Quantity keeps the loss near your risk amount.")

# ------------------------------------------------------------ funnel
with tabs[1]:
    labels = ["Scanned (data ok)"] + [f"{i + 1} · {n}" for i, n in enumerate(STAGES)]
    fig = go.Figure(go.Funnel(y=labels, x=cnt, textinfo="value+percent initial",
                              marker=dict(color=["#355c7d", "#3d7a8f", "#2a9d8f", "#6a994e", "#e9a23b", "#14a44d"])))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    if len(res):
        t1 = valid.copy()
        t1["Stage reached"] = t1[["S1", "S2", "S3", "S4", "S5"]].sum(axis=1)
        for i in range(1, 6):
            t1[f"S{i}"] = t1[f"S{i}"].map({True: "✅", False: "·"})
        show = [c_ for c_ in ["Symbol", "Stage reached", "S1", "S2", "S3", "S4", "S5", "Side", "LTP", "RelVol", "Gap %",
                              "Trigger", "VolX", "RSI", "Why"] if c_ in t1.columns]
        st.markdown("##### Every stock, and where it stopped")
        st.dataframe(t1.sort_values("Stage reached", ascending=False)[show], hide_index=True, width="stretch")
        if len(skipped):
            with st.expander(f"{len(skipped)} stock(s) skipped (incomplete Yahoo data)"):
                st.write(", ".join(f"{a} ({b})" for a, b in zip(skipped.Symbol, skipped.Why)))

# ------------------------------------------------------------ chart
with tabs[2]:
    if not prepared:
        st.info("No data yet.")
    else:
        names = list(final.Symbol) + [s for s in prepared if s not in list(final.Symbol)]
        sym = st.selectbox("Stock", names)
        pdx, dly = prepared[sym]
        days = sorted(set(pdx["date"]))[-2:]
        d = pdx[pdx["date"].isin(days)]
        D = days[-1]
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close, name="Price"))
        fig.add_trace(go.Scatter(x=d.index, y=d.VWAP, name="VWAP", line=dict(color="#f08c00", width=2)))
        fig.add_trace(go.Scatter(x=d.index, y=d.EMA9, name="EMA 9", line=dict(color="#1c7ed6", width=1)))
        fig.add_trace(go.Scatter(x=d.index, y=d.EMA21, name="EMA 21", line=dict(color="#ae3ec9", width=1)))
        t = d[d["date"] == D]
        if len(t) >= P["k"]:
            fig.add_hline(y=float(t.High.iloc[:P["k"]].max()), line_dash="dash", line_color="#14a44d", annotation_text="Opening range high")
            fig.add_hline(y=float(t.Low.iloc[:P["k"]].min()), line_dash="dash", line_color="#e03131", annotation_text="Opening range low")
        fig.update_layout(height=580, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=20, b=10),
                          xaxis=dict(rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[15.5, 9.25], pattern="hour")]))
        st.plotly_chart(fig, width="stretch")
        row = dly.loc[D]
        k = st.columns(4)
        k[0].metric("App VWAP", f"{t.VWAP.iloc[-1]:.2f}")
        k[1].metric("Last price", f"{t.Close.iloc[-1]:.2f}")
        k[2].metric("Candles today", len(t))
        k[3].metric("Opening volume vs avg", f"{row.ow / row.avg_ow:.1f}x" if row.avg_ow and row.avg_ow == row.avg_ow else "-")
        bv = st.number_input("Your broker's VWAP for this stock (optional check)", 0.0, 1000000.0, 0.0, 0.05)
        if bv > 0:
            diff = (t.VWAP.iloc[-1] / bv - 1) * 100
            (st.warning if abs(diff) > 0.15 else st.success)(
                f"App VWAP is {diff:+.2f}% from your broker's. " + ("Yahoo volumes differ from the exchange, so trust the broker's VWAP." if abs(diff) > 0.15 else "Close enough."))

# ------------------------------------------------------------ journal
with tabs[3]:
    j = st.session_state.journal
    if st.button("Check open trades (stop / target)", type="primary"):
        n_ = check_open(data, cfg)
        st.success(f"{n_} trade(s) closed.") if n_ else st.info("No open trade hit its stop or target yet.")
        j = st.session_state.journal
    op = j[j.status == "OPEN"]
    st.markdown(f"##### Open trades ({len(op)})")
    if len(op):
        ltp = {s: float(d.Close.iloc[-1]) for s, d in data.items()}
        o = op[["id", "date", "time", "symbol", "side", "entry", "stop", "target", "qty"]].copy()
        o["LTP"] = o.symbol.map(ltp)
        o["Open P&L"] = ((o.LTP - o.entry) * o.qty * o.side.map({"LONG": 1, "SHORT": -1})).round(0)
        st.dataframe(o, hide_index=True, width="stretch")
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
        for c_ in ("net", "gross", "costs", "r", "relvol"):
            cl[c_] = pd.to_numeric(cl[c_], errors="coerce")
        m = st.columns(5)
        m[0].metric("Trades", len(cl))
        m[1].metric("Win rate", f"{(cl.net > 0).mean() * 100:.0f}%")
        m[2].metric("Net P&L (Rs)", f"{cl.net.sum():,.0f}")
        m[3].metric("Costs paid (Rs)", f"{cl.costs.sum():,.0f}")
        m[4].metric("Average R", f"{cl.r.mean():.2f}")
        st.line_chart(cl.sort_values(["date", "time"]).net.cumsum().reset_index(drop=True), height=200)
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

# ------------------------------------------------------------ backtest
with tabs[4]:
    st.markdown("Runs the same five stages on the last sessions Yahoo has (about 40 trading days of 5-minute data). "
                "Entry is the **next candle's open** after the signal, stop is the other end of the opening range, "
                "exit at target, stop or the last candle of the day. Stop is assumed to hit first when both fall in one candle.")
    a, b = st.columns(2)
    nd = a.slider("Sessions to test", 5, 40, 25)
    topk = b.slider("Trades per day (first N signals)", 1, 5, 3)
    if st.button("Run backtest", type="primary"):
        with st.spinner("Testing..."):
            st.session_state.bt = backtest(data, P, nd, topk)
    tr = st.session_state.get("bt")
    if tr is not None:
        if tr.empty:
            st.info("No trades passed all the stages in this period with these settings. Try lowering the opening-volume or checks settings.")
        else:
            win = tr[tr.net > 0].net.sum()
            loss = -tr[tr.net < 0].net.sum()
            cum = tr.net.cumsum()
            m = st.columns(6)
            m[0].metric("Trades", len(tr))
            m[1].metric("Win rate", f"{(tr.net > 0).mean() * 100:.0f}%")
            m[2].metric("Net P&L (Rs)", f"{tr.net.sum():,.0f}")
            m[3].metric("Average R", f"{tr.R.mean():.2f}")
            m[4].metric("Profit factor", f"{win / loss:.2f}" if loss > 0 else "-")
            m[5].metric("Worst drawdown (Rs)", f"{(cum - cum.cummax()).min():,.0f}")
            st.line_chart(cum, height=220)
            st.dataframe(tr, hide_index=True, width="stretch")
            st.markdown('<div class="warn">A backtest uses past data, Yahoo volumes and a simple cost estimate. A small number of trades '
                        'can look good or bad by luck. Use it to reject weak settings, not to promise future profit.</div>', unsafe_allow_html=True)

# ------------------------------------------------------------ guide
with tabs[5]:
    st.markdown("""
**The funnel (each stage passes only the survivors to the next)**
1. **Quality:** enough turnover, a sensible price and enough daily movement (ATR), with complete data.
2. **In play:** volume in the opening range is well above the same stock's average of the last 14 days, and there is a gap from yesterday's close.
3. **Trigger:** a candle closes beyond the opening range (the first 15 minutes by default), price is on the matching side of VWAP, and the opening candle agrees with the direction.
4. **Momentum:** EMA 9/21 trend, RSI zone, recent volume, and room to run before yesterday's high or low. A set number of these must pass.
5. **Trade plan:** the stop (the other end of the range) is not too tight or too wide, the reward is clearly bigger than your costs, and the quantity fits your risk.

**Timing:** 9:15 to 9:30 only builds the opening range. Entries are best looked at from about 9:30 to 11:00, no new entries after the cut-off time, and paper trades close at about 3:15 pm.

**Rules for yourself**
- Paper trade for 3-4 weeks and read the journal, including costs, before using real money.
- Data comes from Yahoo Finance and can be delayed or have gaps. Compare with your broker screen.
- This is a learning tool, not investment advice. Most individual intraday traders lose money.
""")
