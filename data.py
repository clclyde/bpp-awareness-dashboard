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


def _prepare(ads, posts, tt, ref, built_at, source) -> dict:
    """Same typing and derived columns whether the rows come from Supabase or from the snapshot."""
    ads, posts, tt = ads.copy(), posts.copy(), tt.copy()
    for c in ["spend", "impressions", "reach", "thruplays", "post_engagements", "shares", "reactions", "saves", "comments", "fb_likes", "clicks_all"]:
        ads[c] = pd.to_numeric(ads[c], errors="coerce")
    ads["month"] = pd.to_datetime(ads["start"]).dt.to_period("M")
    ads["objective"] = ads["name"].str.extract(r"^BPP_[A-Za-z]+_([A-Za-z]+)", expand=False).str.lower().fillna("other")
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
    return {"ads": ads, "posts": posts, "tiktok": tt, "ref": {pd.Period(k, "M"): float(v) for k, v in ref.items()}, "built_at": built_at, "source": source}


def load_snapshot(path: Path = SNAPSHOT) -> dict:
    raw = json.loads(Path(path).read_text())
    built = pd.Timestamp(raw["built_at"]).tz_convert(None)
    return _prepare(pd.DataFrame(raw["ads"]), pd.DataFrame(raw["posts"]), pd.DataFrame(raw["tiktok"]), raw.get("ad_spend_report", {}), built,
                    f"BPP Content SSOT snapshot ({built:%d %b %Y})")


SQL = {
    "ads": 'select source_tab as tab, level, reporting_start as "start", reporting_end as "end", name, delivery, result_indicator, spend, impressions, reach, '
           "thruplays, post_engagements, shares, reactions, saves, comments, fb_likes, clicks_all from pulse.social_ads_monthly where account_code = 'BPP' order by id",
    "posts": "select post_id, published, title, type, duration, views, reach, engagements, reactions, comments, shares, clicks, permalink "
             "from pulse.fb_posts where account_code = 'BPP'",
    "tiktok": "select title, link, posted, views, likes, comments, shares, engagement from pulse.tiktok_videos where account_code = 'BPP'",
    "ref": "select month_start, spend_php from pulse.ad_spend_monthly where account_code = 'BPP' and client_code = 'BPP-FB' and source_tab = 'Summary'",
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
    ref = {pd.Timestamp(r.month_start).strftime("%Y-%m"): r.spend_php for r in raw["ref"].itertuples()}
    return _prepare(raw["ads"], raw["posts"], raw["tiktok"], ref, pd.Timestamp.now(), "Supabase (live)")


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
            "clicks_ok": clicks_ok, "tp_ok": tp_ok}


def unit_costs_by_objective(ads, m0, m1) -> pd.DataFrame:
    """Same unit costs split by campaign type (reach, boosting, pagelikes, other): the blended figure also moves with the mix of campaigns."""
    d = _in(ads, m0, m1)
    rows = {}
    for obj, g in d.groupby("objective"):
        sp, im, re, en = g["spend"].sum(), g["impressions"].sum(), g["reach"].sum(), g["post_engagements"].sum()
        rows[obj] = {"spend": sp, "cpm": _div(sp * 1000, im), "cpr1000": _div(sp * 1000, re), "cpe": _div(sp, en)}
    return pd.DataFrame(rows).T


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
