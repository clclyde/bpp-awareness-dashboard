"""BPP (Budol-Proof Pinoy) brand awareness review deck, built from the same data layer as the Streamlit dashboard (data.py).

Output: a .pptx (native, editable charts and tables) in the Project Swarm look: white, navy block, yellow title word, red bar, Montserrat.
It opens in PowerPoint and Google Slides (import the file; Montserrat is a Google font, install it for PowerPoint).

Run (from this folder):
  python report_deck.py --month 2026-09               # data/bpp_snapshot.json (local, git-ignored)
  python report_deck.py --month 2026-09 --live        # read Supabase with .streamlit/secrets.toml or PULSE_DB_* variables
  python report_deck.py --month 2026-09 --internal    # adds the team-only data check (yellow months, Ads Manager vs Ad Spend Report)
Without --month the last full month is used. Needs: pip install -r requirements-report.txt

The text is rule-based (no LLM). A person still checks the numbers against Meta and TikTok and writes the "why" and "what next"
(Media Planning Playbook 3.1, section 4.9): the closing slide leaves a box for the planner.
Awareness is reported as delivery and cost: reach measures exposure, not recall.
"""
import argparse
import os
import tomllib
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_MARKER_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

import data as D

HERE = Path(__file__).parent
# Project Swarm palette (read from the deck file)
NAVY, BLUE, YELLOW, RED = "073763", "0B3691", "F1C232", "D10000"
TEXT, MUTED, LINE, MIST, WHITE = "3F3F3F", "737373", "DCE3EA", "F3F6FA", "FFFFFF"
GOOD, BAD = "3D8B37", "D10000"
FONT = "Montserrat"
W, H = 13.333, 7.5


# ---------- formatting ----------
def peso(x, dec=0):
    return "n/a" if pd.isna(x) else f"{'-' if x < 0 else ''}₱{abs(x):,.{dec}f}"


def num(x):
    return "n/a" if pd.isna(x) else f"{x:,.0f}"


def pct(x, dec=1):
    return "n/a" if pd.isna(x) else f"{x:.{dec}%}"


def short(x):
    return "n/a" if pd.isna(x) else (f"{x / 1e6:.1f} million" if x >= 1e6 else f"{x:,.0f}")


def mlabel(p):
    return p.strftime("%b %Y")


def change(c, p):
    return None if (c is None or p is None or pd.isna(c) or pd.isna(p) or p == 0) else c / p - 1


def tone(chg, higher_better, flat=0.02):
    """Colour of a change: green good, red bad, grey when flat or when the direction has no good or bad (higher_better None)."""
    if chg is None or pd.isna(chg) or abs(chg) < flat or higher_better is None:
        return MUTED
    return GOOD if (chg > 0) == higher_better else BAD


def rgb(h):
    return RGBColor.from_string(h)


# ---------- data ----------
def load_conf():
    """The same settings as the dashboard: .streamlit/secrets.toml [supabase], else PULSE_DB_* variables, else None (snapshot)."""
    f = HERE / ".streamlit" / "secrets.toml"
    if f.exists():
        conf = tomllib.loads(f.read_text()).get("supabase")
        if conf:
            return dict(conf)
    if os.environ.get("PULSE_DB_HOST"):
        return {"host": os.environ["PULSE_DB_HOST"], "user": os.environ["PULSE_DB_USER"], "password": os.environ["PULSE_DB_PASSWORD"],
                "port": os.environ.get("PULSE_DB_PORT", "5432"), "dbname": os.environ.get("PULSE_DB_NAME", "postgres"), "sslmode": os.environ.get("PULSE_DB_SSLMODE", "require")}
    return None


def build_report(S: dict, month: str | None, internal: bool) -> dict:
    ads, posts, tt = S["ads"], S["posts"], S["tiktok"]
    last = D.last_full_month(ads, S["built_at"])
    m = pd.Period(month, "M") if month else last
    p = m - 1
    months = sorted(ads["month"].unique())
    if m not in months:
        raise SystemExit(f"No Ads Manager data for {m}. Months available: {months[0]} to {months[-1]}.")
    has_prior = p >= months[0]
    cur = D.paid(ads, m, m)
    pre = D.paid(ads, p, p) if has_prior else None
    org, org_p = D.organic(posts, m, m), (D.organic(posts, p, p) if has_prior else None)
    tk, tk_p = D.tiktok(tt, m, m), (D.tiktok(tt, p, p) if has_prior else None)
    pm = D.paid_monthly(ads)
    pm = pm[pm.index <= m].tail(12)
    chk = D.spend_check(ads, S["ref"])
    gaps = set(chk[chk["difference"] < -1].index)
    camps = D.campaigns(ads, m, m)
    reach_camps = camps[(camps["reach"] > 0) & (camps["objective"] == "reach")]   # cost per 1,000 reached only compares reach campaigns
    R = {"S": S, "m": m, "label": mlabel(m), "vs": mlabel(p), "has_prior": has_prior, "internal": internal, "cur": cur, "pre": pre, "org": org, "org_p": org_p, "tk": tk,
         "tk_p": tk_p, "pm": pm, "gaps": gaps, "chk": chk, "camps": camps.head(8), "tp": D.top_posts(posts, m, m, 5), "bt": D.by_post_type(posts, m, m),
         "tv": D.top_tiktok(tt, m, m, 5), "partial": m >= pd.Period(S["built_at"], "M")}
    chg = lambda a, b, k: None if b is None else change(a[k], b[k])
    R["chg"] = {k: chg(cur, pre, k) for k in ("spend", "reach", "reach_avg", "frequency", "cpr", "thru_rate")}
    R["chg_org"] = {k: chg(org, org_p, k) for k in ("posts", "reach_per_post", "er", "views")}
    R["chg_tk"] = {k: chg(tk, tk_p, k) for k in ("videos", "views", "engagements", "eng_per_view")}
    # rule-based text, the same wording as the dashboard
    R["headline"] = (f"Paid reach hit {short(cur['reach'])} in {R['label']}, at {peso(cur['cpr'], 2)} per 1,000 reached."
                     if not (pd.isna(cur["reach"]) or pd.isna(cur["cpr"])) else f"Brand awareness, {R['label']}")
    parts = []
    rc, cc = R["chg"]["reach"], R["chg"]["cpr"]
    if rc is not None and cc is not None:
        parts.append(f"That is {abs(rc):.1%} {'more' if rc >= 0 else 'less'} reach than {R['vs']}, at a cost per 1,000 {'up' if cc >= 0 else 'down'} {abs(cc):.1%}, "
                     f"with each person reached about {cur['frequency']:.1f} times on average.")
    if org["posts"]:
        parts.append(f"Facebook posts reached {num(org['reach_per_post'])} people each with a {pct(org['er'], 2)} engagement rate; TikTok videos drew {num(tk['views'])} views.")
    parts.append("Reach adds up campaign reach, so the number of different people is lower.")
    R["standfirst"] = " ".join(parts)
    ask = "Agree target audiences per platform so reach can be reported as a share of audience and judged against a target."
    if len(reach_camps) >= 2:
        lo, hi = reach_camps.loc[reach_camps["cpr"].idxmin()], reach_camps.loc[reach_camps["cpr"].idxmax()]
        R["focus"] = (f"Among reach campaigns, {lo['name'][:60]} was cheapest at {peso(lo['cpr'], 2)} per 1,000 reached and {hi['name'][:60]} the costliest at "
                      f"{peso(hi['cpr'], 2)}. {ask}")
    else:
        R["focus"] = ask
    return R


# ---------- deck ----------
class Deck:
    def __init__(self, R):
        self.R = R
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.n = 0

    # --- primitives ---
    def rect(self, s, x, y, w, h, fill, line=None, lw=1.0):
        b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        b.fill.solid(); b.fill.fore_color.rgb = rgb(fill)
        if line:
            b.line.color.rgb = rgb(line); b.line.width = Pt(lw)
        else:
            b.line.fill.background()
        b.shadow.inherit = False
        st = b._element.find(qn("p:style"))   # drop the theme style reference: it brings a drop shadow in some viewers
        if st is not None:
            b._element.remove(st)
        return b

    def text(self, s, text, x, y, w, h, size, bold=False, color=TEXT, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        p = tf.paragraphs[0]
        p.alignment = align
        self.run(p, text, size, bold, color)
        return tb

    @staticmethod
    def run(p, text, size, bold=False, color=TEXT):
        r = p.add_run()
        r.text = text
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, FONT
        r.font.color.rgb = rgb(color)
        return r

    def new(self):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self.n += 1
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = rgb(WHITE)
        return s

    def slide(self, lead, accent, sub=None):
        """Content slide: navy bar top-left, red bar bottom-right, title with the last words in yellow, footer."""
        s = self.new()
        self.rect(s, 0, 0, W * 0.38, 0.14, NAVY)
        self.rect(s, W * 0.5, H - 0.14, W * 0.5, 0.14, RED)
        tb = self.text(s, f"{lead} ", 0.6, 0.45, 12.1, 0.7, 28, color=NAVY)
        self.run(tb.text_frame.paragraphs[0], accent, 28, True, YELLOW)
        if sub:
            self.text(s, sub, 0.6, 1.17, 12.1, 0.3, 12, color=MUTED)
        R = self.R
        self.text(s, f"BPP · Brand awareness review · {R['label']} · Data as of {R['S']['built_at']:%d %b %Y}", 0.6, 6.88, 9.5, 0.25, 9, color=MUTED)
        self.text(s, str(self.n), 11.9, 6.88, 0.8, 0.25, 9, color=MUTED, align=PP_ALIGN.RIGHT)
        return s

    def note(self, s, text, y=6.4, h=0.4):
        self.text(s, text, 0.6, y, 12.1, h, 9.5, color=MUTED)

    def kpi(self, s, x, y, w, label, value, line, chg, higher_better, h=1.6):
        self.rect(s, x, y, w, h, MIST)
        self.rect(s, x, y, w, 0.06, NAVY)
        self.text(s, label, x + 0.18, y + 0.2, w - 0.3, 0.3, 10.5, bold=True, color=MUTED)
        self.text(s, value, x + 0.18, y + 0.52, w - 0.3, 0.5, 24, bold=True, color=NAVY)
        self.text(s, line, x + 0.18, y + 1.05, w - 0.3, 0.2, 9, color=MUTED)
        t = "No prior month to compare" if chg is None else f"{chg:+.1%} vs {self.R['vs']}"
        self.text(s, t, x + 0.18, y + 1.3, w - 0.3, 0.2, 10, bold=True, color=tone(chg, higher_better))

    def takeaway(self, s, x, y, w, h, blocks):
        self.rect(s, x, y, w, h, WHITE, line=NAVY, lw=1.25)
        self.rect(s, x, y, 0.12, h, YELLOW)
        tb = s.shapes.add_textbox(Inches(x + 0.35), Inches(y + 0.2), Inches(w - 0.6), Inches(h - 0.4))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        first = True
        for k, v in blocks:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            self.run(p, k, 11, True, BLUE)
            p2 = tf.add_paragraph(); p2.space_after = Pt(8)
            self.run(p2, v, 13, False, TEXT)

    @staticmethod
    def _borders(cell):
        """Thin bottom line only (the default table style draws white grid lines). Border elements must come before the fill in tcPr."""
        from lxml import etree

        ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        tcPr = cell._tc.get_or_add_tcPr()
        for tag in ("lnB", "lnT", "lnR", "lnL"):
            ln = etree.SubElement(tcPr, f"{{{ns}}}{tag}")
            tcPr.remove(ln)
            if tag == "lnB":
                ln.set("w", "9525")
                etree.SubElement(etree.SubElement(ln, f"{{{ns}}}solidFill"), f"{{{ns}}}srgbClr").set("val", LINE)
            else:
                ln.set("w", "0")
                etree.SubElement(ln, f"{{{ns}}}noFill")
            tcPr.insert(0, ln)

    def table(self, s, x, y, headers, rows, widths, aligns, row_h=0.44, size=10.5):
        gt = s.shapes.add_table(len(rows) + 1, len(headers), Inches(x), Inches(y), Inches(sum(widths)), Inches(row_h * (len(rows) + 1)))
        tbl = gt.table
        tblPr = gt._element.graphic.graphicData.tbl.tblPr
        for a in ("bandRow", "firstRow"):
            tblPr.set(a, "0")
        for j, wd in enumerate(widths):
            tbl.columns[j].width = Inches(wd)
        for i in range(len(rows) + 1):
            tbl.rows[i].height = Inches(row_h)
            for j in range(len(headers)):
                c = tbl.cell(i, j)
                c.fill.solid(); c.fill.fore_color.rgb = rgb(NAVY if i == 0 else WHITE)
                c.margin_left = c.margin_right = Inches(0.1)
                c.vertical_anchor = MSO_ANCHOR.MIDDLE
                self._borders(c)
                p = c.text_frame.paragraphs[0]
                p.alignment = PP_ALIGN.RIGHT if aligns[j] == "r" else PP_ALIGN.LEFT
                self.run(p, str(headers[j] if i == 0 else rows[i - 1][j]), size, bold=(i == 0 or j == 0), color=WHITE if i == 0 else (NAVY if j == 0 else TEXT))

    def line_chart(self, s, x, y, w, h, cats, vals, numfmt, label_fmt, flags=None):
        vals = list(vals)
        cd = CategoryChartData(); cd.categories = cats
        cd.add_series("Monthly value", [None if pd.isna(v) else float(v) for v in vals])
        flagged = [i for i, f in enumerate(flags or []) if f]
        if flagged:   # internal view: months whose Ads Manager export is probably incomplete, as their own marker-only series (renders in every viewer)
            cd.add_series("Export probably incomplete", [None if (i not in flagged or pd.isna(vals[i])) else float(vals[i]) for i in range(len(vals))])
        ch = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
        ch.has_title = False
        ch.has_legend = False
        ch.font.size, ch.font.name = Pt(9), FONT
        ch.font.color.rgb = rgb(MUTED)
        va = ch.value_axis
        va.major_gridlines.format.line.color.rgb = rgb("E9EEF3")
        va.format.line.fill.background()
        va.tick_labels.number_format, va.tick_labels.number_format_is_linked = numfmt, False
        ch.category_axis.format.line.color.rgb = rgb(LINE)
        ch.category_axis.has_major_gridlines = False
        ser = ch.plots[0].series[0]
        ser.smooth = False
        ser.format.line.color.rgb = rgb(BLUE); ser.format.line.width = Pt(2.5)
        ser.marker.style, ser.marker.size = XL_MARKER_STYLE.CIRCLE, 7
        ser.marker.format.fill.solid(); ser.marker.format.fill.fore_color.rgb = rgb(BLUE); ser.marker.format.line.color.rgb = rgb(NAVY)
        if flagged:
            s2 = ch.plots[0].series[1]
            s2.smooth = False
            s2.format.line.fill.background()
            s2.marker.style, s2.marker.size = XL_MARKER_STYLE.CIRCLE, 10
            s2.marker.format.fill.solid(); s2.marker.format.fill.fore_color.rgb = rgb(YELLOW); s2.marker.format.line.color.rgb = rgb(NAVY)
        valid = [i for i, v in enumerate(vals) if not pd.isna(v)]
        if valid:
            dl = ser.points[valid[-1]].data_label
            dl.position = XL_LABEL_POSITION.ABOVE
            tf = dl.text_frame
            tf.text = label_fmt(vals[valid[-1]])
            tf.paragraphs[0].runs[0].font.size, tf.paragraphs[0].runs[0].font.bold = Pt(10), True
            tf.paragraphs[0].runs[0].font.color.rgb = rgb(NAVY)
        return ch

    # --- slides ---
    def build(self):
        R, c, ch, org, tk, pm = self.R, self.R["cur"], self.R["chg"], self.R["org"], self.R["tk"], self.R["pm"]

        # 1. cover (the Swarm cover: navy block top-left, red bar bottom-right, right-aligned title)
        s = self.new()
        self.rect(s, 0, 0, 5.1, 3.7, NAVY)
        self.rect(s, 6.8, H - 0.74, W - 6.8, 0.74, RED)
        self.rect(s, 0, H - 0.74, 5.1, 0.74, RED)
        self.text(s, "BUDOL-PROOF PINOY", 5.6, 2.2, 7.1, 0.7, 30, color=BLUE, align=PP_ALIGN.RIGHT)
        self.text(s, "Brand Awareness", 4.6, 2.95, 8.1, 1.1, 48, bold=True, color=YELLOW, align=PP_ALIGN.RIGHT)
        self.text(s, "MONTHLY REVIEW", 5.6, 4.55, 7.1, 0.4, 18, bold=True, color=TEXT, align=PP_ALIGN.RIGHT)
        self.text(s, R["label"], 5.6, 4.95, 7.1, 0.4, 18, bold=True, color=TEXT, align=PP_ALIGN.RIGHT)
        self.text(s, "Draft: numbers to be checked against Meta and TikTok before this goes to the client.", 5.6, 5.55, 7.1, 0.4, 10, color=MUTED, align=PP_ALIGN.RIGHT)

        # 2. headline
        s = self.slide("Brand awareness,", R["label"], "Paid awareness on Facebook, with the organic Facebook page and TikTok alongside")
        self.text(s, R["headline"], 0.6, 1.75, 11.6, 1.3, 30, bold=True, color=NAVY)
        self.text(s, R["standfirst"], 0.6, 3.2, 11.4, 1.1, 14, color=TEXT)
        heroes = [("Reach", num(c["reach"]), ch["reach"], True), ("Cost per 1,000 reached", peso(c["cpr"], 2), ch["cpr"], False), ("Average frequency", f"{c['frequency']:.2f}", ch["frequency"], False)]
        for i, (lab, val, chg_, hb) in enumerate(heroes):
            x = 0.6 + i * 4.1
            self.rect(s, x, 4.6, 3.8, 0.05, NAVY)
            self.text(s, lab, x, 4.75, 3.8, 0.3, 11, bold=True, color=MUTED)
            self.text(s, val, x, 5.05, 3.8, 0.7, 36, bold=True, color=NAVY)
            self.text(s, "No prior month to compare" if chg_ is None else f"{chg_:+.1%} vs {R['vs']}", x, 5.8, 3.8, 0.3, 11, bold=True, color=tone(chg_, hb))
        self.note(s, "Reach is the sum of campaign reach in the Ads Manager export, and campaigns overlap, so unique reach is lower. Reach measures exposure, not recall.", y=6.4)

        # 3. paid awareness
        s = self.slide("Paid", "awareness", f"Facebook, Ads Manager, {R['label']}. Targets are pending sign-off, so nothing here is judged on target yet.")
        items = [("Ad spend", peso(c["spend"]), f"{c['campaigns']} campaigns", ch["spend"], None), ("Reach", num(c["reach"]), "Share of target audience: pending", ch["reach"], True),
                 ("Average frequency", f"{c['frequency']:.2f}", "Monthly; alert above 3 is weekly", ch["frequency"], False), ("Cost per 1,000 reached", peso(c["cpr"], 2), "Target pending", ch["cpr"], False),
                 ("Video view-through", pct(c["thru_rate"], 1), "ThruPlays / impressions", ch["thru_rate"], True)]
        for i, (lab, val, line, chg_, hb) in enumerate(items):
            self.kpi(s, 0.6 + i * 2.45, 1.75, 2.3, lab, val, line, chg_, hb)
        self.takeaway(s, 0.6, 3.75, 12.1, 2.35, [("Key takeaway", R["standfirst"]), ("Suggested focus (auto-generated)", R["focus"])])
        self.note(s, "Cost per 1,000 reached only compares reach campaigns: engagement boosts optimise for engagement, not reach.")

        # 4. awareness trend
        s = self.slide("Awareness", "Trend", f"Paid awareness on Facebook by month, up to {R['label']}. Weekly reach and target audiences are not available yet, so months are shown.")
        cats = [m.strftime("%b %y") for m in pm.index]
        flags = [m in R["gaps"] for m in pm.index] if R["internal"] else None
        specs = [("Reach (sum of campaign reach)", pm["reach"], "#,##0", short), ("Average frequency (impressions / reach)", pm["frequency"], "0.0", lambda v: f"{v:.2f}"),
                 ("Cost per 1,000 reached (₱)", pm["cpr"], "₱#,##0", lambda v: peso(v, 2)), ("Video view-through (ThruPlays / impressions)", pm["thru_rate"], "0%", lambda v: pct(v, 1))]
        for i, (title, vals, fmt, lab) in enumerate(specs):
            x, y = 0.6 + (i % 2) * 6.15, 1.65 + (i // 2) * 2.4
            self.text(s, title, x, y, 5.9, 0.25, 11, bold=True, color=NAVY)
            self.line_chart(s, x - 0.1, y + 0.25, 6.0, 2.05, cats, vals, fmt, lab, flags)
        n = "Reach is the sum of campaign reach per month, so it overstates unique reach. Frequency is monthly; the deck's alert level of 3 applies to weekly frequency."
        if R["internal"] and R["gaps"]:
            n = "INTERNAL: yellow markers are months whose Ads Manager export has less spend than the Ad Spend Report, so the export is probably incomplete. " + n
        self.note(s, n, y=6.4)

        # 5. paid campaigns
        s = self.slide("Paid", "campaigns", f"{R['label']}, largest spend first")
        rows = [[r["name"][:62], r["objective"], peso(r["spend"], 2), num(r["reach"]), f"{r['frequency']:.2f}" if not pd.isna(r["frequency"]) else "n/a", peso(r["cpr"], 2), pct(r["thru_rate"], 1)]
                for _, r in R["camps"].iterrows()]
        self.table(s, 0.6, 1.7, ["Campaign", "Type", "Spend", "Reach", "Freq.", "Cost / 1,000", "View-through"], rows, [4.7, 1.2, 1.35, 1.3, 0.9, 1.4, 1.25], ["l", "l", "r", "r", "r", "r", "r"], size=9.5)
        self.note(s, "Boosting campaigns optimise for engagement, so their cost per 1,000 reached is not comparable with reach campaigns.", y=6.1)

        # 6. facebook page
        s = self.slide("Facebook", "page", f"Organic posts published in {R['label']} (lifetime numbers of each post as exported)")
        co = R["chg_org"]
        for i, (lab, val, line, chg_) in enumerate([("Posts published", num(org["posts"]), "Facebook page", co["posts"]), ("Average reach per post", num(org["reach_per_post"]), "Lifetime reach", co["reach_per_post"]),
                                                    ("Engagement rate", pct(org["er"], 2), "Engagements / reach", co["er"]), ("Post views", num(org["views"]), "Facebook post views", co["views"])]):
            self.kpi(s, 0.6 + i * 3.05, 1.7, 2.9, lab, val, line, chg_, True, h=1.55)
        tp = R["tp"]
        rows = [[" ".join(str(r["title"]).split())[:70], r["type"], f"{r['published']:%d %b}", num(r["views"]), num(r["reach"]), pct(r["er"], 1)] for _, r in tp.iterrows()]
        self.text(s, "Top posts by reach", 0.6, 3.5, 6, 0.3, 13, bold=True, color=NAVY)
        if rows:
            self.table(s, 0.6, 3.9, ["Post", "Type", "Date", "Views", "Reach", "Eng. rate"], rows, [6.0, 1.3, 1.0, 1.3, 1.3, 1.2], ["l", "l", "l", "r", "r", "r"], row_h=0.4, size=9.5)

        # 7. tiktok
        s = self.slide("TikTok", "videos", f"Videos posted in {R['label']}. TikTok has views and engagement only in the source data, so there is no reach.")
        ct = R["chg_tk"]
        for i, (lab, val, line, chg_) in enumerate([("Videos posted", num(tk["videos"]), "TikTok", ct["videos"]), ("Video views", num(tk["views"]), f"{num(tk['views_per_video'])} per video", ct["views"]),
                                                    ("Engagements", num(tk["engagements"]), "Likes, comments, shares", ct["engagements"]), ("Engagement per view", pct(tk["eng_per_view"], 1), "Engagements / views", ct["eng_per_view"])]):
            self.kpi(s, 0.6 + i * 3.05, 1.7, 2.9, lab, val, line, chg_, True, h=1.55)
        tv = R["tv"]
        rows = [[" ".join(str(r["title"]).split())[:70], f"{r['posted']:%d %b}", num(r["views"]), num(r["likes"]), num(r["shares"]), pct(r["eng_per_view"], 1)] for _, r in tv.iterrows()]
        self.text(s, "Top videos by views", 0.6, 3.5, 6, 0.3, 13, bold=True, color=NAVY)
        if rows:
            self.table(s, 0.6, 3.9, ["Video", "Date", "Views", "Likes", "Shares", "Eng. / view"], rows, [6.0, 1.0, 1.3, 1.3, 1.3, 1.2], ["l", "l", "r", "r", "r", "r"], row_h=0.4, size=9.5)

        # 8. next steps and notes
        s = self.slide("What to look", "at next", "Written by the dashboard from the numbers; the planner adds the why and the plan")
        self.takeaway(s, 0.6, 1.75, 6.2, 1.9, [("Suggested focus (auto-generated)", R["focus"])])
        self.rect(s, 0.6, 3.9, 6.2, 2.3, WHITE, line=LINE, lw=1.25)
        self.text(s, "Planner's notes", 0.85, 4.05, 5.7, 0.3, 11, bold=True, color=BLUE)
        self.text(s, "Why it happened, and what we do next. To be written by the planner before this goes to the client.", 0.85, 4.4, 5.7, 1.0, 12, color=MUTED)
        self.text(s, "About these numbers", 7.3, 1.75, 5.4, 0.3, 13, bold=True, color=NAVY)
        tb = s.shapes.add_textbox(Inches(7.3), Inches(2.15), Inches(5.4), Inches(4.0))
        tf = tb.text_frame; tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        bullets = ["Reach is the sum of the campaign reach rows of the monthly Ads Manager export. Campaigns overlap, so unique reach is lower.",
                   "Frequency is impressions / reach over the month. The deck's alert level of 3 is weekly.",
                   "Cost per 1,000 reached = ad spend / reach x 1,000.",
                   "Engagement rate = reactions + comments + shares, divided by reach, for Facebook page posts.",
                   "Not available yet: weekly reach, target audiences (share of audience), follower growth, brand health.",
                   "Awareness is reported as delivery and cost. Reach measures exposure, not recall."]
        for i, b in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(7)
            self.run(p, "• " + b, 11, False, TEXT)
        if R["partial"]:
            self.note(s, f"{R['label']} was still running when the data was loaded: its numbers are partial.", y=6.4)
        return self.prs


def main():
    ap = argparse.ArgumentParser(description="Build the BPP brand awareness review deck")
    ap.add_argument("--month", help="YYYY-MM (default: last full month)")
    ap.add_argument("--live", action="store_true", help="read Supabase (secrets.toml or PULSE_DB_* variables) instead of the local snapshot")
    ap.add_argument("--internal", action="store_true", help="add the team-only data check (yellow months, note)")
    ap.add_argument("--out", help="output file (default out/BPP_Awareness_YYYY-MM.pptx)")
    a = ap.parse_args()
    conf = load_conf() if a.live else None
    if a.live and not conf:
        raise SystemExit("--live needs a [supabase] section in .streamlit/secrets.toml or PULSE_DB_* environment variables.")
    if not a.live and not D.snapshot_exists():
        raise SystemExit("No local snapshot (data/bpp_snapshot.json). Use --live to read Supabase.")
    S = D.load(conf)
    R = build_report(S, a.month, a.internal)
    out = Path(a.out) if a.out else HERE / "out" / f"BPP_Awareness_{R['m']}.pptx"
    out.parent.mkdir(parents=True, exist_ok=True)
    Deck(R).build().save(out)
    print(f"Saved {out}  ({R['label']}, source: {S['source']})")


if __name__ == "__main__":
    main()
