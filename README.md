# BPP Brand Awareness Review (Streamlit prototype)

A brand awareness version of the PediaWell dashboard for BPP (Budol-Proof Pinoy: Facebook page and TikTok). Requested by Sir Joven; first prototype.

## Design source
The Marketing 3.0 KPI deck (Example Reports): the dark Razza style, the **Modules** page (Paid awareness cards), the **Awareness Trend** page, key takeaway boxes, and status dots that stay grey while targets are pending sign-off. Three tabs:
1. **Page one**: Paid awareness (ad spend, reach, average frequency, cost per 1,000 reached, video view-through), Facebook page posts, including boosted posts (reach, engagement rate, views), TikTok (videos, views, engagements), plus an auto takeaway.
2. **Awareness trend**: reach, frequency, cost per 1,000 reached and video view-through by month, and a paid campaigns table.
3. **Content**: top Facebook posts by reach, performance by post type, engagement rate by month, top TikTok videos.

## Look and feel
Editorial layout (2026-10-20): headline sentence first, then figures with sparklines, then charts and tables; native Streamlit theming in `.streamlit/config.toml` (Streamlit 1.66). Headings use Source Serif 4 (serif), body and figures Montserrat. A plain yellow rule tops the page and a red bar closes it. The tabs are First vs Second Half, Overview, Awareness Trend, Content and Channel Diagnostics. Page titles, tab names and section headings are in Title Case; figure labels and captions stay in sentence case.

Colour scheme and font follow the Project Swarm 2026 Year-to-Date Report deck (values read from the deck file, not estimated): white background, navy `#073763` (headings, cards, table headers, top bar), title blue `#0B3691` (chart lines), yellow `#F1C232` (title highlight, section marks, incomplete-month markers), red `#D10000` (bottom bar, negative changes), text `#3F3F3F`, status green `#93C47D`. Font: **Montserrat** (the deck's main font), loaded from Google Fonts, with Open Sans as fallback. The PediaWell dashboard keeps its own dark design.

## Run
```bash
cd bpp_dashboard
../.venv/bin/streamlit run app.py
```
The app reads Supabase when it finds `[supabase]` settings (`.streamlit/secrets.toml`, or `PULSE_DB_*` environment variables), using the read-only `pulse_reader_bpp` login. Without settings it falls back to a local, git-ignored `data/bpp_snapshot.json` if present, otherwise it shows an error box. Hosting: see `DEPLOY.md`.

## Data
The data comes from the BPP Content SSOT (Google Sheet) and lives in Supabase (`social_ads_monthly`, `fb_posts`, `tiktok_videos`, read with the BPP-only login). A local, git-ignored `data/bpp_snapshot.json` is the fallback and the file the seed is generated from:
- **ads**: the monthly Ads Manager export tabs (`AUG - AM` ... `OCT Ads`), one row per campaign (March 2026 is exported per ad).
- **posts**: the monthly Facebook post tabs plus the `YTD Meta` tab (a few posts were missing from the monthly tabs and were added from it).
- **tiktok**: `YTD TikTok` (2026) plus the `AUG - TT` and `SEPT - TT` tabs (2025). The SSOT has no TikTok videos for Oct to Dec 2025, so those months are treated as missing data, not zero.
- **ad_spend_report**: BPP-FB monthly spend from the Ad Spend Report 2026, used only for the internal data check.

Known gaps: the February, April and May 2026 Ads Manager tabs look incomplete (spend below the Ad Spend Report), so those months are understated; they are marked in the internal view. Not integrated yet: TikTok ad spend, follower counts, post sentiment, budget pacing. The refresh is manual (read the sheet, rebuild the snapshot, generate and run the seed); an n8n loader is not built.

## Definitions and differences from the deck
Follows the deck's Paid awareness definitions, with these differences, all stated on the pages:
- The deck's standard is **weekly** reach (1+, Monday to Sunday, per platform) as a **% of a target audience**. The SSOT has monthly exports and no target audience, so reach is monthly and "share of target audience" is pending.
- **Reach** is the sum of the campaign reach rows in each export. Campaigns overlap, so it overstates unique reach. It is not added across platforms (TikTok is shown by views).
- **Average frequency** is impressions / reach over the month; the deck's alert level of 3 is weekly.
- **Cost per 1,000 reached** = ad spend / reach x 1,000. It only makes sense for reach campaigns; engagement boosts optimise for engagement, and the page-one focus text compares reach campaigns only.
- **Engagement rate** = reactions + comments + shares / reach, for Facebook page posts (lifetime numbers per post).
- TikTok has views and engagement only, so "engagement per view".
- Awareness is reported as delivery and cost: reach measures exposure, not recall.

## Not available yet
Weekly reach, target audiences, follower growth, brand health (branded search, brand lift, survey). The "Targets" tab (`Tables`) of the SSOT holds Aug and Sep **2025** figures, so it is not used.

## Hosting
Streamlit Community Cloud as its own app from the private repo `clclyde/bpp-awareness-dashboard`; the data lives in Supabase (tables `social_ads_monthly`, `fb_posts`, `tiktok_videos`). Steps in `DEPLOY.md`.
