"""BPP (Budol-Proof Pinoy) brand awareness data layer.

Prototype source: data/bpp_snapshot.json, built from the BPP Content SSOT (git-ignored, real client data):
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


def load_snapshot(path: Path = SNAPSHOT) -> dict:
    raw = json.loads(Path(path).read_text())
    ads, posts, tt = pd.DataFrame(raw["ads"]), pd.DataFrame(raw["posts"]), pd.DataFrame(raw["tiktok"])
    for c in ["spend", "impressions", "reach", "thruplays", "post_engagements", "shares", "reactions", "saves", "comments", "fb_likes", "clicks_all"]:
        ads[c] = pd.to_numeric(ads[c], errors="coerce")
    ads["month"] = pd.to_datetime(ads["start"]).dt.to_period("M")
    ads["objective"] = ads["name"].str.extract(r"^BPP_[A-Za-z]+_([A-Za-z]+)", expand=False).str.lower().fillna("other")
    for c in ["views", "reach", "engagements", "reactions", "comments", "shares", "clicks", "duration"]:
        posts[c] = pd.to_numeric(posts[c], errors="coerce")
    posts["published"] = pd.to_datetime(posts["published"])
    posts["month"] = posts["published"].dt.to_period("M")
    for c in ["views", "likes", "comments", "shares", "engagement"]:
        tt[c] = pd.to_numeric(tt[c], errors="coerce")
    tt["posted"] = pd.to_datetime(tt["posted"])
    tt["month"] = tt["posted"].dt.to_period("M")
    ref = {pd.Period(k, "M"): v for k, v in raw.get("ad_spend_report", {}).items()}
    return {"ads": ads, "posts": posts, "tiktok": tt, "ref": ref, "built_at": pd.Timestamp(raw["built_at"]).tz_convert(None)}


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
