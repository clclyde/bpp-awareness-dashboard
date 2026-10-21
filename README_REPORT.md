# BPP brand awareness review deck

`report_deck.py` builds an 8-slide .pptx from the same numbers as the dashboard (`data.py`), in the Project Swarm look (white, navy block, yellow title word, red bar, Montserrat). Native editable charts and tables; opens in PowerPoint and Google Slides (File > Import slides). Install Montserrat for PowerPoint; Google Slides has it.

```bash
pip install -r requirements-report.txt
python report_deck.py --month 2026-09            # local snapshot (data/bpp_snapshot.json)
python report_deck.py --month 2026-09 --live     # Supabase, using .streamlit/secrets.toml or PULSE_DB_* variables
python report_deck.py --month 2026-09 --internal # adds the team-only data check (yellow months, note on the trend slide)
```
Output: `out/BPP_Awareness_YYYY-MM.pptx` (git-ignored: real client numbers). Without `--month` it uses the last full month.

Slides: 1 cover, 2 headline and three key figures, 3 paid awareness (5 KPIs + key takeaway), 4 awareness trend (4 charts, 12 months), 5 paid campaigns, 6 Facebook page, 7 TikTok, 8 what to look at next + planner's notes box + definitions.

Rules: the text is rule-based (no LLM); a person checks the numbers against Meta and TikTok and writes the why and what next (Playbook 3.1, 4.9), so the closing slide leaves a box for the planner. The default build is the client version (no data-quality check). The February and May 2026 exports are incomplete, so those months' figures are understated until the SSOT is re-exported.
Next step if wanted: fill a Google Slides template with `replaceAllText` placeholders, as in the PediaWell `report_deck.py` (`--slides`), once Sir Joven provides the template.
