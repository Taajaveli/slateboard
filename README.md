# Slateboard — live scores for your onn Google TV box (no ads)

## Get the APK (no Android Studio needed)
1. Create a new GitHub repo and upload everything in this folder (keep the `.github` folder).
2. Open the repo's **Actions** tab → **Build APK** runs automatically (~3 min).
3. Open the finished run → download **slateboard-apk** → unzip → `app-debug.apk`.

## Install on the onn box
1. Settings → System → About → click **Android TV OS build** 7 times (Developer mode on).
2. Settings → System → Developer options → turn on **USB debugging**.
3. Easiest: install the **Downloader** app (by AFTVnews), put the APK somewhere with a link
   (GitHub release, Google Drive direct link), open it in Downloader, install.
   Or from a computer on the same Wi-Fi: `adb connect <box-ip>:5555` then `adb install app-debug.apk`.
4. Slateboard appears in your apps row. Long-press → move it to Favorites.

## Remote
◀ ▶ switch league (from the top bar) or move between games · ▲ ▼ move · OK details · BACK close

Scores come from ESPN's public scoreboard feed (unofficial, free, no key). Refreshes every 20s when games are live.
Edit `app/src/main/assets/index.html` to change anything, push, and Actions rebuilds the APK.

## Picks tab (your TAAJAVEILI board on the TV)
1. Keep `picks.json` in the root of this repo. Edit it (or have your pipeline write it) each day.
2. One time: in `app/src/main/assets/index.html`, set
   `const PICKS_URL='https://raw.githubusercontent.com/<your-github-name>/<repo-name>/main/picks.json';`
   then push so Actions rebuilds the APK, and reinstall once.
   (The repo must be public for the raw link to work.)
3. After that, just update `picks.json` — the TV picks it up within ~5 minutes. No reinstall.

Format (see `picks.json`):
- `boards[]`: `league` (nfl, ncaaf, mlb, nba, wnba, nhl), `title`, `picks[]`
- each pick: `player`, `team`, `opp`, `market`, `line`, `odds`, `tier` (S/A/B/C), `score`, `why`,
  optional `stats` (any label → value pairs shown on the detail screen)
- `parlays[]`: `league`, `title`, `odds`, optional `note`, `legs[]` with `player`, `team`, `market`, `line`, `odds`
Use the same team abbreviations ESPN uses (KC, LAD, NYY…). ARI/AZ, WSH/WAS, CHW/CWS and similar are matched either way.
Each pick shows its game's live status and score automatically.

## Daily export from the pipeline
`export_picks.py` turns your board/parlay JSON into picks.json and pushes it with the GitHub CLI.
One-time: `gh auth login`. Then, as the last pipeline step:

    python3 export_picks.py --league mlb --board board.json:"HR Board":HR --board basehits.json:"Base Hits" \
        --parlays parlays.json --top 16 --push <github-name>/<repo>

    python3 export_picks.py --league nfl --board props.json:"Player Props" --parlays parlays.json --push <github-name>/<repo>

Running a second league the same day keeps the first league's boards. Use --dry-run to preview.
