"""BPP Brand Awareness Review (Streamlit prototype).

Design and KPI definitions follow the Marketing 3.0 KPI deck: dark Razza report style, the Paid awareness module (reach, frequency,
cost per 1,000 reached, video view-through), the Awareness Trend page, organic social (engagement rate = engagements / reach), and
key takeaway boxes. Awareness is reported as delivery and cost: reach measures exposure, not recall.

Run:  cd bpp_dashboard && ../.venv/bin/streamlit run app.py     (needs data/bpp_snapshot.json, git-ignored)
"""
import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data as D

st.set_page_config(page_title="BPP Brand Awareness Review", page_icon=":bar_chart:", layout="wide")

BG, CARD, LINE = "#1a2023", "#232a2f", "#323b41"
TEXT, MUTED = "#ffffff", "#a9b4bb"
GREEN, AMBER, RED, GREY = "#92d050", "#f6b73c", "#e0605e", "#8f9aa1"
BLUE, TEAL = "#3b82f6", "#1fa67a"

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'Lato', sans-serif; }}
.stApp {{ background: {BG}; color: {TEXT}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; max-width: 1240px; }}
section[data-testid="stSidebar"] {{ background: #151b1d; border-right: 1px solid {LINE}; }}
.eyebrow {{ color: {MUTED}; font-size: 15px; margin-bottom: 2px; }}
.h1 {{ font-weight: 900; font-size: 40px; line-height: 1.1; color: {GREEN}; margin: 0; }}
.h1 span {{ color: {TEXT}; }}
.sub {{ color: {MUTED}; font-size: 14px; margin: 6px 0 14px 0; }}
.pill {{ display:inline-block; background:#394147; color:#fff; font-weight:700; font-size:12px; letter-spacing:.4px; border-radius:999px; padding:9px 22px; text-transform:uppercase; }}
.cards {{ display:grid; gap:14px; margin: 6px 0 12px 0; }}
.c5 {{ grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }} .c4 {{ grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }}
.card {{ background:{CARD}; border-radius:12px; padding:16px 18px 14px 18px; border:1px solid {LINE}; }}
.card .lab {{ color:{MUTED}; font-size:14px; font-weight:700; display:flex; justify-content:space-between; align-items:center; }}
.card .val {{ font-size:34px; font-weight:900; margin:10px 0 12px 0; letter-spacing:-.5px; white-space:nowrap; }}
.card .ln1 {{ font-size:13px; font-weight:700; }} .card .ln2 {{ font-size:13px; color:{MUTED}; margin-top:2px; }}
.dot {{ width:14px; height:14px; border-radius:50%; display:inline-block; }}
.good {{ color:{GREEN}; }} .bad {{ color:{RED}; }} .neutral {{ color:{MUTED}; }}
.sec {{ color:{GREEN}; font-weight:900; font-size:13px; letter-spacing:.6px; text-transform:uppercase; margin:18px 0 0 0; }}
.sec small {{ color:{MUTED}; font-weight:400; text-transform:none; letter-spacing:0; font-size:13px; margin-left:8px; }}
.ctitle {{ font-weight:900; font-size:15px; margin:6px 0 2px 0; }}
.take {{ background:{CARD}; border:1.5px solid {GREEN}; border-radius:14px; padding:18px 20px; font-size:15px; line-height:1.5; }}
.take .k {{ color:{GREEN}; font-weight:900; font-size:12px; letter-spacing:.6px; text-transform:uppercase; margin-bottom:4px; }}
.take p {{ margin: 0 0 12px 0; }}
.legend {{ display:flex; gap:34px; color:{MUTED}; font-size:13px; margin:6px 0 4px 0; flex-wrap:wrap; }}
.legend .dot {{ width:12px; height:12px; margin-right:8px; vertical-align:-1px; }}
.note {{ color:{MUTED}; font-size:13px; line-height:1.5; margin:8px 0; }}
table.t {{ width:100%; border-collapse:collapse; font-size:14px; margin:8px 0; }}
table.t th {{ color:{GREEN}; text-align:left; font-weight:900; padding:10px 12px; border-bottom:1px solid {LINE}; background:#1f262a; }}
table.t td {{ padding:11px 12px; border-bottom:1px solid {LINE}; background:{CARD}; vertical-align:top; }}
table.t td.r, table.t th.r {{ text-align:right; }}
table.t td.b {{ font-weight:900; }}
table.t a {{ color:{MUTED}; text-decoration:none; }} table.t a:hover {{ color:{GREEN}; }}
div[data-testid="stTabs"] button[role="tab"] {{ font-weight:700; font-size:15px; }}
</style>
""",
    unsafe_allow_html=True,
)

if not D.snapshot_exists():
    st.error("data/bpp_snapshot.json is missing. This prototype reads a snapshot of the BPP Content SSOT that is not stored in the repository. See README.md.")
    st.stop()


@st.cache_data(show_spinner="Loading BPP data...")
def load():
    return D.load_snapshot()


S = load()
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


def mlabel(p):
    return p.strftime("%b %Y")


def change(c, p):
    return None if (c is None or p is None or pd.isna(c) or pd.isna(p) or p == 0) else c / p - 1


def tone(chg, higher_better=True, flat=0.02):
    if chg is None or pd.isna(chg) or abs(chg) < flat:
        return "neutral"
    return "good" if (chg > 0) == higher_better else "bad"


def card(label, value, ln1, chg, higher_better=True, vs=None):
    arrow = "No prior period to compare" if chg is None else f"{chg:+.1%} vs {vs}"
    return (f'<div class="card"><div class="lab"><span>{html.escape(label)}</span><span class="dot" style="background:{GREY}"></span></div>'
            f'<div class="val">{value}</div><div class="ln1 neutral">{html.escape(ln1)}</div>'
            f'<div class="ln2 {tone(chg, higher_better) if chg is not None else ""}">{arrow}</div></div>')


def cards(items, cols):
    st.markdown(f'<div class="cards c{cols}">' + "".join(items) + "</div>", unsafe_allow_html=True)


def sec(title, small=""):
    st.markdown(f'<div class="sec">{title}<small>{small}</small></div>', unsafe_allow_html=True)


def legend():
    st.markdown(
        f'<div class="legend"><span><span class="dot" style="background:{GREEN}"></span>On or above target</span>'
        f'<span><span class="dot" style="background:{AMBER}"></span>Within 10% of target</span>'
        f'<span><span class="dot" style="background:{RED}"></span>More than 10% off</span>'
        f'<span><span class="dot" style="background:{GREY}"></span>Pacing only or target pending</span></div>', unsafe_allow_html=True)


def header(eyebrow, green, white, sub=None):
    left, right = st.columns([4, 1.5])
    with left:
        st.markdown(f'<div class="eyebrow">{eyebrow}</div><div class="h1">{green} <span>{white}</span></div>', unsafe_allow_html=True)
        if sub:
            st.markdown(f'<div class="sub">{sub}</div>', unsafe_allow_html=True)
    with right:
        st.markdown(f'<div style="text-align:right;margin-top:26px"><span class="pill">Snapshot {S["built_at"]:%d %b %Y}</span></div>', unsafe_allow_html=True)


def ctitle(text):
    st.markdown(f'<div class="ctitle">{html.escape(text)}</div>', unsafe_allow_html=True)


def takeaway(blocks):
    st.markdown('<div class="take">' + "".join(f'<div class="k">{k}</div><p>{v}</p>' for k, v in blocks) + "</div>", unsafe_allow_html=True)


def table(headers, rows, aligns):
    th = "".join(f'<th class="{"r" if a == "r" else ""}">{html.escape(h)}</th>' for h, a in zip(headers, aligns))
    body = ""
    for row in rows:
        tds = ""
        for j, (cell, a) in enumerate(zip(row, aligns)):
            cls = " ".join(c for c in (("r" if a == "r" else ""), ("b" if j == 0 else "")) if c)
            tds += f'<td class="{cls}">{cell}</td>'
        body += f"<tr>{tds}</tr>"
    st.markdown(f'<table class="t"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>', unsafe_allow_html=True)


def style_fig(fig, height=300, legend_on=True, tickprefix="", ticksuffix="", tickformat=None):
    fig.update_layout(height=height, margin=dict(l=8, r=54, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#d7dde1", family="Lato, sans-serif", size=13), showlegend=legend_on,
                      legend=dict(orientation="h", y=-0.16, x=0.5, xanchor="center"), hoverlabel=dict(bgcolor=CARD, font_color=TEXT))
    fig.update_xaxes(showgrid=False, linecolor=LINE, tickfont=dict(color=MUTED), tickangle=0)
    fig.update_yaxes(gridcolor="#2c353a", zeroline=False, tickfont=dict(color=MUTED), tickprefix=tickprefix, ticksuffix=ticksuffix, tickformat=tickformat)
    return fig


def month_axis(fig):
    fig.update_xaxes(type="date", tickformat="%b %y", nticks=7)
    return fig


def show(fig, key):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)


# ---------- sidebar: month range ----------
def _presets():
    ytd0 = max(m for m in MONTHS if m.year == LAST.year and m.month == 1) if any(m.year == LAST.year and m.month == 1 for m in MONTHS) else MONTHS[0]
    return {"Last full month": (LAST, LAST), "Last 3 months": (LAST - 2, LAST), f"Year to date ({LAST.year})": (ytd0, LAST), "All data": (MONTHS[0], MONTHS[-1])}


def _on_preset():
    st.session_state["m0"], st.session_state["m1"] = _presets()[st.session_state["preset"]]


st.session_state.setdefault("m0", LAST)
st.session_state.setdefault("m1", LAST)
with st.sidebar:
    st.markdown("### Reporting months")
    st.selectbox("Quick range", list(_presets()), key="preset", on_change=_on_preset)
    st.selectbox("From month", MONTHS, key="m0", format_func=mlabel)
    st.selectbox("To month", MONTHS, key="m1", format_func=mlabel)
    st.caption(f"Source: BPP Content SSOT snapshot ({S['built_at']:%d %b %Y}). The Ads Manager exports are monthly, so this view works in whole months.")
    with st.expander("How the numbers are defined"):
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
if M1 >= BUILT_MONTH:
    st.warning(f"{mlabel(M1)} was still running when the snapshot was built ({S['built_at']:%d %b}): its numbers are partial.")

cur = D.paid(ADS, M0, M1)
pre = D.paid(ADS, P0, P1) if HAS_PRIOR else None
org, org_p = D.organic(POSTS, M0, M1), (D.organic(POSTS, P0, P1) if HAS_PRIOR else None)
tk, tk_p = D.tiktok(TT, M0, M1), (D.tiktok(TT, P0, P1) if HAS_PRIOR else None)
chg = lambda a, b, k: None if b is None else change(a[k], b[k])

tabs = st.tabs(["Page one", "Awareness trend", "Content"])

# ===== Page one: the deck's Modules page =====
with tabs[0]:
    header("BPP  |  Review", "Brand Awareness Review,", RANGE)
    sec("Paid awareness: Facebook", "Ads Manager, targets pending sign-off")
    cards([
        card("Ad spend (pacing)", peso(cur["spend"]), f"{cur['campaigns']} campaigns", chg(cur, pre, "spend"), False, VS),
        card("Reach (monthly avg)", num(cur["reach_avg"]), "Share of target audience: pending", chg(cur, pre, "reach_avg"), True, VS),
        card("Avg frequency", f"{cur['frequency']:.2f}" if not pd.isna(cur["frequency"]) else "n/a", "Monthly; alert above 3 is weekly", chg(cur, pre, "frequency"), False, VS),
        card("Cost / 1,000 reached", peso(cur["cpr"], 2), "Target pending", chg(cur, pre, "cpr"), False, VS),
        card("Video view-through", pct(cur["thru_rate"], 1), "ThruPlays / impressions", chg(cur, pre, "thru_rate"), True, VS),
    ], 5)
    sec("Organic social: Facebook page", "posts published in the range")
    cards([
        card("Posts published", num(org["posts"]), "Facebook page", chg(org, org_p, "posts"), True, VS),
        card("Avg reach per post", num(org["reach_per_post"]), "Lifetime reach of each post", chg(org, org_p, "reach_per_post"), True, VS),
        card("Engagement rate", pct(org["er"], 2), "Engagements / reach", chg(org, org_p, "er"), True, VS),
        card("Post views", num(org["views"]), "Facebook post views", chg(org, org_p, "views"), True, VS),
    ], 4)
    sec("TikTok", "videos posted in the range")
    cards([
        card("Videos posted", num(tk["videos"]), "TikTok", chg(tk, tk_p, "videos"), True, VS),
        card("Video views", num(tk["views"]), f"{num(tk['views_per_video'])} per video", chg(tk, tk_p, "views"), True, VS),
        card("Engagements", num(tk["engagements"]), "Likes, comments, shares", chg(tk, tk_p, "engagements"), True, VS),
        card("Engagement per view", pct(tk["eng_per_view"], 1), "No reach for TikTok in the SSOT", chg(tk, tk_p, "eng_per_view"), True, VS),
    ], 4)
    legend()
    st.markdown(
        f'<div class="note">Reach is the sum of campaign reach in the Ads Manager exports, and campaigns overlap, so unique reach is lower. It is not added across platforms: TikTok is shown by views. '
        f'The deck reports weekly reach as a share of a target audience; the SSOT has monthly exports and no target audience yet, so that card is pending. '
        f'Reach measures exposure, not recall.</div>', unsafe_allow_html=True)

    # key takeaway (rule-based)
    parts = []
    if pre is not None and not pd.isna(cur["reach_avg"]) and chg(cur, pre, "reach_avg") is not None and chg(cur, pre, "cpr") is not None:
        rc, cc = chg(cur, pre, "reach_avg"), chg(cur, pre, "cpr")
        parts.append(f"Paid reach averaged <b>{num(cur['reach_avg'])}</b> a month, {'up' if rc >= 0 else 'down'} {abs(rc):.1%} vs {VS}, at <b>{peso(cur['cpr'], 2)}</b> per 1,000 reached "
                     f"({'up' if cc >= 0 else 'down'} {abs(cc):.1%}) with an average frequency of {cur['frequency']:.2f}.")
    else:
        parts.append(f"Paid reach averaged <b>{num(cur['reach_avg'])}</b> a month at <b>{peso(cur['cpr'], 2)}</b> per 1,000 reached, frequency {cur['frequency']:.2f}.")
    if org["posts"]:
        parts.append(f"Facebook posts reached {num(org['reach_per_post'])} people on average with a {pct(org['er'], 2)} engagement rate. TikTok videos got {num(tk['views'])} views.")
    camps = D.campaigns(ADS, M0, M1)
    camps = camps[(camps["reach"] > 0) & (camps["objective"] == "reach")]   # cost per 1,000 reached only compares reach campaigns
    if len(camps) >= 2:
        lo, hi = camps.loc[camps["cpr"].idxmin()], camps.loc[camps["cpr"].idxmax()]
        focus = (f"Among reach campaigns, cheapest: <b>{html.escape(lo['name'][:60])}</b> at {peso(lo['cpr'], 2)} per 1,000 reached. Costliest: <b>{html.escape(hi['name'][:60])}</b> at {peso(hi['cpr'], 2)}. "
                 f"Agree target audiences per platform so reach can be reported as a share of audience and statuses can be judged.")
    else:
        focus = "Agree target audiences per platform so reach can be reported as a share of audience and statuses can be judged."
    takeaway([("Key takeaway", " ".join(parts)), ("Suggested focus (auto-generated)", focus)])

# ===== Awareness trend: the deck's Awareness Trend page, monthly =====
with tabs[1]:
    header("BPP  |  Monthly", "Awareness", "Trend", f"Paid awareness on Facebook, by month, up to {mlabel(M1)}. Weekly reach and target audiences are not in the SSOT yet, so months are shown.")
    pm = D.paid_monthly(ADS)
    pm = pm[(pm.index <= M1)].tail(12)
    pm = pm[pm.index < BUILT_MONTH] if M1 < BUILT_MONTH else pm
    xl = [mlabel(m) for m in pm.index]
    xs = [m.to_timestamp() for m in pm.index]
    CHK = D.spend_check(ADS, S["ref"])
    GAPS = set(CHK[CHK["difference"] < -1].index)   # months whose Ads Manager export has less spend than the Ad Spend Report: probably incomplete
    mk = dict(size=9, color=[AMBER if m in GAPS else BLUE for m in pm.index], line=dict(width=0))
    mk2 = dict(size=9, color=[AMBER if m in GAPS else TEAL for m in pm.index], line=dict(width=0))
    a, b = st.columns(2)
    with a:
        ctitle("Monthly reach, sum of campaign reach")
        fig = go.Figure(go.Scatter(x=xs, y=pm["reach"], mode="lines+markers", line=dict(color=BLUE, width=3), marker=mk, name="Reach"))
        show(month_axis(style_fig(fig, 300, legend_on=False, tickformat=",.0f")), "tr1")
    with b:
        ctitle("Average frequency by month (impressions / reach)")
        fig = go.Figure(go.Scatter(x=xs, y=pm["frequency"], mode="lines+markers+text", text=[f"{v:.2f}" for v in pm["frequency"]], textposition="top center",
                                   textfont=dict(color=BLUE, size=11), line=dict(color=BLUE, width=3), marker=mk, name="Frequency"))
        fig.update_yaxes(rangemode="tozero")
        show(month_axis(style_fig(fig, 300, legend_on=False, tickformat=".1f")), "tr2")
    c, d = st.columns(2)
    with c:
        ctitle("Cost per 1,000 reached (₱)")
        fig = go.Figure(go.Scatter(x=xs, y=pm["cpr"], mode="lines+markers+text", text=[f"₱{v:,.1f}" for v in pm["cpr"]], textposition="top center",
                                   textfont=dict(color=TEAL, size=11), line=dict(color=TEAL, width=3), marker=mk2, name="Cost per 1,000 reached"))
        show(month_axis(style_fig(fig, 300, legend_on=False, tickprefix="₱", tickformat=",.0f")), "tr3")
    with d:
        ctitle("Video view-through (ThruPlays / impressions)")
        fig = go.Figure(go.Scatter(x=xs, y=pm["thru_rate"], mode="lines+markers", line=dict(color=TEAL, width=3), marker=mk2, name="View-through"))
        show(month_axis(style_fig(fig, 300, legend_on=False, tickformat=".0%")), "tr4")
    st.markdown('<div class="note">Reach is the sum of campaign reach per month, so it overstates unique reach. Frequency here is monthly; the deck\'s alert level of 3 applies to weekly frequency. '
                'Months before January 2026 use the 2025 exports. Amber markers are months whose Ads Manager export has less spend than the Ad Spend Report, so the export is probably incomplete (see the data check below). Cost per 1,000 reached suits reach campaigns; engagement boosts optimise for engagement, not reach.</div>', unsafe_allow_html=True)
    if len(pm) >= 2:
        last, prev = pm.iloc[-1], pm.iloc[-2]
        takeaway([("Key takeaway", f"In {xl[-1]}, reach was {num(last['reach'])} ({pct(change(last['reach'], prev['reach']), 1, True)} vs {xl[-2]}), cost per 1,000 reached {peso(last['cpr'], 2)} "
                                    f"({pct(change(last['cpr'], prev['cpr']), 1, True)}) and frequency {last['frequency']:.2f}.")])
    sec("Paid campaigns", f"{RANGE}, largest spend first")
    camp = D.campaigns(ADS, M0, M1).head(10)
    rows = [[html.escape(r["name"][:78]), r["objective"], peso(r["spend"], 2), num(r["reach"]), f"{r['frequency']:.2f}" if not pd.isna(r["frequency"]) else "n/a",
             peso(r["cpr"], 2), pct(r["thru_rate"], 1)] for _, r in camp.iterrows()]
    table(["Campaign", "Type", "Spend", "Reach", "Freq.", "Cost / 1,000", "View-through"], rows, ["l", "l", "r", "r", "r", "r", "r"])
    chk = CHK
    bad = chk[chk["difference"].abs() > 1]
    with st.expander("Data check: Ads Manager spend vs Ad Spend Report"):
        st.markdown("Monthly spend in the Ads Manager exports against the BPP-FB line of the Ad Spend Report 2026 (same ex-VAT basis). Months that differ probably have an incomplete export tab.")
        st.dataframe(chk.assign(month=[mlabel(m) for m in chk.index]).set_index("month").style.format("₱{:,.2f}"), use_container_width=True)
        if len(bad):
            st.caption("Differences: " + ", ".join(f"{mlabel(m)} {peso(v)}" for m, v in bad["difference"].items()))

# ===== Content =====
with tabs[2]:
    header("BPP  |  Monthly", "Content", "Performance", f"What builds awareness: Facebook page posts and TikTok videos published in {RANGE}.")
    tp = D.top_posts(POSTS, M0, M1, 10)
    sec("Top Facebook posts", "by reach")
    rows = []
    for _, r in tp.iterrows():
        title = html.escape(" ".join(str(r["title"]).split())[:90])
        link = f'<a href="{html.escape(r["permalink"])}" target="_blank">{title}</a>' if r["permalink"] else title
        rows.append([link, html.escape(r["type"]), f"{r['published']:%d %b}", num(r["views"]), num(r["reach"]), num(r["engagements"]), pct(r["er"], 1)])
    if rows:
        table(["Post", "Type", "Date", "Views", "Reach", "Engagements", "Eng. rate"], rows, ["l", "l", "l", "r", "r", "r", "r"])
    else:
        st.info("No Facebook posts in this range.")
    l, r = st.columns([1.1, 1])
    with l:
        sec("By post type")
        bt = D.by_post_type(POSTS, M0, M1)
        table(["Type", "Posts", "Reach / post", "Views", "Eng. rate"], [[html.escape(i), num(x["posts"]), num(x["reach_per_post"]), num(x["views"]), pct(x["er"], 2)] for i, x in bt.iterrows()],
              ["l", "r", "r", "r", "r"])
    with r:
        ctitle("Facebook engagement rate by month (engagements / reach)")
        om = D.organic_monthly(POSTS)
        om = om[om.index < BUILT_MONTH] if M1 < BUILT_MONTH else om
        om = om[om.index <= M1].tail(12)
        fig = go.Figure(go.Bar(x=[m.to_timestamp() for m in om.index], y=om["er"], marker_color=BLUE, text=[f"{v:.1%}" for v in om["er"]], textposition="outside", textfont=dict(color="#d7dde1")))
        fig.update_layout(bargap=0.4)
        show(month_axis(style_fig(fig, 280, legend_on=False, tickformat=".0%")), "ct1")
    sec("Top TikTok videos", "by views")
    tv = D.top_tiktok(TT, M0, M1, 8)
    rows = []
    for _, x in tv.iterrows():
        title = html.escape(" ".join(str(x["title"]).split())[:80])
        rows.append([f'<a href="{html.escape(x["link"])}" target="_blank">{title}</a>' if x["link"] else title, f"{x['posted']:%d %b}", num(x["views"]), num(x["likes"]), num(x["shares"]), pct(x["eng_per_view"], 1)])
    if rows:
        table(["Video", "Date", "Views", "Likes", "Shares", "Eng. / view"], rows, ["l", "l", "r", "r", "r", "r"])
    else:
        st.info("No TikTok videos in this range.")
    best = bt["er"].idxmax() if len(bt) and bt["er"].notna().any() else None
    if best is not None and len(tp):
        takeaway([("Key takeaway", f"The top post by reach was a {html.escape(tp.iloc[0]['type'].lower())} with {num(tp.iloc[0]['reach'])} reach. <b>{html.escape(best)}</b> had the highest engagement rate ({pct(bt.loc[best, 'er'], 2)}) "
                                    f"and <b>{html.escape(bt['reach_per_post'].idxmax())}</b> the highest reach per post ({num(bt['reach_per_post'].max())}).")])
