"""BPP (Budol-Proof Pinoy) brand awareness data layer.

Source: Supabase schema pulse (tables social_ads_monthly, fb_posts, tiktok_videos and the BPP rows of ad_spend_monthly), read with the read-only
pulse_reader_bpp login, which can only see account_code = BPP. Without database settings, a local data/bpp_snapshot.json is used
(built from the BPP Content SSOT; git-ignored, real client data, development only):
  ads     Ads Manager exports, one row per campaign (or ad) and month, Aug 2025 to now (spend, impressions, reach, ThruPlays, engagements)
  posts   Facebook page posts (views, reach, engagements), one row per post
  tiktok  TikTok videos (views, likes, comments, shares, engagement)
  ad_spend_report  BPP-FB monthly spend from the Ad Spend Report 2026, only used to cross-check the Ads Manager exports

Definitions follow the Marketing 3.0 KPI deck (Paid awareness module), with these differences, shown on the page:
  * the deck's standard is WEEKLY reach (1+, Mon-Sun, per platform) as a % of a target audience. The SSOT only has monthly exports and no
    target audience, so reach is monthly and the audience share is "pending";
  * reach is the sum of the campaign (or ad) reach rows of an export. Campaigns overlap, so this overstates unique reach;
  * frequency is impressions / reach over the month (the deck's alert level of 3 is weekly).
"""
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
SNAPSHOT = DATA_DIR / "bpp_snapshot.json"


def snapshot_exists() -> bool:
    return SNAPSHOT.exists()


PLATFORM_METRICS = {"fb_followers": "Facebook followers", "tt_followers": "TikTok followers", "tt_reach": "TikTok reach", "tt_engagement": "TikTok engagements"}


def platform_period(tt_platform, m0, m1) -> dict:
    """TikTok analytics figures whose period is exactly the months m0..m1 (first day of m0 to last day of m1): {metric: value}. Empty when the periods do not match."""
    if tt_platform is None or len(tt_platform) == 0:
        return {}
    start, end = m0.start_time.normalize(), m1.end_time.normalize()
    d = tt_platform[(tt_platform["start"] == start) & (tt_platform["end"] == end)]
    return {r.metric: float(r.value) for r in d.itertuples() if pd.notna(r.value)}


def _prepare(ads, posts, tt, ref, built_at, source, ref_tt=None, page=None) -> dict:
    """Same typing and derived columns whether the rows come from Supabase or from the snapshot."""
    ads, posts, tt = ads.copy(), posts.copy(), tt.copy()
    for c in ["spend", "impressions", "reach", "thruplays", "post_engagements", "shares", "reactions", "saves", "comments", "fb_likes", "clicks_all"]:
        ads[c] = pd.to_numeric(ads[c], errors="coerce")
    ads["month"] = pd.to_datetime(ads["start"]).dt.to_period("M")
    ads["objective"] = ads["name"].str.extract(r"^BPP_[A-Za-z]+_([A-Za-z]+)", expand=False).str.lower().fillna("other")
    # level 'account' rows are Meta's own monthly totals for the whole ad account (unique reach per month): kept apart, they must never be summed with the campaign rows
    acct = ads[ads["level"] == "account"][["month", "spend", "impressions", "reach", "clicks_all"]].reset_index(drop=True)
    ads = ads[ads["level"] != "account"].reset_index(drop=True)
    for c in ["views", "reach", "engagements", "reactions", "comments", "shares", "clicks", "duration"]:
        posts[c] = pd.to_numeric(posts[c], errors="coerce")
    posts["published"] = pd.to_datetime(posts["published"])
    posts["month"] = posts["published"].dt.to_period("M")
    posts["permalink"] = posts["permalink"].fillna("")
    posts["title"] = posts["title"].fillna("")
    for c in ["views", "likes", "comments", "shares", "engagement"]:
        tt[c] = pd.to_numeric(tt[c], errors="coerce")
    tt["posted"] = pd.to_datetime(tt["posted"])
    tt["month"] = tt["posted"].dt.to_period("M")
    tt["link"] = tt["link"].fillna("")
    # Facebook page figures from Business Suite (long format): follows per month, and whole-period totals that cannot be split by month
    page = pd.DataFrame(columns=["metric", "start", "end", "value"]) if page is None else page.copy()
    page["value"] = pd.to_numeric(page["value"], errors="coerce")
    follows = page[page["metric"] == "follows_month"].copy()
    follows["month"] = pd.to_datetime(follows["start"]).dt.to_period("M")
    follows = follows.rename(columns={"value": "follows"})[["month", "follows"]].sort_values("month").reset_index(drop=True)
    page_ctx = {r.metric: float(r.value) for r in page[page["metric"].isin(["followers_lifetime", "net_follows", "unfollows"])].itertuples()}
    # Platform analytics figures of a whole period (Facebook followers, TikTok followers, reach, engagement), supplied by the team: they are not sums of videos and cannot be split by month
    tt_platform = page[page["metric"].isin(PLATFORM_METRICS)][["metric", "start", "end", "value"]].copy()
    tt_platform["start"], tt_platform["end"] = pd.to_datetime(tt_platform["start"]), pd.to_datetime(tt_platform["end"])
    return {"ads": ads, "acct": acct, "follows": follows, "page": page_ctx, "tt_platform": tt_platform, "posts": posts, "tiktok": tt, "ref": {pd.Period(k, "M"): float(v) for k, v in ref.items()},
            "ref_tt": {pd.Period(k, "M"): float(v) for k, v in (ref_tt or {}).items()}, "built_at": built_at, "source": source}


def load_snapshot(path: Path = SNAPSHOT) -> dict:
    raw = json.loads(Path(path).read_text())
    built = pd.Timestamp(raw["built_at"]).tz_convert(None)
    return _prepare(pd.DataFrame(raw["ads"]), pd.DataFrame(raw["posts"]), pd.DataFrame(raw["tiktok"]), {**raw.get("ad_spend_report", {}), **raw.get("ad_spend_fb_csm", {})}, built,
                    f"BPP Content SSOT snapshot ({built:%d %b %Y})", raw.get("tiktok_ad_spend", {}), pd.DataFrame(raw.get("page_metrics", [])))


SQL = {
    "ads": 'select source_tab as tab, level, reporting_start as "start", reporting_end as "end", name, delivery, result_indicator, spend, impressions, reach, '
           "thruplays, post_engagements, shares, reactions, saves, comments, fb_likes, clicks_all from pulse.social_ads_monthly where account_code = 'BPP' order by id",
    "posts": "select post_id, published, title, type, duration, views, reach, engagements, reactions, comments, shares, clicks, permalink "
             "from pulse.fb_posts where account_code = 'BPP'",
    "tiktok": "select title, link, posted, views, likes, comments, shares, engagement from pulse.tiktok_videos where account_code = 'BPP'",
    # Facebook spend reference: the Ad Spend Report Summary, replaced by Campaign Spend Monitoring for the months where the Summary figure includes VAT
    "page": 'select metric, period_start as "start", period_end as "end", value from pulse.fb_page_metrics where account_code = \'BPP\'',
    "ref": "select month_start, spend_php, source_tab from pulse.ad_spend_monthly where account_code = 'BPP' and client_code = 'BPP-FB' "
           "and source_tab in ('Summary', 'Campaign Spend Monitoring')",
    # TikTok ad spend, ex-VAT: the Campaign Spend Monitoring sheet (2026), the SSOT TikTok tabs (Aug and Oct 2025) and the Ad Spend Report 2025 Summary (Sep, Nov and Dec 2025).
    # Not the 2026 Ad Spend Report's BPP-TT line, which mixes VAT bases.
    "ref_tt": "select month_start, spend_php from pulse.ad_spend_monthly where account_code = 'BPP' and client_code = 'BPP-TT' and source_tab in ('Campaign Spend Monitoring', 'SSOT TT tabs', 'Ad Spend Report 2025')",
}


def _query(conf: dict) -> dict:
    """Read-only queries with the pulse_reader_bpp login (it can only SELECT BPP rows)."""
    import psycopg2

    con = psycopg2.connect(host=conf["host"], port=int(conf.get("port", 5432)), dbname=conf.get("dbname", "postgres"), user=conf["user"], password=conf["password"],
                           sslmode=conf.get("sslmode", "require"), connect_timeout=10, options="-c default_transaction_read_only=on")
    try:
        out = {}
        with con.cursor() as cur:
            for name, sql in SQL.items():
                cur.execute(sql)
                out[name] = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
        return out
    finally:
        con.close()


def load_db(conf: dict) -> dict:
    raw = _query(conf)
    rows = sorted(raw["ref"].itertuples(), key=lambda r: r.source_tab == "Campaign Spend Monitoring")   # Campaign Spend Monitoring wins
    ref = {pd.Timestamp(r.month_start).strftime("%Y-%m"): r.spend_php for r in rows}
    ref_tt = {pd.Timestamp(r.month_start).strftime("%Y-%m"): r.spend_php for r in raw["ref_tt"].itertuples()}
    return _prepare(raw["ads"], raw["posts"], raw["tiktok"], ref, pd.Timestamp.now(), "Supabase (live)", ref_tt, raw["page"])


def load(conf: dict | None = None) -> dict:
    return load_db(conf) if conf else load_snapshot()


def _div(a, b):
    return float(a) / float(b) if b and not pd.isna(b) and b != 0 and not pd.isna(a) else float("nan")


def _in(df: pd.DataFrame, m0, m1) -> pd.DataFrame:
    return df[(df["month"] >= m0) & (df["month"] <= m1)]


def paid(ads, m0, m1) -> dict:
    """Paid awareness (Facebook / Meta) for the months m0..m1."""
    d = _in(ads, m0, m1)
    n = d["month"].nunique()
    spend, impr, reach = d["spend"].sum(), d["impressions"].sum(), d["reach"].sum()
    tv = d[d["thruplays"].notna()]
    return {"months": n, "rows": len(d), "spend": spend, "impressions": impr, "reach": reach, "reach_avg": _div(reach, n),
            "frequency": _div(impr, reach), "cpr": _div(spend * 1000, reach), "thru_rate": _div(tv["thruplays"].sum(), tv["impressions"].sum()),
            "campaigns": d["name"].nunique()}


def organic(posts, m0, m1) -> dict:
    """Facebook page posts published in the months m0..m1 (lifetime numbers of each post as exported)."""
    d = _in(posts, m0, m1)
    reach, eng = d["reach"].sum(), d["engagements"].sum()
    return {"posts": len(d), "views": d["views"].sum(), "reach": reach, "reach_per_post": _div(reach, len(d)), "engagements": eng, "er": _div(eng, reach)}


def tiktok(tt, m0, m1) -> dict:
    d = _in(tt, m0, m1)
    views, eng = d["views"].sum(), d["engagement"].sum()
    return {"videos": len(d), "views": views, "engagements": eng, "eng_per_view": _div(eng, views), "views_per_video": _div(views, len(d))}


def prior_months(m0, m1):
    n = (m1 - m0).n + 1
    return m0 - n, m1 - n


def account_period(acct, m0, m1) -> dict:
    """Meta's account totals (all campaigns together) for the months m0..m1. Reach is unique people within each month, so the period figure is the monthly
    average, and the frequency divides the impressions by the summed monthly reach (a month's reach cannot be added across months into one unique figure)."""
    d = _in(acct, m0, m1)
    n = d["month"].nunique()
    sp, im, re, cl = d["spend"].sum(), d["impressions"].sum(), d["reach"].sum(), d["clicks_all"].sum()
    return {"months": n, "spend": sp, "impressions": im, "clicks": cl, "reach_avg": _div(re, n), "frequency": _div(im, re), "ctr": _div(cl, im), "cpc": _div(sp, cl)}


def unit_costs(ads, m0, m1) -> dict:
    """Unit costs of the paid Facebook ads in the months m0..m1, and what each PHP 1,000 of spend bought.
    Clicks and ThruPlays only exist in the exports from Mar 2026, so cost per click / per ThruPlay are only filled when every month of the range has them."""
    d = _in(ads, m0, m1)
    months = [m0 + i for i in range((m1 - m0).n + 1)]
    spend, impr, reach, eng = d["spend"].sum(), d["impressions"].sum(), d["reach"].sum(), d["post_engagements"].sum()

    def covered(col):
        return all(d[(d["month"] == m) & d[col].notna()].shape[0] > 0 for m in months)

    ck, tp = d[d["clicks_all"].notna()], d[d["thruplays"].notna()]
    clicks_ok, tp_ok = covered("clicks_all"), covered("thruplays")
    return {"spend": spend, "impressions": impr, "reach": reach, "engagements": eng,
            "cpm": _div(spend * 1000, impr), "cpr1000": _div(spend * 1000, reach), "cpe": _div(spend, eng),
            "cpc": _div(ck["spend"].sum(), ck["clicks_all"].sum()) if clicks_ok else float("nan"),
            "cptp": _div(tp["spend"].sum(), tp["thruplays"].sum()) if tp_ok else float("nan"),
            "impr_per_k": _div(impr * 1000, spend), "reach_per_k": _div(reach * 1000, spend), "eng_per_k": _div(eng * 1000, spend),
            "ctr": _div(ck["clicks_all"].sum(), ck["impressions"].sum()) if clicks_ok else float("nan"), "frequency": _div(impr, reach),
            "er_impr": _div(eng, impr),   # ad engagement rate: post engagements / impressions
            "clicks_ok": clicks_ok, "tp_ok": tp_ok}


def half_cards(ads, posts, tt, a0, n, acct=None, follows=None, tt_platform=None) -> dict:
    """The KPI cards of the half vs half comparison: the first n months from a0 against the next n months.
    Used by the dashboard's KPI Cards tab and by the deck (report_deck.py --halves), so both show the same cards in the same order.
    Groups run from the strongest results to the context (agreed 2026-10-21, the report makes the case for renewing); each group is a list of rows.
    Card keys: label, a (first period), b (second period), better (True higher is better, False lower is better, None neither),
    kind (formatting: num, peso0, peso2, peso3, rate, freq), hint, series (monthly values over both periods, for a sparkline), compared
    and paid_series (the series comes from the Ads Manager exports, so incomplete-export months can be marked).
    acct = Meta's account-level monthly totals (S["acct"]): they add unique reach per month, true frequency, click-through rate and cost per click, and only
    appear when every month of both periods has an account row.
    follows = new Facebook page follows per month (S["follows"], Business Suite, before unfollows): they add new follows and new follows per 1,000 of ad spend when every
    month of both periods has a figure. Net new followers need unfollows per month, which are not available, so they are not computed.
    tt_platform = platform analytics figures of a whole period (S["tt_platform"]): Facebook followers and TikTok followers, reach and engagement appear as a third Audience Growth row only when the
    stored periods are exactly the two periods compared (they cannot be split by month, so there is no sparkline)."""
    a1, b0, b1 = a0 + (n - 1), a0 + n, a0 + (2 * n - 1)
    months = [a0 + i for i in range(2 * n)]
    ca, cb = paid(ads, a0, a1), paid(ads, b0, b1)
    ua, ub = unit_costs(ads, a0, a1), unit_costs(ads, b0, b1)
    oa, ob = organic(posts, a0, a1), organic(posts, b0, b1)
    ta, tb = tiktok(tt, a0, a1), tiktok(tt, b0, b1)
    tt_ok = all(m in set(tt["month"].unique()) for m in months)

    def card(label, a, b, better, kind, hint=None, series=None, compared=True, paid_series=False):
        return {"label": label, "a": a, "b": b, "better": better, "kind": kind, "hint": hint, "compared": compared, "paid_series": paid_series,
                "series": None if series is None else [series(m) for m in months]}

    fol_ok = follows is not None and len(follows) > 0 and all(m in set(follows["month"]) for m in months)
    if fol_ok:
        fm = dict(zip(follows["month"], follows["follows"].astype(float)))
        fa, fb = sum(fm[m] for m in months[:n]), sum(fm[m] for m in months[n:])
        new_follows = [card("New Facebook follows", fa, fb, True, "num", "new follows before unfollows", series=lambda m: fm[m])]
        follows_per_k = [card("New follows per ₱1,000", _div(fa * 1000, ca["spend"]), _div(fb * 1000, cb["spend"]), True, "num1", "all new follows / Facebook ad spend")]
    else:
        new_follows, follows_per_k = [], []
    acct_ok = acct is not None and len(acct) > 0 and all(m in set(acct["month"]) for m in months)
    if acct_ok:    # Meta's account totals cover every month, so clicks need no campaign data
        xa, xb = account_period(acct, a0, a1), account_period(acct, b0, b1)
        unique = [card("Unique people reached per month", xa["reach_avg"], xb["reach_avg"], True, "num", "Facebook ads, each person counted once a month",
                       series=lambda m: account_period(acct, m, m)["reach_avg"])]
        true_freq = [card("True frequency", xa["frequency"], xb["frequency"], None, "freq", "impressions / unique reach")]
        clicks = [card("Click-through rate (CTR)", xa["ctr"], xb["ctr"], True, "rate", "clicks / impressions"),
                  card("Cost per click", xa["cpc"], xb["cpc"], False, "peso2", "lower is better")]
    else:          # campaign exports only have clicks from Mar 2026
        unique, true_freq = [], []
        clicks = [card("Click-through rate (CTR)", ua["ctr"], ub["ctr"], True, "rate", "clicks / impressions"),
                  card("Cost per click", ua["cpc"], ub["cpc"], False, "peso2", "lower is better")] if (ua["clicks_ok"] and ub["clicks_ok"]) else []
    pa, pb = platform_period(tt_platform, a0, a1), platform_period(tt_platform, b0, b1)
    platform = [card(PLATFORM_METRICS[k], pa[k], pb[k], True, "num", "platform analytics, figure of the whole period") for k in PLATFORM_METRICS if k in pa and k in pb]
    groups = [
        ("Audience Growth", [
            new_follows + [card("Average reach per Facebook post", oa["reach_per_post"], ob["reach_per_post"], True, "num", series=lambda m: organic(posts, m, m)["reach_per_post"]),
             card("Facebook post views", oa["views"], ob["views"], True, "num", series=lambda m: organic(posts, m, m)["views"]),
             card("TikTok video views", ta["views"], tb["views"], True, "num", series=lambda m: tiktok(tt, m, m)["views"], compared=tt_ok)],
            [card("Paid reach per month", ca["reach_avg"], cb["reach_avg"], True, "num", "Facebook ads"),
             card("Total reach", ca["reach"], cb["reach"], True, "num", "sum of the monthly campaign reach, Facebook ads", series=lambda m: paid(ads, m, m)["reach"], paid_series=True)] + unique
            + [card("TikTok engagement per view", ta["eng_per_view"], tb["eng_per_view"], True, "rate", "likes, comments, shares / views", compared=tt_ok)]]
            + ([platform] if platform else [])),
        ("More From Every Peso Spent", [
            [card("Ad post engagements", ua["engagements"], ub["engagements"], True, "num", "Facebook ads, as counted by Ads Manager", series=lambda m: unit_costs(ads, m, m)["engagements"], paid_series=True),
             card("Engagements per ₱1,000", ua["eng_per_k"], ub["eng_per_k"], True, "num", "higher is better", series=lambda m: unit_costs(ads, m, m)["eng_per_k"], paid_series=True),
             card("Cost per engagement", ua["cpe"], ub["cpe"], False, "peso3", "lower is better", series=lambda m: unit_costs(ads, m, m)["cpe"], paid_series=True),
             card("Cost per mille (CPM)", ua["cpm"], ub["cpm"], False, "peso2", "lower is better", series=lambda m: unit_costs(ads, m, m)["cpm"], paid_series=True)],
            follows_per_k + [card("Ad engagement rate", ua["er_impr"], ub["er_impr"], True, "rate", "engagements / impressions"),
             card("Impressions per ₱1,000", ua["impr_per_k"], ub["impr_per_k"], True, "num", "higher is better")] + clicks]),
        ("Spend and Activity", [
            [card("Ad spend per month", ca["spend"] / n, cb["spend"] / n, None, "peso0", "Facebook ads"),
             card("Cost per 1,000 reached", ua["cpr1000"], ub["cpr1000"], False, "peso2", "lower is better"),
             card("Reach per ₱1,000", ua["reach_per_k"], ub["reach_per_k"], True, "num", "higher is better"),
             card("Average frequency", ca["frequency"], cb["frequency"], None, "freq", "impressions / reach")] + true_freq,
            [card("Facebook posts published", oa["posts"], ob["posts"], True, "num"),
             card("TikTok videos posted", ta["videos"], tb["videos"], True, "num", compared=tt_ok),
             card("Facebook engagement rate", oa["er"], ob["er"], True, "rate", "engagements / reach")]]),
    ]
    return {"a": (a0, a1), "b": (b0, b1), "months": months, "groups": groups, "clicks_ok": acct_ok or (ua["clicks_ok"] and ub["clicks_ok"]), "tt_ok": tt_ok}


def unit_costs_by_objective(ads, m0, m1) -> pd.DataFrame:
    """Same unit costs split by campaign type (reach, boosting, pagelikes, other): the blended figure also moves with the mix of campaigns."""
    d = _in(ads, m0, m1)
    rows = {}
    for obj, g in d.groupby("objective"):
        sp, im, re, en = g["spend"].sum(), g["impressions"].sum(), g["reach"].sum(), g["post_engagements"].sum()
        rows[obj] = {"spend": sp, "impressions": im, "reach": re, "engagements": en, "frequency": _div(im, re),
                     "cpm": _div(sp * 1000, im), "cpr1000": _div(sp * 1000, re), "cpe": _div(sp, en)}
    return pd.DataFrame(rows).T


def tiktok_ad_spend(ref_tt, m0, m1):
    """TikTok ad spend (ex-VAT) of the months m0..m1: Campaign Spend Monitoring for 2026, SSOT TikTok tabs for Aug and Oct 2025, Ad Spend Report 2025 for Sep, Nov and Dec 2025. NaN unless every month of the range has a figure."""
    months = [m0 + i for i in range((m1 - m0).n + 1)]
    return float(sum(ref_tt[m] for m in months)) if all(m in ref_tt for m in months) else float("nan")


def paid_monthly(ads) -> pd.DataFrame:
    g = pd.DataFrame({m: paid(ads, m, m) for m in sorted(ads["month"].unique())}).T
    return g[["spend", "impressions", "reach", "frequency", "cpr", "thru_rate", "campaigns"]].astype(float)


def organic_monthly(posts) -> pd.DataFrame:
    g = posts.groupby("month").agg(posts=("post_id", "count"), reach=("reach", "sum"), engagements=("engagements", "sum"), views=("views", "sum"))
    g["er"] = g["engagements"] / g["reach"]
    return g


def tiktok_monthly(tt) -> pd.DataFrame:
    g = tt.groupby("month").agg(videos=("title", "count"), views=("views", "sum"), engagement=("engagement", "sum"))
    g["eng_per_view"] = g["engagement"] / g["views"]
    return g


def campaigns(ads, m0, m1) -> pd.DataFrame:
    d = _in(ads, m0, m1)
    c = d.groupby(["name", "objective"]).agg(spend=("spend", "sum"), impressions=("impressions", "sum"), reach=("reach", "sum"),
                                              thruplays=("thruplays", "sum")).reset_index()
    c = c[c["spend"] > 0].copy()
    c["frequency"] = c["impressions"] / c["reach"].where(c["reach"] > 0)
    c["cpr"] = c["spend"] * 1000 / c["reach"].where(c["reach"] > 0)
    c["thru_rate"] = c["thruplays"] / c["impressions"].where(c["impressions"] > 0)
    return c.sort_values("spend", ascending=False)


def top_posts(posts, m0, m1, n=10) -> pd.DataFrame:
    d = _in(posts, m0, m1).copy()
    d["er"] = d["engagements"] / d["reach"].where(d["reach"] > 0)
    return d.sort_values("reach", ascending=False).head(n)


def by_post_type(posts, m0, m1) -> pd.DataFrame:
    d = _in(posts, m0, m1)
    g = d.groupby("type").agg(posts=("post_id", "count"), reach=("reach", "sum"), views=("views", "sum"), engagements=("engagements", "sum"))
    g["reach_per_post"] = g["reach"] / g["posts"]
    g["er"] = g["engagements"] / g["reach"].where(g["reach"] > 0)
    return g.sort_values("reach_per_post", ascending=False)


def top_tiktok(tt, m0, m1, n=8) -> pd.DataFrame:
    d = _in(tt, m0, m1).copy()
    d["eng_per_view"] = d["engagement"] / d["views"].where(d["views"] > 0)
    return d.sort_values("views", ascending=False).head(n)


def last_full_month(ads, built_at):
    """Latest month with ads data that is before the month the snapshot was built (that month is still running)."""
    done = [m for m in sorted(ads["month"].unique()) if m < pd.Period(built_at, "M")]
    return done[-1]


def spend_check(ads, ref) -> pd.DataFrame:
    """Ads Manager spend per month vs the Ad Spend Report's BPP-FB figure (same ex-VAT basis)."""
    m = ads.groupby("month")["spend"].sum()
    rows = [(p, m.get(p, float("nan")), v) for p, v in sorted(ref.items())]
    out = pd.DataFrame(rows, columns=["month", "ads_manager", "ad_spend_report"]).set_index("month")
    out["difference"] = out["ads_manager"] - out["ad_spend_report"]
    return out
