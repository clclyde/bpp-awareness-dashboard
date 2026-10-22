# BPP brand awareness review deck

`report_deck.py` builds an 8-slide .pptx from the same numbers as the dashboard (`data.py`), in the Project Swarm look (white, navy block, yellow title word, red bar, Montserrat). Native editable charts and tables; opens in PowerPoint and Google Slides (File > Import slides). Install Montserrat for PowerPoint; Google Slides has it.

```bash
pip install -r requirements-report.txt
python report_deck.py --month 2026-09            # local snapshot (data/bpp_snapshot.json)
python report_deck.py --month 2026-09 --live     # Supabase, using .streamlit/secrets.toml or PULSE_DB_* variables
python report_deck.py --month 2026-09 --internal # adds the team-only data check (yellow months, note on the trend slide)
python report_deck.py --halves                   # half vs half review, the KPI Cards tab as slides (default: 6 months from Oct 2025)
python report_deck.py --halves --start 2025-10 --n 6 --live
```
Half vs half output: `out/BPP_Awareness_Halves_<start>_<n>m_<layout>.pptx`, 2 slides, both titled "Platform Distribution Level Up", in the look of the "Share-Led Content Focus" deck (cream page, dark ink, deep green for results that improved, burnt orange for results that got worse, DM Sans, white rounded cards, dark note bar; install DM Sans for PowerPoint, Google Slides has it). Slide 1 is how far the content travelled (reach per Facebook post, Facebook post views, TikTok video views, paid reach, reach and impressions per ₱1,000, TikTok engagement per view, plus a note on boosted posts); slide 2 is what each peso delivered (engagements per ₱1,000, cost per engagement, CPM, ad engagement rate, cost per 1,000 reached, spend, frequency, posts, videos, Facebook engagement rate). `--layout cards` (default): every figure is a card, three key cards with monthly sparklines and smaller cards below, in the order number now, filled change pill, previous number. `--layout halves`: like the dashboard's first tab, the first period in a panel on the left (numbers with a Baseline pill) and the next period on the right (numbers with the change pill), every metric level across both. `--layout table`: three key cards and the other figures as table rows. The cards come from `data.half_cards`, the same list the dashboard's KPI Cards tab uses; a card the layout does not list (click-through rate, cost per click once clicks are loaded) is added to slide 2. Speaker notes explain how to read the slides. The monthly deck keeps the Project Swarm look.

Monthly output: `out/BPP_Awareness_YYYY-MM.pptx` (git-ignored: real client numbers). Without `--month` it uses the last full month.

Slides: 1 cover, 2 headline and three key figures, 3 paid awareness (5 KPIs + key takeaway), 4 awareness trend (4 charts, 12 months), 5 paid campaigns, 6 Facebook page, 7 TikTok, 8 what to look at next + planner's notes box + definitions.

Rules: the text is rule-based (no LLM); a person checks the numbers against Meta and TikTok and writes the why and what next (Playbook 3.1, 4.9), so the closing slide leaves a box for the planner. The default build is the client version (no data-quality check). The February and May 2026 exports are incomplete, so those months' figures are understated until the SSOT is re-exported.
Next step if wanted: fill a Google Slides template with `replaceAllText` placeholders, as in the PediaWell `report_deck.py` (`--slides`), once Sir Joven provides the template.
