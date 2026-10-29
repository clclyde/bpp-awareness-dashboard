# Deploying the BPP dashboard (Streamlit Community Cloud)

The app reads Supabase only, with the read-only `pulse_reader_bpp` login that can see BPP rows and nothing else. No client data is stored in this repository.

## 1. Supabase (once). The SQL files live in the parent project's git-ignored `supabase/` folder
Run these in the Supabase SQL Editor, in this order:
1. `20_social_tables.sql`: creates `social_ads_monthly`, `fb_posts`, `tiktok_videos`, `fb_page_metrics` (generic, with `account_code`). An install that already ran an older version of this file gets `fb_page_metrics` and its read access from `22_seed_bpp.sql`.
2. `21_bpp_reader_role.sql.template`: first generate a password in a normal Terminal (`openssl rand -hex 16`, never in a chat), replace `<PASSWORD>` in the one marked place, run, then close the tab and delete that entry from the query history. Every row of the check table at the end must be `true`.
3. `22_seed_bpp.sql`: loads the BPP data (229 ad rows, 153 Facebook posts, 87 TikTok videos). It ends with a count table.

## 2. Streamlit Community Cloud
1. share.streamlit.io, Create app, repo `clclyde/bpp-awareness-dashboard`, branch `main`, main file `app.py`. This is a separate app from the PediaWell dashboard.
2. Advanced settings: Python **3.12**. In **Secrets** paste the `[supabase]` block from `.streamlit/secrets.toml.example` with the real project ref and the `pulse_reader_bpp` password (session pooler host).
3. Deploy. The sidebar should say "Source: Supabase (live)".
4. Share (app menu): private, only specific people, add the team's emails.

## Updating
- Code: push to `main` of this repo; the app redeploys. Data refreshes from Supabase every 5 minutes.
- Data: today the BPP tables are a one-off seed from a snapshot of the BPP Content SSOT (dated in the seed file). To refresh, rebuild the snapshot and re-run `22_seed_bpp.sql` (it replaces the BPP rows). Meta ads no longer need that: the n8n workflow `pulse32_meta_ads` loads them weekly from the Marketing API (run `28_bpp_reader_api_grants.sql` once so the read-only login can read those tables; until then the app uses the seed). Facebook posts, TikTok and page metrics are still the seed.

## Errors
"The dashboard could not load its data": the Secrets are missing or wrong (host, user `pulse_reader_bpp.<project-ref>`, password) or Supabase is unreachable. Rotate the password if it was ever pasted outside the Secrets box.

## Access password (while the app is public)
Streamlit Community Cloud allows one private app, so this app is public. To keep casual visitors out, add one line to the app's **Secrets**, above the `[supabase]` block: `app_password = "<shared password>"`. The app then shows a password box first and loads no data until it is right. Change it by editing the Secrets (visitors already inside stay in until their session ends). It is a shared secret with no lockout and no per-person logins, so treat it as a door latch, not security; the real fix is the razzaconsulting.com-only hosting. Never put the password in the repo or in chat.
