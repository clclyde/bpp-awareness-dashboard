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
Half vs half output: `out/BPP_Awareness_Halves_<start>_<n>m.pptx`, 3 slides: cover; every metric on one slide (one band per card group, strongest first: Audience Growth and More From Every Peso Spent as five cards with monthly sparklines, Spend and Activity as seven narrow cards; a group with more than five cards, e.g. once click-through rate is loaded, switches to narrow cards); summary and next steps (the summary sentences of the First vs Second Half tab, a planner's notes box, definitions). The cards come from `data.half_cards`, the same list the dashboard's KPI Cards tab uses, so both show the same figures in the same order. Each card: the number now, a filled change pill (green better, red worse, grey within 2%), and the previous number with the absolute change.

Monthly output: `out/BPP_Awareness_YYYY-MM.pptx` (git-ignored: real client numbers). Without `--month` it uses the last full month.

Slides: 1 cover, 2 headline and three key figures, 3 paid awareness (5 KPIs + key takeaway), 4 awareness trend (4 charts, 12 months), 5 paid campaigns, 6 Facebook page, 7 TikTok, 8 what to look at next + planner's notes box + definitions.

Rules: the text is rule-based (no LLM); a person checks the numbers against Meta and TikTok and writes the why and what next (Playbook 3.1, 4.9), so the closing slide leaves a box for the planner. The default build is the client version (no data-quality check). The February and May 2026 exports are incomplete, so those months' figures are understated until the SSOT is re-exported.
Next step if wanted: fill a Google Slides template with `replaceAllText` placeholders, as in the PediaWell `report_deck.py` (`--slides`), once Sir Joven provides the template.
