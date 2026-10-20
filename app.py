"""BPP Brand Awareness Review (Streamlit prototype), editorial layout.

The page opens with the finding as a sentence, then the figures, then the evidence. Colours are the Project Swarm deck palette (navy, title blue,
yellow, red on white); fonts, colours and metric sizes live in .streamlit/config.toml. The only custom HTML is the caution stripe.
KPI definitions follow the Marketing 3.0 KPI deck (Paid awareness module): reach, frequency, cost per 1,000 reached, video view-through,
engagement rate = engagements / reach. Awareness is reported as delivery and cost: reach measures exposure, not recall.

Run:  cd bpp_dashboard && ../.venv/bin/streamlit run app.py     (reads Supabase via .streamlit/secrets.toml, or the local snapshot data/bpp_snapshot.json)
"""
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data as D

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


def metric(label, value, chg, higher_better=True, series=None, help=None):
    """Native st.metric. Change vs the prior period; green or red by whether the move is good, grey when it is flat (under 2%)."""
    if chg is None:
        delta, colour = None, "off"
    else:
        delta = f"{chg:+.1%}"
        colour = "off" if abs(chg) < 0.02 else ("normal" if higher_better else "inverse")
    if higher_better is None:   # a change that is neither good nor bad (spend)
        colour = "off"
    kw = {"chart_data": [float(v) for v in series if not pd.isna(v)], "chart_type": "area"} if series is not None and len(series) > 1 else {}
    st.metric(label, value, delta=delta, delta_color=colour, delta_description=f"vs {VS}" if chg is not None else None, help=help, **kw)


def stripe():
    """The one custom element: caution tape. BPP is Budol-Proof Pinoy, an awareness page about not getting scammed."""
    st.html(f'<div style="height:8px;background:repeating-linear-gradient(-45deg,{YELLOW} 0 14px,{NAVY} 14px 28px)"></div>')


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
    st.subheader("Reporting months")
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

tabs = st.tabs(["Overview", "Awareness trend", "Content"])

# ===== Overview =====
with tabs[0]:
    reach_now = cur["reach"] if cur["months"] == 1 else cur["reach_avg"]
    if pd.isna(reach_now) or pd.isna(cur["cpr"]):
        st.title(f"Brand awareness, {RANGE}")
    else:
        lead = f"Paid reach hit {short(reach_now)} in {RANGE}" if cur["months"] == 1 else f"Paid reach averaged {short(reach_now)} a month, {RANGE}"
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

    st.subheader("Paid awareness on Facebook")
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
        st.subheader("Facebook page")
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

    camps = D.campaigns(ADS, M0, M1)
    camps = camps[(camps["reach"] > 0) & (camps["objective"] == "reach")]   # cost per 1,000 reached only compares reach campaigns
    st.subheader("What to look at next")
    if len(camps) >= 2:
        lo, hi = camps.loc[camps["cpr"].idxmin()], camps.loc[camps["cpr"].idxmax()]
        st.markdown(f"Among reach campaigns, **{lo['name'][:60]}** was cheapest at {peso(lo['cpr'], 2)} per 1,000 reached and **{hi['name'][:60]}** the costliest at {peso(hi['cpr'], 2)}. "
                    "Agree target audiences per platform so reach can be reported as a share of audience and judged against a target.")
    else:
        st.markdown("Agree target audiences per platform so reach can be reported as a share of audience and judged against a target.")
    st.caption("Written by the dashboard from the numbers above. Reach measures exposure, not recall.")

# ===== Awareness trend =====
with tabs[1]:
    st.title("How awareness moved, month by month")
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

    st.subheader("Paid campaigns", anchor=False)
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
            st.markdown("Monthly spend in the Ads Manager exports against the BPP-FB line of the Ad Spend Report 2026 (same ex-VAT basis). Months that differ probably have an incomplete export tab.")
            st.dataframe(CHK.assign(month=[mlabel(m) for m in CHK.index]).set_index("month").style.format("₱{:,.2f}"), width="stretch")
            if len(bad):
                st.caption("Differences: " + ", ".join(f"{mlabel(m)} {peso(v)}" for m, v in bad["difference"].items()))

# ===== Content =====
with tabs[2]:
    st.title("What people saw and engaged with")
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
    st.subheader("Top Facebook posts")
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
        st.subheader("By post type")
        st.dataframe(pd.DataFrame({"Type": bt.index, "Posts": bt["posts"].values, "Reach per post": bt["reach_per_post"].round(0).values, "Views": bt["views"].values,
                                   "Engagement rate": bt["er"].values}), hide_index=True, width="stretch", column_config={
            "Reach per post": st.column_config.NumberColumn(format="localized"), "Views": st.column_config.NumberColumn(format="localized"),
            "Engagement rate": st.column_config.NumberColumn(format="percent")})
    with r:
        om = D.organic_monthly(POSTS)
        om = om[om.index < BUILT_MONTH] if M1 < BUILT_MONTH else om
        om = om[om.index <= M1].tail(12)
        trend("Facebook engagement rate by month", [m.to_timestamp() for m in om.index], om["er"], [False] * len(om), lambda v: pct(v, 1), "%{y:.1%}", ".0%", key="ct1")
    st.subheader("Top TikTok videos")
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

st.html(f'<div style="height:8px;background:{RED};margin-top:2rem"></div>')
