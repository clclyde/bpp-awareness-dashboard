# BPP Brand Awareness Review (Streamlit prototype)

A brand awareness version of the PediaWell dashboard for BPP (Budol-Proof Pinoy: Facebook page and TikTok). Requested by Sir Joven; first prototype.

## Design source
The Marketing 3.0 KPI deck (Example Reports): the dark Razza style, the **Modules** page (Paid awareness cards), the **Awareness Trend** page, key takeaway boxes, and status dots that stay grey while targets are pending sign-off. Three tabs:
1. **Page one**: Paid awareness (ad spend, reach, average frequency, cost per 1,000 reached, video view-through), Organic social (Facebook posts: reach, engagement rate, views), TikTok (videos, views, engagements), plus an auto takeaway.
2. **Awareness trend**: reach, frequency, cost per 1,000 reached and video view-through by month, and a paid campaigns table.
3. **Content**: top Facebook posts by reach, performance by post type, engagement rate by month, top TikTok videos.

## Look and feel
Colour scheme and font follow the Project Swarm 2026 Year-to-Date Report deck (values read from the deck file, not estimated): white background, navy `#073763` (headings, cards, table headers, top bar), title blue `#0B3691` (chart lines), yellow `#F1C232` (title highlight, section marks, incomplete-month markers), red `#D10000` (bottom bar, negative changes), text `#3F3F3F`, status green `#93C47D`. Font: **Montserrat** (the deck's main font), loaded from Google Fonts, with Open Sans as fallback. The PediaWell dashboard keeps its own dark design.

## Run
```bash
cd bpp_dashboard
../.venv/bin/streamlit run app.py
```
It needs `data/bpp_snapshot.json` (real client data, git-ignored, never commit). Without it the app says so and stops.

## Data
`data/bpp_snapshot.json` was built on 2026-10-19 from the BPP Content SSOT (Google Sheet):
- **ads**: the monthly Ads Manager export tabs (`AUG - AM` ... `OCT Ads`), Aug 2025 to 17 Oct 2026, one row per campaign (March 2026 is exported per ad).
- **posts**: the monthly Facebook post tabs (`AUG - Meta` ... `OCT FB`), one row per post.
- **tiktok**: the `YTD TikTok` tab, one row per video.
- **ad_spend_report**: BPP-FB monthly spend from the Ad Spend Report 2026, used only for the data check.

Cross-check: Ads Manager spend equals the Ad Spend Report's BPP-FB line to the cent for Jan, Mar, Jun, Jul and Aug 2026. Feb, Apr and May differ (the export tabs look incomplete); those months are marked amber on the trend charts. September and October are not in the Ad Spend Report yet.

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
Not deployable as is: the snapshot is git-ignored. To host it (for example on Streamlit Community Cloud) the BPP data has to go into Supabase first (the same sheets to Supabase work as for PediaWell), and the app then reads it with a read-only login.
