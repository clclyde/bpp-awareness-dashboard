"""BPP Brand Awareness Review (Streamlit prototype), editorial layout.

The page opens with the finding as a sentence, then the figures, then the evidence. Colours are the Project Swarm deck palette (navy, title blue,
yellow, red on white); fonts, colours and metric sizes live in .streamlit/config.toml. The only custom HTML is the yellow rule at the top and the red bar at the bottom.
KPI definitions follow the Marketing 3.0 KPI deck (Paid awareness module): reach, frequency, cost per 1,000 reached, video view-through,
engagement rate = engagements / reach. Awareness is reported as delivery and cost: reach measures exposure, not recall.

Run:  cd bpp_dashboard && ../.venv/bin/streamlit run app.py     (reads Supabase via .streamlit/secrets.toml, or the local snapshot data/bpp_snapshot.json)
"""
import hmac
import importlib
import os
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data as D

# A long-running server (Streamlit Cloud) can keep an older data.py in memory after a deploy that changed only that file, and then fails with
# AttributeError on a new function. Reload it whenever the file on disk is newer than the copy in memory.
_dm = Path(D.__file__).stat().st_mtime
if getattr(D, "_loaded_mtime", None) != _dm:
    D = importlib.reload(D)
    D._loaded_mtime = _dm

st.set_page_config(page_title="BPP Brand Awareness Review", page_icon=":material/shield:", layout="wide")

# Project Swarm palette, read from the deck file
NAVY, BLUE, YELLOW, RED = "#073763", "#0B3691", "#F1C232", "#D10000"
TEXT, MUTED, LINE, MIST = "#3F3F3F", "#737373", "#DCE3EA", "#F3F6FA"
FONT = "Montserrat, Open Sans, sans-serif"

_secret_files = [Path(__file__).parent / ".streamlit" / "secrets.toml", Path.cwd() / ".streamlit" / "secrets.toml", Path.home() / ".streamlit" / "secrets.toml"]
_conf = None
if any(f.exists() for f in _secret_files):  # only then touch st.secrets (Streamlit shows a red "No secrets found" box otherwise)
    try:
        _conf = dict(st.secrets["supabase"]) if "supabase" in st.secrets else None
    except Exception:
        _conf = None
if _conf is None and os.environ.get("PULSE_DB_HOST"):  # self-hosted: the same settings as environment variables
    _env = {k: os.environ.get(v) for k, v in (("host", "PULSE_DB_HOST"), ("user", "PULSE_DB_USER"), ("password", "PULSE_DB_PASSWORD"))}
    if all(_env.values()):
        _conf = {**_env, "port": os.environ.get("PULSE_DB_PORT", "5432"), "dbname": os.environ.get("PULSE_DB_NAME", "postgres"), "sslmode": os.environ.get("PULSE_DB_SSLMODE", "require")}


# ---------- access password (optional) ----------
# One shared password for the people allowed in, while the app itself stays public. Set `app_password` in the app's Secrets (above the [supabase] block,
# or inside it) or the APP_PASSWORD environment variable. Without it the app opens as before. It is a shared secret with no lockout, not an account system.
_pw = None
if any(f.exists() for f in _secret_files):
    try:
        _pw = st.secrets.get("app_password") or (_conf or {}).get("app_password")
    except Exception:
        _pw = None
_pw = _pw or os.environ.get("APP_PASSWORD")
if _pw and not st.session_state.get("authed"):
    st.html(f'<div style="height:8px;background:{YELLOW}"></div>')
    st.title("BPP Brand Awareness Review")
    st.markdown("This dashboard is for invited viewers. Enter the access password you were given.")
    with st.form("login"):
        entered = st.text_input("Access password", type="password")
        go = st.form_submit_button("Open dashboard")
    if go:
        if hmac.compare_digest(entered.encode(), str(_pw).encode()):
            st.session_state["authed"] = True
            st.rerun()
        time.sleep(1)   # slows down guessing a little
        st.error("That password is not right.")
    st.stop()


@st.cache_data(ttl=300, show_spinner="Loading BPP data...")
def load(conf):
    return D.load(conf)


try:
    if not _conf and not D.snapshot_exists():
        raise RuntimeError("no database settings and no local data snapshot")
    S = load(_conf)
except Exception as e:  # database unreachable or wrong password: show the local snapshot if there is one, loudly
    _why = f"{type(e).__name__}: {str(e).strip().splitlines()[0][:160]}"
    if not D.snapshot_exists():
        st.error(f"The dashboard could not load its data ({_why}). Check the [supabase] secrets (host, user, password) of this app, or ask the dashboard owner. See README.md.")
        st.stop()
    if not _conf:
        raise
    st.warning(f"Supabase could not be reached ({_why}). Showing the local snapshot instead, which may be out of date.")
    S = load(None)
ADS, POSTS, TT = S["ads"], S["posts"], S["tiktok"]
MONTHS = sorted(ADS["month"].unique())
LAST = D.last_full_month(ADS, S["built_at"])
BUILT_MONTH = pd.Period(S["built_at"], "M")


# ---------- helpers ----------
def peso(x, dec=0):
    return "n/a" if pd.isna(x) else f"{'-' if x < 0 else ''}₱{abs(x):,.{dec}f}"


def num(x):
    return "n/a" if pd.isna(x) else f"{x:,.0f}"


def pct(x, dec=1, sign=False):
    return "n/a" if pd.isna(x) else (f"{x:+.{dec}%}" if sign else f"{x:.{dec}%}")


def short(x):
    """1,014,541 -> '1.0 million'; 48,200 -> '48,200'."""
    return "n/a" if pd.isna(x) else (f"{x / 1e6:.1f} million" if x >= 1e6 else f"{x:,.0f}")


def mlabel(p):
    return p.strftime("%b %Y")


def change(c, p):
    return None if (c is None or p is None or pd.isna(c) or pd.isna(p) or p == 0) else c / p - 1


def metric(label, value, chg, higher_better=True, series=None, help=None, vs=None, baseline=False):
    """Native st.metric. Change vs the prior period; green or red by whether the move is good, grey when it is flat (under 2%).
    baseline=True is for the reference period of a comparison: a grey "Baseline" pill (no arrow, no number) takes the place of the change row,
    so its trend line sits level with the compared period's."""
    if chg is None:
        delta, colour = None, "off"
    else:
        delta = f"{chg:+.1%}"
        colour = "off" if abs(chg) < 0.02 else ("normal" if higher_better else "inverse")
    if higher_better is None:   # a change that is neither good nor bad (spend)
        colour = "off"
    kw = {"chart_data": [float(v) for v in series if not pd.isna(v)], "chart_type": "area"} if series is not None and len(series) > 1 else {}
    if baseline:
        st.metric(label, value, delta="Baseline", delta_color="off", delta_arrow="off", help=help, **kw)
        return
    st.metric(label, value, delta=delta, delta_color=colour, delta_description=f"vs {vs or VS}" if chg is not None else None, help=help, **kw)


def stripe():
    """A plain yellow rule across the top of the page."""
    st.html(f'<div style="height:8px;background:{YELLOW}"></div>')


def style_fig(fig, height=300, tickprefix="", tickformat=None):
    fig.update_layout(height=height, margin=dict(l=4, r=76, t=24, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
                      font=dict(color=TEXT, family=FONT, size=12), hoverlabel=dict(bgcolor="#FFFFFF", font_color=TEXT, font_family=FONT))
    fig.update_xaxes(showgrid=False, linecolor=LINE, tickfont=dict(color=MUTED), tickangle=0, type="date", tickformat="%b %y", nticks=7)
    fig.update_yaxes(gridcolor="#E9EEF3", zeroline=False, tickfont=dict(color=MUTED), tickprefix=tickprefix, tickformat=tickformat)
    return fig


def show(fig, key):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


def trend(title, xs, ys, flags, label_fmt, hover_fmt, tickformat, tickprefix="", best="max", zero=False, key=""):
    """One-series line chart. Direct labels on the best point and the latest point only; yellow markers = incomplete export months."""
    ys = list(ys)
    marker = dict(size=9, color=[YELLOW if f else BLUE for f in flags], line=dict(width=1.5, color=NAVY))
    fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines+markers", line=dict(color=BLUE, width=2.5), marker=marker,
                               hovertemplate="%{x|%b %Y}: " + hover_fmt + "<extra></extra>"))
    valid = [i for i, v in enumerate(ys) if not pd.isna(v)]
    if valid:
        pick = max(valid, key=lambda i: ys[i]) if best == "max" else min(valid, key=lambda i: ys[i])
        last = valid[-1]
        if pick != last:
            fig.add_annotation(x=xs[pick], y=ys[pick], text=f"<b>{label_fmt(ys[pick])}</b>", showarrow=False, yshift=16, font=dict(color=NAVY, size=12))
        fig.add_annotation(x=xs[last], y=ys[last], text=f"<b>{label_fmt(ys[last])}</b>", showarrow=False, xanchor="left", xshift=12, font=dict(color=NAVY, size=12))
    if zero:
        fig.update_yaxes(rangemode="tozero")
    st.markdown(f"**{title}**")
    show(style_fig(fig, 280, tickprefix=tickprefix, tickformat=tickformat), key)
    if valid:
        i = pick
        st.caption(f"{'Highest' if best == 'max' else 'Lowest'}: {label_fmt(ys[i])} in {mlabel(pd.Period(xs[i], 'M'))}. Latest: {label_fmt(ys[valid[-1]])}.")


# ---------- sidebar: month range ----------
def _presets():
    ytd0 = max(m for m in MONTHS if m.year == LAST.year and m.month == 1) if any(m.year == LAST.year and m.month == 1 for m in MONTHS) else MONTHS[0]
    return {"Last full month": (LAST, LAST), "Last 3 months": (LAST - 2, LAST), f"Year to date ({LAST.year})": (ytd0, LAST), "All data": (MONTHS[0], MONTHS[-1])}


def _on_preset():
    st.session_state["m0"], st.session_state["m1"] = _presets()[st.session_state["preset"]]


st.session_state.setdefault("m0", LAST)
st.session_state.setdefault("m1", LAST)
with st.sidebar:
    st.subheader("Reporting Months")
    st.selectbox("Quick range", list(_presets()), key="preset", on_change=_on_preset)
    st.selectbox("From month", MONTHS, key="m0", format_func=mlabel)
    st.selectbox("To month", MONTHS, key="m1", format_func=mlabel)
    st.caption("The Ads Manager exports are monthly, so this view works in whole months.")
    INTERNAL = st.toggle("Internal view", key="internal", help="Adds the data source and the data-quality check (Ads Manager vs Ad Spend Report). Leave it off when presenting to the client. "
                         "It is a display switch, not security: anyone with the link can turn it on.")
    if INTERNAL:
        st.caption(f"Source: {S['source']}.")
    with st.expander("How the numbers are defined", icon=":material/info:"):
        st.markdown(
            "Follows the Marketing 3.0 KPI deck, Paid awareness module.\n"
            "- **Reach**: sum of the campaign reach rows of each monthly Ads Manager export. Campaigns overlap, so unique reach is lower. Multi-month ranges show the monthly average\n"
            "- **Avg frequency**: impressions / reach over the month. The deck's alert level (3) is weekly\n"
            "- **Cost per 1,000 reached**: ad spend / reach x 1,000\n"
            "- **Video view-through**: ThruPlays / impressions (Meta ThruPlay = 15 seconds or completion)\n"
            "- **Engagement rate**: engagements (reactions + comments + shares) / reach, for Facebook page posts\n"
            "- **TikTok**: views and engagement only (no reach in the SSOT), so engagement per view\n"
            "- **Not in the SSOT yet**: weekly reach, target audiences (share of audience), follower growth, brand health"
        )

M0, M1 = st.session_state["m0"], st.session_state["m1"]
if M0 > M1:
    st.info("Pick a start month that is not after the end month.")
    st.stop()
P0, P1 = D.prior_months(M0, M1)
RANGE = mlabel(M0) if M0 == M1 else f"{mlabel(M0)} to {mlabel(M1)}"
VS = mlabel(P0) if P0 == P1 else f"prior {(M1 - M0).n + 1} months"
HAS_PRIOR = P0 >= MONTHS[0]

cur = D.paid(ADS, M0, M1)
pre = D.paid(ADS, P0, P1) if HAS_PRIOR else None
org, org_p = D.organic(POSTS, M0, M1), (D.organic(POSTS, P0, P1) if HAS_PRIOR else None)
tk, tk_p = D.tiktok(TT, M0, M1), (D.tiktok(TT, P0, P1) if HAS_PRIOR else None)
chg = lambda a, b, k: None if b is None else change(a[k], b[k])

pm = D.paid_monthly(ADS)
pm = pm[(pm.index <= M1)].tail(12)
pm = pm[pm.index < BUILT_MONTH] if M1 < BUILT_MONTH else pm          # the month still running is partial
CHK = D.spend_check(ADS, S["ref"])
GAPS = set(CHK[CHK["difference"] < -1].index)                          # Ads Manager export has less spend than the Ad Spend Report: probably incomplete

# ---------- masthead ----------
stripe()
left, right = st.columns([3, 1], vertical_alignment="bottom")
left.caption("BPP, Budol-Proof Pinoy · Brand awareness review")
right.caption(f"Data as of {S['built_at']:%d %b %Y}", text_alignment="right")
if M1 >= BUILT_MONTH:
    st.warning(f"{mlabel(M1)} was still running when the data was loaded ({S['built_at']:%d %b}): its numbers are partial.", icon=":material/schedule:")

tab_cmp, *tabs = st.tabs(["First vs Second Half", "Overview", "Awareness Trend", "Content", "Channel Diagnostics"])

# ===== First vs second half (default view) =====
with tab_cmp:
    LASTM = [m for m in MONTHS if m <= LAST]
    DEFAULT_CMP_START = pd.Period("2025-10", "M")                          # agreed default: the first period starts in Oct 2025
    st.title("Brand Awareness: First Half vs Second Half")
    sel1, sel2, sel3 = st.columns([1, 1, 2], vertical_alignment="bottom")
    N = sel1.selectbox("Months per period", [3, 4, 6], index=2, key="cmp_n", help="The first period is followed straight away by a second period of the same length.")
    STARTS = [m for i, m in enumerate(LASTM) if i + 2 * N <= len(LASTM)]
    if st.session_state.get("cmp_start") not in STARTS:
        st.session_state["cmp_start"] = DEFAULT_CMP_START if DEFAULT_CMP_START in STARTS else STARTS[0]   # default view: Oct 2025 to Mar 2026 vs Apr to Sep 2026
    A0 = sel2.selectbox("First period starts", STARTS, key="cmp_start", format_func=mlabel)
    A1, B0, B1 = A0 + (N - 1), A0 + N, A0 + (2 * N - 1)
    A_NAME, B_NAME = f"First {N} months", f"Next {N} months"
    A_TITLE, B_TITLE = f"First {N} Months", f"Next {N} Months"       # headings in Title Case, running text uses the lowercase names
    A_RNG, B_RNG = f"{mlabel(A0)} to {mlabel(A1)}", f"{mlabel(B0)} to {mlabel(B1)}"
    sel3.caption("This view has its own period selector. The sidebar months drive the other tabs.")

    ca, cb = D.paid(ADS, A0, A1), D.paid(ADS, B0, B1)
    oa, ob = D.organic(POSTS, A0, A1), D.organic(POSTS, B0, B1)
    ta, tb = D.tiktok(TT, A0, A1), D.tiktok(TT, B0, B1)
    spm_a, spm_b = ca["spend"] / N, cb["spend"] / N                      # spend per month
    g = lambda k, a=ca, b=cb: change(b[k], a[k])
    rc, cc, sc = g("reach_avg"), g("cpr"), change(spm_b, spm_a)
    rp, pv, er = change(ob["reach_per_post"], oa["reach_per_post"]), change(ob["views"], oa["views"]), change(ob["er"], oa["er"])
    mv = lambda c: f"{'grew' if c >= 0 else 'fell'} {abs(c):.0%}"
    intro = []
    if None not in (rp, pv, er):
        intro.append(f"On the Facebook page, reach per post {mv(rp)} ({num(oa['reach_per_post'])} to {num(ob['reach_per_post'])}) and post views {mv(pv)}"
                     f"{', while' if (er < 0) != (min(rp, pv) < 0) else ', and'} the engagement rate {mv(er)} ({pct(oa['er'], 2)} to {pct(ob['er'], 2)}).")
    if rc is not None and cc is not None:
        intro.append(f"In Facebook paid awareness, reach per month {'grew' if rc >= 0 else 'fell'} **{abs(rc):.1%}**, from {short(ca['reach_avg'])} to {short(cb['reach_avg'])}. "
                     f"Cost per 1,000 reached went {'down' if cc <= 0 else 'up'} **{abs(cc):.1%}**, from {peso(ca['cpr'], 2)} to {peso(cb['cpr'], 2)}"
                     + (f", and monthly Facebook ad spend {'dropped' if sc < 0 else 'rose'} {abs(sc):.1%} ({peso(spm_a)} to {peso(spm_b)})." if sc is not None else "."))
    if intro:
        st.markdown(" ".join(intro))
    if INTERNAL:
        bad = [m for m in GAPS if A0 <= m <= B1]
        if bad:
            st.warning("Some Ads Manager exports in these periods look incomplete (spend below the Ad Spend Report): " + ", ".join(mlabel(m) for m in sorted(bad))
                       + ". Spend and reach for those months are understated, so check before showing a cost comparison to the client.", icon=":material/warning:")

    st.subheader("Facebook Page and TikTok")
    _tt_months = set(TT["month"].unique())                               # TikTok is only comparable when every month of both periods has videos in the SSOT
    TT_GAPS = [m for m in (A0 + i for i in range(2 * N)) if m not in _tt_months]
    TT_OK = not TT_GAPS
    _cov = lambda m0, n_: [m for m in (m0 + i for i in range(n_)) if m in _tt_months]   # months of a period that have TikTok videos

    def tt_partial(m0, n_):
        """Label for a period whose TikTok total covers only some of its months (the rest are missing in the SSOT, not zero)."""
        got = _cov(m0, n_)
        return None if len(got) == n_ else (", ".join(mlabel(m) for m in got) + f" only ({len(got)} of {n_} months)" if got else "no months with data")
    fl, fr = st.columns(2, gap="large", border=True)
    with fl:
        st.markdown(f"**{A_TITLE}** · {A_RNG}")
        f1, f2 = st.columns(2)
        f1.metric("Posts published", num(oa["posts"]))
        f1.metric("Engagement rate", pct(oa["er"], 2))
        f2.metric("Average reach per post", num(oa["reach_per_post"]))
        f2.metric("Post views", num(oa["views"]))
        _pa = tt_partial(A0, N)
        st.metric("TikTok video views" + (" (partial)" if _pa else ""), num(ta["views"]) if _cov(A0, N) else "n/a",
                  help=None if not _pa else "The SSOT has no TikTok videos for " + ", ".join(mlabel(m) for m in TT_GAPS if A0 <= m <= A1) + ", so this total is not the whole period.")
        if _pa:   # says outright that it is the TikTok views figure, not the whole box
            st.caption("TikTok video views: no data for this period." if _pa == "no months with data" else f"TikTok video views cover {_pa}.")
    with fr:
        st.markdown(f"**{B_TITLE}** · {B_RNG}")
        f1, f2 = st.columns(2)
        with f1:
            metric("Posts published", num(ob["posts"]), change(ob["posts"], oa["posts"]), True, vs=A_NAME.lower())
            metric("Engagement rate", pct(ob["er"], 2), change(ob["er"], oa["er"]), True, vs=A_NAME.lower())
        with f2:
            metric("Average reach per post", num(ob["reach_per_post"]), change(ob["reach_per_post"], oa["reach_per_post"]), True, vs=A_NAME.lower())
            metric("Post views", num(ob["views"]), change(ob["views"], oa["views"]), True, vs=A_NAME.lower())
        _pb = tt_partial(B0, N)
        metric("TikTok video views" + (" (partial)" if _pb else ""), num(tb["views"]) if _cov(B0, N) else "n/a", change(tb["views"], ta["views"]) if TT_OK else None, True, vs=A_NAME.lower())
        if _pb:   # says outright that it is the TikTok views figure, not the whole box
            st.caption("TikTok video views: no data for this period." if _pb == "no months with data" else f"TikTok video views cover {_pb}.")
    if INTERNAL and not TT_OK:   # internal view only: the client sees the "(partial)" label and the months it covers
        st.caption(f"The SSOT has no TikTok videos for {', '.join(mlabel(m) for m in TT_GAPS)}. The first period's TikTok total covers only the months that have data, so it is not compared with the second period (no change shown).")

    pm_all = D.paid_monthly(ADS)
    sa, sb = pm_all.loc[A0:A1], pm_all.loc[B0:B1]
    st.subheader("Paid Awareness on Facebook")
    box = st.container(border=True)                                      # one row per metric so each pair sits level
    hl, hr = box.columns(2, gap="large")
    hl.subheader(A_TITLE)
    hl.caption(A_RNG)
    hr.subheader(B_TITLE)
    hr.caption(B_RNG)
    fa = lambda c: f"{c['frequency']:.2f}" if not pd.isna(c["frequency"]) else "n/a"
    for label, va, vb, ch, better, kcol, hp in (("Reach (monthly average)", num(ca["reach_avg"]), num(cb["reach_avg"]), rc, True, "reach", None),
                                                 ("Cost per 1,000 reached", peso(ca["cpr"], 2), peso(cb["cpr"], 2), cc, False, "cpr", "Ad spend / reach x 1,000. Lower is better."),
                                                 ("Ad spend (per month)", peso(spm_a), peso(spm_b), sc, None, "spend", "Ads Manager, ex-VAT."),
                                                 ("Average frequency", fa(ca), fa(cb), g("frequency"), False, "frequency", "Impressions / reach over the month.")):
        ml, mr = box.columns(2, gap="large")
        with ml:
            metric(label, va, None, better, sa[kcol], hp, baseline=True)
        with mr:
            metric(label, vb, ch, better, sb[kcol], hp, vs=A_NAME.lower())

    # ----- cost efficiency: unit costs, and what the same budget bought -----
    st.subheader("Cost Efficiency")
    st.caption("Paid Facebook ads (Ads Manager). Unit costs (left) should go down; what each ₱1,000 of spend buys (right) should go up. Together they show whether the same budget delivers more.")
    ua, ub = D.unit_costs(ADS, A0, A1), D.unit_costs(ADS, B0, B1)
    _vs_ef = A_NAME.lower()
    _cost_rows = [("Cost per mille (CPM)", "cpm", 2, "Cost per 1,000 impressions = ad spend / impressions x 1,000. Lower is better."),
                  ("Cost per 1,000 reached", "cpr1000", 2, "Ad spend / reach x 1,000. Lower is better."),
                  ("Cost per engagement", "cpe", 3, "Ad spend / post engagements (reactions, comments, shares, clicks as counted by Ads Manager). Lower is better.")]
    if ua["clicks_ok"] and ub["clicks_ok"]:
        _cost_rows.append(("Cost per click", "cpc", 2, "Ad spend / clicks (all). Lower is better."))
    if ua["tp_ok"] and ub["tp_ok"]:
        _cost_rows.append(("Cost per ThruPlay", "cptp", 3, "Video ad spend / ThruPlays (15 seconds or completion). Lower is better."))
    _out_rows = [("Impressions per ₱1,000", "impr_per_k", "Impressions delivered for every ₱1,000 of ad spend. Higher is better."),
                 ("Reach per ₱1,000", "reach_per_k", "Reach for every ₱1,000 of ad spend. Higher is better."),
                 ("Engagements per ₱1,000", "eng_per_k", "Post engagements for every ₱1,000 of ad spend. Higher is better.")]
    ef = st.container(border=True)                                       # one row per figure, like the paid box above, so each pair sits level
    e1, e2 = ef.columns(2, gap="large")
    e1.subheader(A_TITLE)
    e1.caption(A_RNG)
    e2.subheader(B_TITLE)
    e2.caption(B_RNG)
    ef.caption("Costs (lower is better)")
    for label, k, dec, hp in _cost_rows:
        ml, mr = ef.columns(2, gap="large")
        with ml:
            metric(label, peso(ua[k], dec), None, False, help=hp, baseline=True)
        with mr:
            metric(label, peso(ub[k], dec), change(ub[k], ua[k]), False, help=hp, vs=_vs_ef)
    ef.caption("What each ₱1,000 of spend bought (higher is better)")
    for label, k, hp in _out_rows:
        ml, mr = ef.columns(2, gap="large")
        with ml:
            metric(label, num(ua[k]), None, True, help=hp, baseline=True)
        with mr:
            metric(label, num(ub[k]), change(ub[k], ua[k]), True, help=hp, vs=_vs_ef)
    if not (ua["clicks_ok"] and ub["clicks_ok"]):
        st.caption("Cost per click and cost per ThruPlay appear when both periods are from Mar 2026 onward; earlier data does not include clicks or ThruPlays.")
    with st.expander("Unit costs by campaign type", icon=":material/stacked_bar_chart:"):
        st.markdown("Reach, boosting (engagement and video views) and page-like campaigns have very different costs, so the blended figures above also move with the mix of campaigns. Compare like with like here.")
        oa_, ob_ = D.unit_costs_by_objective(ADS, A0, A1), D.unit_costs_by_objective(ADS, B0, B1)
        _names = {"reach": "Reach", "boosting": "Boosting (engagement, views)", "pagelikes": "Page likes", "other": "Other"}
        _rows = []
        for obj in [o for o in _names if o in oa_.index or o in ob_.index]:
            a_r = oa_.loc[obj] if obj in oa_.index else None
            b_r = ob_.loc[obj] if obj in ob_.index else None
            _g = lambda r, k: float("nan") if r is None else float(r[k])
            _rows.append({"Campaign type": _names[obj], f"Spend, {A_NAME} (₱)": _g(a_r, "spend"), f"Spend, {B_NAME} (₱)": _g(b_r, "spend"),
                          "CPM, change": change(_g(b_r, "cpm"), _g(a_r, "cpm")), "Cost per 1,000 reached, change": change(_g(b_r, "cpr1000"), _g(a_r, "cpr1000")),
                          "Cost per engagement, change": change(_g(b_r, "cpe"), _g(a_r, "cpe"))})
        if _rows:
            st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch", column_config={
                f"Spend, {A_NAME} (₱)": st.column_config.NumberColumn(format="localized"), f"Spend, {B_NAME} (₱)": st.column_config.NumberColumn(format="localized"),
                "CPM, change": st.column_config.NumberColumn(format="percent"), "Cost per 1,000 reached, change": st.column_config.NumberColumn(format="percent"),
                "Cost per engagement, change": st.column_config.NumberColumn(format="percent")})
        st.caption(f"Change is the {B_NAME.lower()} against the {A_NAME.lower()}; negative means cheaper. Spend and campaign mix shift between the periods.")

    def split_trend(title, col, avgs, label_fmt, hover_fmt, tickformat, tickprefix="", zero=False, key=""):
        """Monthly line across both periods; each period in its own colour with a dashed line at its average."""
        fig = go.Figure()
        for ser, color, name, avg in ((sa, "#7F8FA3", A_NAME, avgs[0]), (sb, BLUE, B_NAME, avgs[1])):
            xs = [m.to_timestamp() for m in ser.index]
            fig.add_trace(go.Scatter(x=xs, y=ser[col], mode="lines+markers", line=dict(color=color, width=2.5), marker=dict(size=8, color=color),
                                     name=name, hovertemplate="%{x|%b %Y}: " + hover_fmt + "<extra></extra>"))
            fig.add_shape(type="line", x0=xs[0], x1=xs[-1], y0=avg, y1=avg, line=dict(color=color, width=1.5, dash="dash"))
            fig.add_annotation(x=xs[0], y=avg, text=f"<b>{label_fmt(avg)}</b> avg", showarrow=False, xanchor="left", yanchor="bottom", yshift=6, font=dict(color=color, size=12))
        if zero:
            fig.update_yaxes(rangemode="tozero")
        st.markdown(f"**{title}**")
        show(style_fig(fig, 280, tickprefix=tickprefix, tickformat=tickformat), key)

    a_, b_ = st.columns(2, gap="large")
    with a_:
        split_trend("Reach by month", "reach", (ca["reach_avg"], cb["reach_avg"]), lambda v: short(v), "%{y:,.0f}", ",.0f", key="cmp1")
    with b_:
        split_trend("Cost per 1,000 reached by month", "cpr", (ca["cpr"], cb["cpr"]), lambda v: peso(v, 2), "₱%{y:,.2f}", ",.0f", tickprefix="₱", key="cmp2")
    st.caption(f"Dashed lines are the average of each period (for cost per 1,000: total spend / total reach) ({A_NAME.lower()} in grey, {B_NAME.lower()} in blue). Reach adds up campaign reach, so the number of different people is lower.")

    def _row(label, a, b, chg_, fmt):
        return {"Metric": label, A_NAME + " (" + A_RNG + ")": fmt(a), B_NAME + " (" + B_RNG + ")": fmt(b), "Change": pct(chg_, 1, True) if chg_ is not None else "n/a"}
    rows = [_row("Reach (monthly average)", ca["reach_avg"], cb["reach_avg"], rc, num),
            _row("Cost per 1,000 reached", ca["cpr"], cb["cpr"], cc, lambda v: peso(v, 2)),
            _row("Ad spend (total)", ca["spend"], cb["spend"], change(cb["spend"], ca["spend"]), peso),
            _row("Ad spend (per month)", spm_a, spm_b, sc, peso),
            _row("Average frequency", ca["frequency"], cb["frequency"], g("frequency"), lambda v: "n/a" if pd.isna(v) else f"{v:.2f}"),
            _row("Cost per 1,000 impressions (CPM)", ua["cpm"], ub["cpm"], change(ub["cpm"], ua["cpm"]), lambda v: peso(v, 2)),
            _row("Cost per post engagement", ua["cpe"], ub["cpe"], change(ub["cpe"], ua["cpe"]), lambda v: peso(v, 3)),
            _row("Impressions per ₱1,000", ua["impr_per_k"], ub["impr_per_k"], change(ub["impr_per_k"], ua["impr_per_k"]), num),
            _row("Engagements per ₱1,000", ua["eng_per_k"], ub["eng_per_k"], change(ub["eng_per_k"], ua["eng_per_k"]), num),
            _row("Facebook posts published", oa["posts"], ob["posts"], change(ob["posts"], oa["posts"]), num),
            _row("Facebook engagement rate", oa["er"], ob["er"], change(ob["er"], oa["er"]), lambda v: pct(v, 2)),
            _row("Facebook reach per post", oa["reach_per_post"], ob["reach_per_post"], change(ob["reach_per_post"], oa["reach_per_post"]), num)]
    with st.expander("All figures side by side", icon=":material/table:"):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Change is the second period against the first. For cost per 1,000 reached and frequency, lower is better. Awareness is reported as delivery and cost: reach measures exposure, not recall.")

# ===== Overview =====
with tabs[0]:
    reach_now = cur["reach"] if cur["months"] == 1 else cur["reach_avg"]
    if pd.isna(reach_now) or pd.isna(cur["cpr"]):
        st.title(f"Brand Awareness, {RANGE}")
    else:
        lead = f"Facebook paid reach hit {short(reach_now)} in {RANGE}" if cur["months"] == 1 else f"Facebook paid reach averaged {short(reach_now)} a month, {RANGE}"
        st.title(f"{lead}, at {peso(cur['cpr'], 2)} per 1,000 reached.")

    parts = []
    rc, cc = chg(cur, pre, "reach_avg"), chg(cur, pre, "cpr")
    if rc is not None and cc is not None:
        parts.append(f"That is {abs(rc):.1%} {'more' if rc >= 0 else 'less'} reach than {VS}, at a cost per 1,000 {'up' if cc >= 0 else 'down'} {abs(cc):.1%}, "
                     f"with each person reached about {cur['frequency']:.1f} times on average.")
    if org["posts"]:
        parts.append(f"Facebook posts reached {num(org['reach_per_post'])} people each with a {pct(org['er'], 2)} engagement rate; TikTok videos drew {num(tk['views'])} views.")
    parts.append("Reach adds up campaign reach, so the number of different people is lower.")
    st.markdown(" ".join(parts))

    st.subheader("Paid Awareness on Facebook")
    c1, c2, c3 = st.columns(3)
    with c1:
        metric("Reach (monthly)", num(reach_now), chg(cur, pre, "reach_avg"), True, pm["reach"], "Sum of campaign reach per month. Multi-month ranges show the monthly average. Share of target audience: pending.")
    with c2:
        metric("Cost per 1,000 reached", peso(cur["cpr"], 2), chg(cur, pre, "cpr"), False, pm["cpr"], "Ad spend / reach x 1,000. Only fair between reach campaigns.")
    with c3:
        metric("Average frequency", f"{cur['frequency']:.2f}" if not pd.isna(cur["frequency"]) else "n/a", chg(cur, pre, "frequency"), False, pm["frequency"],
               "Impressions / reach over the month. The deck's alert level of 3 is weekly.")
    d1, d2, d3 = st.columns(3)
    with d1:
        metric("Ad spend", peso(cur["spend"]), chg(cur, pre, "spend"), None, pm["spend"], f"{cur['campaigns']} campaigns. Ads Manager, ex-VAT.")
    with d2:
        metric("Video view-through", pct(cur["thru_rate"], 1), chg(cur, pre, "thru_rate"), True, pm["thru_rate"], "ThruPlays / impressions.")
    d3.caption("Targets are pending sign-off, so nothing here is judged on target yet.")

    left_col, right_col = st.columns(2, gap="large", border=True)   # a frame per group so Facebook page and TikTok read as separate things
    with left_col:
        st.subheader("Facebook Page")
        o1, o2 = st.columns(2)
        with o1:
            metric("Posts published", num(org["posts"]), chg(org, org_p, "posts"), True)
            metric("Engagement rate", pct(org["er"], 2), chg(org, org_p, "er"), True, help="Reactions + comments + shares, divided by reach.")
        with o2:
            metric("Average reach per post", num(org["reach_per_post"]), chg(org, org_p, "reach_per_post"), True, help="Lifetime reach of each post, as exported.")
            metric("Post views", num(org["views"]), chg(org, org_p, "views"), True)
    with right_col:
        st.subheader("TikTok")
        t1, t2 = st.columns(2)
        with t1:
            metric("Videos posted", num(tk["videos"]), chg(tk, tk_p, "videos"), True)
            metric("Engagement per view", pct(tk["eng_per_view"], 1), chg(tk, tk_p, "eng_per_view"), True, help="No reach for TikTok in the SSOT, so engagements are divided by views.")
        with t2:
            metric("Video views", num(tk["views"]), chg(tk, tk_p, "views"), True, help=f"{num(tk['views_per_video'])} per video.")
            metric("Engagements", num(tk["engagements"]), chg(tk, tk_p, "engagements"), True, help="Likes, comments, shares.")
        _tt_all = set(TT["month"].unique())
        _gap = [m for m in sorted({*(M0 + i for i in range((M1 - M0).n + 1)), *((P0 + i for i in range((P1 - P0).n + 1)) if HAS_PRIOR else ())})
                if TT["month"].min() <= m <= TT["month"].max() and m not in _tt_all]
        if INTERNAL and _gap:   # a month with no video rows in the SSOT is missing data, not a month without posts (internal view only)
            st.caption("The SSOT has no TikTok videos for " + ", ".join(mlabel(m) for m in _gap) + ", so zeros and changes here reflect missing data.")

    camps = D.campaigns(ADS, M0, M1)
    camps = camps[(camps["reach"] > 0) & (camps["objective"] == "reach")]   # cost per 1,000 reached only compares reach campaigns
    st.subheader("What to Look at Next")
    if len(camps) >= 2:
        lo, hi = camps.loc[camps["cpr"].idxmin()], camps.loc[camps["cpr"].idxmax()]
        st.markdown(f"Among reach campaigns, **{lo['name'][:60]}** was cheapest at {peso(lo['cpr'], 2)} per 1,000 reached and **{hi['name'][:60]}** the costliest at {peso(hi['cpr'], 2)}. "
                    "Agree target audiences per platform so reach can be reported as a share of audience and judged against a target.")
    else:
        st.markdown("Agree target audiences per platform so reach can be reported as a share of audience and judged against a target.")
    st.caption("Written by the dashboard from the numbers above. Reach measures exposure, not recall.")

# ===== Awareness trend =====
with tabs[1]:
    st.title("How Awareness Moved, Month by Month")
    st.markdown(f"Paid awareness on Facebook up to {mlabel(M1)}. Weekly reach and target audiences are not in the SSOT yet, so the unit is the month.")
    xs = [m.to_timestamp() for m in pm.index]
    flags = [INTERNAL and m in GAPS for m in pm.index]
    a, b = st.columns(2, gap="large")
    with a:
        trend("Reach", xs, pm["reach"], flags, lambda v: short(v), "%{y:,.0f}", ",.0f", key="tr1")
    with b:
        trend("Average frequency", xs, pm["frequency"], flags, lambda v: f"{v:.2f}", "%{y:.2f}", ".1f", best="max", zero=True, key="tr2")
    c, d = st.columns(2, gap="large")
    with c:
        trend("Cost per 1,000 reached", xs, pm["cpr"], flags, lambda v: peso(v, 2), "₱%{y:,.2f}", ",.0f", tickprefix="₱", best="min", key="tr3")
    with d:
        trend("Video view-through", xs, pm["thru_rate"], flags, lambda v: pct(v, 1), "%{y:.1%}", ".0%", key="tr4")
    note = "Reach is the sum of campaign reach per month, so it overstates unique reach. Months before January 2026 use the 2025 exports."
    if INTERNAL:
        note = "Yellow markers are months whose Ads Manager export has less spend than the Ad Spend Report, so the export is probably incomplete (see the data check below). " + note
    st.caption(note)

    st.subheader("Paid Campaigns", anchor=False)
    st.caption(f"{RANGE}, largest spend first")
    camp = D.campaigns(ADS, M0, M1).head(10)
    cdf = pd.DataFrame({"Campaign": camp["name"].str[:78], "Type": camp["objective"], "Spend (₱)": camp["spend"], "Reach": camp["reach"],
                        "Frequency": camp["frequency"], "Cost per 1,000 (₱)": camp["cpr"], "View-through": camp["thru_rate"]})
    st.dataframe(cdf, hide_index=True, width="stretch", column_config={
        "Campaign": st.column_config.TextColumn(width="medium"), "Type": st.column_config.TextColumn(width="small"),
        "Spend (₱)": st.column_config.NumberColumn(format="localized"),
        "Reach": st.column_config.ProgressColumn(format="localized", min_value=0, max_value=float(max(camp["reach"].max(), 1))),
        "Frequency": st.column_config.NumberColumn(format="%.2f"),
        "Cost per 1,000 (₱)": st.column_config.NumberColumn(format="%.2f"),
        "View-through": st.column_config.NumberColumn(format="percent")})
    if INTERNAL:
        bad = CHK[CHK["difference"].abs() > 1]
        with st.expander("Data check: Ads Manager spend vs Ad Spend Report", icon=":material/fact_check:"):
            st.markdown("Monthly spend in the Ads Manager exports against the BPP-FB line of the Ad Spend Report 2026 (same ex-VAT basis; Apr 2026 uses the ex-VAT amount from Campaign Spend Monitoring, because the report's April figure includes VAT). Months that differ probably have an incomplete export tab.")
            st.dataframe(CHK.assign(month=[mlabel(m) for m in CHK.index]).set_index("month").style.format("₱{:,.2f}"), width="stretch")
            if len(bad):
                st.caption("Differences: " + ", ".join(f"{mlabel(m)} {peso(v)}" for m, v in bad["difference"].items()))

# ===== Content =====
with tabs[2]:
    st.title("What People Saw and Engaged With")
    st.markdown(f"Facebook page posts and TikTok videos published in {RANGE}.")
    tp = D.top_posts(POSTS, M0, M1, 10)
    bt = D.by_post_type(POSTS, M0, M1)
    if len(tp):
        best = bt["er"].idxmax() if len(bt) and bt["er"].notna().any() else None
        if best is not None:
            top_reach = bt["reach_per_post"].idxmax()
            second = (f"**{best}** had both the highest engagement rate ({pct(bt.loc[best, 'er'], 2)}) and the highest reach per post ({num(bt['reach_per_post'].max())})." if best == top_reach
                      else f"**{best}** had the highest engagement rate ({pct(bt.loc[best, 'er'], 2)}) and **{top_reach}** the highest reach per post ({num(bt['reach_per_post'].max())}).")
            st.markdown(f"The top post by reach was a **{tp.iloc[0]['type'].lower().rstrip('s')}** with {num(tp.iloc[0]['reach'])} reach. {second}")
    st.subheader("Top Facebook Posts")
    st.caption("By reach")
    if len(tp):
        pdf = pd.DataFrame({"Post": tp["title"].map(lambda t: " ".join(str(t).split())[:90]), "Type": tp["type"], "Date": tp["published"].dt.strftime("%d %b"),
                            "Views": tp["views"], "Reach": tp["reach"], "Engagements": tp["engagements"], "Engagement rate": tp["er"], "Link": tp["permalink"].replace("", None)})
        st.dataframe(pdf, hide_index=True, width="stretch", column_config={
            "Post": st.column_config.TextColumn(width="large"), "Type": st.column_config.TextColumn(width="small"), "Date": st.column_config.TextColumn(width="small"),
            "Views": st.column_config.NumberColumn(format="localized"),
            "Reach": st.column_config.ProgressColumn(format="localized", min_value=0, max_value=float(max(tp["reach"].max(), 1))),
            "Engagements": st.column_config.NumberColumn(format="localized"),
            "Engagement rate": st.column_config.NumberColumn(format="percent"),
            "Link": st.column_config.LinkColumn(display_text="Open")})
    else:
        st.info("No Facebook posts in this range.")
    l, r = st.columns([1.1, 1], gap="large")
    with l:
        st.subheader("By Post Type")
        st.dataframe(pd.DataFrame({"Type": bt.index, "Posts": bt["posts"].values, "Reach per post": bt["reach_per_post"].round(0).values, "Views": bt["views"].values,
                                   "Engagement rate": bt["er"].values}), hide_index=True, width="stretch", column_config={
            "Reach per post": st.column_config.NumberColumn(format="localized"), "Views": st.column_config.NumberColumn(format="localized"),
            "Engagement rate": st.column_config.NumberColumn(format="percent")})
    with r:
        om = D.organic_monthly(POSTS)
        om = om[om.index < BUILT_MONTH] if M1 < BUILT_MONTH else om
        om = om[om.index <= M1].tail(12)
        trend("Facebook engagement rate by month", [m.to_timestamp() for m in om.index], om["er"], [False] * len(om), lambda v: pct(v, 1), "%{y:.1%}", ".0%", key="ct1")
    st.subheader("Top TikTok Videos")
    st.caption("By views")
    tv = D.top_tiktok(TT, M0, M1, 8)
    if len(tv):
        tdf = pd.DataFrame({"Video": tv["title"].map(lambda t: " ".join(str(t).split())[:80]), "Date": tv["posted"].dt.strftime("%d %b"), "Views": tv["views"],
                            "Likes": tv["likes"], "Shares": tv["shares"], "Engagement per view": tv["eng_per_view"], "Link": tv["link"].replace("", None)})
        st.dataframe(tdf, hide_index=True, width="stretch", column_config={
            "Video": st.column_config.TextColumn(width="large"), "Date": st.column_config.TextColumn(width="small"),
            "Views": st.column_config.ProgressColumn(format="localized", min_value=0, max_value=float(max(tv["views"].max(), 1))),
            "Likes": st.column_config.NumberColumn(format="localized"), "Shares": st.column_config.NumberColumn(format="localized"),
            "Engagement per view": st.column_config.NumberColumn(format="percent"), "Link": st.column_config.LinkColumn(display_text="Open")})
    else:
        st.info("No TikTok videos in this range.")

# ===== Channel Diagnostics =====
with tabs[3]:
    # ----- periods: two equal periods, own selector, default 6 months starting Oct 2025 (same idea as the first tab)
    _lm = [m for m in MONTHS if m <= LAST]
    st.title("Channel Diagnostics")
    cs1, cs2, cs3 = st.columns([1, 1, 2], vertical_alignment="bottom")
    CN = cs1.selectbox("Months per period", [3, 4, 6], index=2, key="ch_n", help="The first period is followed straight away by a second period of the same length.")
    _starts = [m for i, m in enumerate(_lm) if i + 2 * CN <= len(_lm)]
    if st.session_state.get("ch_start") not in _starts:
        st.session_state["ch_start"] = pd.Period("2025-10", "M") if pd.Period("2025-10", "M") in _starts else _starts[0]
    CA0 = cs2.selectbox("First period starts", _starts, key="ch_start", format_func=mlabel)
    CA1, CB0, CB1 = CA0 + (CN - 1), CA0 + CN, CA0 + (2 * CN - 1)
    C_A, C_B = f"First {CN} Months", f"Next {CN} Months"
    C_ARNG, C_BRNG = f"{mlabel(CA0)} to {mlabel(CA1)}", f"{mlabel(CB0)} to {mlabel(CB1)}"
    cs3.caption("This view has its own period selector. The sidebar months drive the Overview, Awareness Trend and Content tabs.")

    def status_of(chg, lower_is_better=True):
        """Efficiency status from the change in one metric vs the first period (the PediaWell thresholds, proposed and still to be calibrated)."""
        if chg is None or pd.isna(chg):
            return "n/a"
        c = -chg if lower_is_better else chg
        if c >= 0.05:
            return "Improved"
        if c > -0.05:
            return "Steady"
        if c > -0.15:
            return "Slightly weaker"
        return "Weaker"

    _status_bg = {"Improved": "#E3F1DF", "Steady": "#EEF1F5", "Slightly weaker": "#FFF3CD", "Weaker": "#FBE1E1", "Baseline": "#EEF1F5"}

    def show_table(rows):
        """Channel, period and status come first so the verdict is visible without scrolling; the wide 'What changed' text goes last."""
        short_names = {"Impressions": "Impr.", "Cost per 1,000 reached": "Cost/1K reach", "Frequency": "Freq.", "Cost per engagement": "Cost/eng.", "Posts / videos": "Posts",
                       "Engagement rate (÷ reach)": "Eng. rate", "Engagement per view": "Eng./view", "Reach or views per post": "Per post", "Share of spend": "% of spend"}
        df = pd.DataFrame(rows).rename(columns=short_names)
        first = df.columns[0]
        df = df[[first, "Period", "Status"] + [c for c in df.columns if c not in (first, "Period", "Status", "What changed")] + ["What changed"]]
        sty = df.style.map(lambda v: f"background-color: {_status_bg.get(v, 'transparent')}; font-weight: 600", subset=["Status"])
        cfg = {c: st.column_config.TextColumn(width=int(min(max(len(c), df[c].astype(str).str.len().max()) * 7.4 + 26, 150))) for c in df.columns}
        cfg["What changed"] = st.column_config.TextColumn(width=330)
        cfg[first] = st.column_config.TextColumn(width=int(min(max(len(first), df[first].astype(str).str.len().max()) * 7.4 + 26, 220)))
        cfg["Period"] = st.column_config.TextColumn(width=170)
        st.dataframe(sty, hide_index=True, width="stretch", column_config=cfg)

    def chg_text(name, chg):
        return f"{name} {pct(chg, 1, True)} vs {C_A.lower()}" if chg is not None else ""

    ua, ub = D.unit_costs(ADS, CA0, CA1), D.unit_costs(ADS, CB0, CB1)
    cpm_chg = change(ub["cpm"], ua["cpm"])
    oa_c, ob_c = D.organic(POSTS, CA0, CA1), D.organic(POSTS, CB0, CB1)
    st.markdown(f"Comparing {C_ARNG} with {C_BRNG}: Facebook ads cost per 1,000 impressions went from **{peso(ua['cpm'], 2)}** to **{peso(ub['cpm'], 2)}** ({pct(cpm_chg, 1, True)}) "
                f"and cost per engagement from **{peso(ua['cpe'], 3)}** to **{peso(ub['cpe'], 3)}**; the Facebook page's engagement rate went from **{pct(oa_c['er'], 2)}** to **{pct(ob_c['er'], 2)}**. "
                "Status compares each channel in the second period with the first, using proposed thresholds that are still to be calibrated with the client.")

    # ---- paid channels
    st.subheader("Paid Channels")

    def fb_row(u, label_period, status, what):
        return {"Channel": "Facebook ads", "Period": label_period, "Status": status, "Spend": peso(u["spend"]), "Impressions": num(u["impressions"]), "CPM": peso(u["cpm"], 2),
                "Reach": num(u["reach"]), "Cost per 1,000 reached": peso(u["cpr1000"], 2), "Frequency": f"{u['frequency']:.2f}", "CTR": pct(u["ctr"], 2) if u["clicks_ok"] else "n/a",
                "CPC": peso(u["cpc"], 2) if u["clicks_ok"] else "n/a", "Cost per engagement": peso(u["cpe"], 3), "What changed": what}

    def tt_ad_row(spend, label_period, what):
        return {"Channel": "TikTok ads", "Period": label_period, "Status": "n/a", "Spend": peso(spend) if not pd.isna(spend) else "n/a", "Impressions": "n/a", "CPM": "n/a", "Reach": "n/a",
                "Cost per 1,000 reached": "n/a", "Frequency": "n/a", "CTR": "n/a", "CPC": "n/a", "Cost per engagement": "n/a", "What changed": what}

    tts_a, tts_b = D.tiktok_ad_spend(S["ref_tt"], CA0, CA1), D.tiktok_ad_spend(S["ref_tt"], CB0, CB1)
    paid_rows = [fb_row(ua, C_ARNG, "Baseline", ""), fb_row(ub, C_BRNG, status_of(cpm_chg, True), chg_text("Cost per mille", cpm_chg)),
                 tt_ad_row(tts_a, C_ARNG, ""),
                 tt_ad_row(tts_b, C_BRNG, (chg_text("Spend", change(tts_b, tts_a)) + ". " if not (pd.isna(tts_a) or pd.isna(tts_b)) else "") + "Spend only: no TikTok ad performance data yet")]
    show_table(paid_rows)
    st.caption("Impr. = impressions. CPM = cost per 1,000 impressions. Cost/1K reach = cost per 1,000 reached. Freq. = impressions / reach. CTR = clicks / impressions. CPC = cost per click. Cost/eng. = cost per engagement. "
               "Facebook figures are from Ads Manager (ex-VAT); reach adds up campaign reach, so it overstates unique reach. CTR and cost per click use all clicks and exist from Mar 2026 onward, so they show n/a for a period that starts earlier. "
               "TikTok spend (ex-VAT) is from the BPP Campaign Spend Monitoring sheet for 2026, the SSOT's TikTok tabs for Aug to Oct 2025 and the Ad Spend Report 2025 for Nov and Dec 2025. It is shown only when every month of the period has a figure; impressions and clicks for TikTok ads are not in the data yet.")

    # ---- page posts and videos (Facebook page posts include boosted posts, so they are not organic-only)
    st.subheader("Page Posts and Videos")
    _tt_all = set(TT["month"].unique())
    cov = lambda m0, n_: [m for m in (m0 + i for i in range(n_)) if m in _tt_all]
    full_a, full_b = len(cov(CA0, CN)) == CN, len(cov(CB0, CN)) == CN
    ta_c, tb_c = D.tiktok(TT, CA0, CA1), D.tiktok(TT, CB0, CB1)
    er_chg = change(ob_c["er"], oa_c["er"])
    tt_chg = change(tb_c["eng_per_view"], ta_c["eng_per_view"]) if (full_a and full_b) else None

    def fbp_row(o, label_period, status, what):
        return {"Channel": "Facebook page (posts)", "Period": label_period, "Status": status, "Posts / videos": num(o["posts"]), "Views": num(o["views"]), "Reach": num(o["reach"]),
                "Engagements": num(o["engagements"]), "Engagement rate (÷ reach)": pct(o["er"], 2), "Engagement per view": "n/a", "Reach or views per post": num(o["reach_per_post"]) + " reach", "What changed": what}

    def tkv_row(t, label_period, covered, full, status, what):
        have = len(covered) > 0
        return {"Channel": "TikTok (videos)" if full or not have else "TikTok (videos, partial)", "Period": label_period, "Status": status, "Posts / videos": num(t["videos"]) if have else "n/a",
                "Views": num(t["views"]) if have else "n/a", "Reach": "n/a", "Engagements": num(t["engagements"]) if have else "n/a", "Engagement rate (÷ reach)": "n/a",
                "Engagement per view": pct(t["eng_per_view"], 1) if have else "n/a", "Reach or views per post": (num(t["views_per_video"]) + " views") if have else "n/a", "What changed": what}

    org_rows = [fbp_row(oa_c, C_ARNG, "Baseline", ""), fbp_row(ob_c, C_BRNG, status_of(er_chg, False), chg_text("Engagement rate", er_chg)),
                tkv_row(ta_c, C_ARNG, cov(CA0, CN), full_a, "Baseline" if full_a else "n/a", ""),
                tkv_row(tb_c, C_BRNG, cov(CB0, CN), full_b, status_of(tt_chg, False), chg_text("Engagement per view", tt_chg) if tt_chg is not None else "Not compared: TikTok video data does not cover every month of both periods")]
    show_table(org_rows)
    st.caption("Eng. rate = engagements / reach (Facebook). Eng./view = engagements / views (TikTok, which has no reach in the data). Per post = reach per post (Facebook) or views per video (TikTok). "
               "Facebook page posts include boosted posts: from Mar 2026 the exports show most of their views come from boosting, so these are not organic-only figures. Numbers are lifetime figures of the posts published in the period. Status uses the change in engagement rate (Facebook) or engagement per view (TikTok); higher is better.")
    if INTERNAL and not (full_a and full_b):
        _gap_c = [m for m in (CA0 + i for i in range(2 * CN)) if m not in _tt_all]
        st.caption("Internal: the SSOT has no TikTok videos for " + ", ".join(mlabel(m) for m in _gap_c) + ".")

    # ---- Facebook ads by campaign type
    st.subheader("Facebook Ads by Campaign Type")
    oca, ocb = D.unit_costs_by_objective(ADS, CA0, CA1), D.unit_costs_by_objective(ADS, CB0, CB1)
    _names = {"reach": "Reach campaigns", "boosting": "Boosting (engagement, views)", "pagelikes": "Page-like campaigns", "other": "Other"}

    def type_row(name, label_period, r, total_spend, status, what):
        return {"Campaign type": name, "Period": label_period, "Status": status, "Spend": peso(r["spend"]), "Share of spend": pct(r["spend"] / total_spend, 0) if total_spend else "n/a",
                "Impressions": num(r["impressions"]), "CPM": peso(r["cpm"], 2), "Reach": num(r["reach"]), "Cost per 1,000 reached": peso(r["cpr1000"], 2),
                "Cost per engagement": peso(r["cpe"], 3), "Frequency": f"{r['frequency']:.2f}", "What changed": what}

    type_rows = []
    for obj in [o for o in _names if (o in oca.index) or (o in ocb.index)]:
        ra = oca.loc[obj] if obj in oca.index else None
        rb = ocb.loc[obj] if obj in ocb.index else None
        small = any(r is not None and (ua["spend"] if r is ra else ub["spend"]) and r["spend"] / (ua["spend"] if r is ra else ub["spend"]) < 0.02 for r in (ra, rb))
        chg_o = change(rb["cpm"], ra["cpm"]) if (ra is not None and rb is not None and not small) else None
        if ra is not None:
            type_rows.append(type_row(_names[obj], C_ARNG, ra, ua["spend"], "Baseline", ""))
        if rb is not None:
            what = chg_text("Cost per mille", chg_o) if chg_o is not None else ("Too little spend to judge" if small else ("No spend in the first period" if ra is None else ""))
            type_rows.append(type_row(_names[obj], C_BRNG, rb, ub["spend"], status_of(chg_o, True), what))
    if type_rows:
        _tot_a = {"spend": ua["spend"], "impressions": ua["impressions"], "cpm": ua["cpm"], "reach": ua["reach"], "cpr1000": ua["cpr1000"], "cpe": ua["cpe"], "frequency": ua["frequency"]}
        _tot_b = {"spend": ub["spend"], "impressions": ub["impressions"], "cpm": ub["cpm"], "reach": ub["reach"], "cpr1000": ub["cpr1000"], "cpe": ub["cpe"], "frequency": ub["frequency"]}
        type_rows.append(type_row("All Facebook ads", C_ARNG, _tot_a, ua["spend"], "Baseline", ""))
        type_rows.append(type_row("All Facebook ads", C_BRNG, _tot_b, ub["spend"], status_of(cpm_chg, True), chg_text("Cost per mille", cpm_chg)))
        show_table(type_rows)
    else:
        st.info("No Facebook ads in these periods.")
    st.caption("Reach, boosting (engagement and video views) and page-like campaigns have very different costs, so compare each type with itself. Status uses the change in cost per mille from the first period to the second; lower is better. "
               "Improved is 5% lower or better, Steady is within 5%, Slightly weaker is up to 15% higher, Weaker is beyond that. A type with under 2% of the spend gets no status. These are proposed thresholds, to be calibrated with the client.")

st.html(f'<div style="height:8px;background:{RED};margin-top:2rem"></div>')
