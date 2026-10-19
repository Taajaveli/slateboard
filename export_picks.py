#!/usr/bin/env python3
"""
export_picks.py — turn TAAJAVEILI pipeline output into picks.json for Slateboard, and push it to GitHub.

Drop this next to your pipeline files and run it as the last step, after build_html.py:

    python3 export_picks.py --league mlb \
        --board board.json:"HR Board":hr \
        --board basehits.json:"Base Hits" \
        --parlays parlays.json \
        --top 16 \
        --push <github-name>/<repo>

  --board FILE[:TITLE[:MARKET]]  one per board. MARKET fills in when rows have no market field (e.g. "hr").
  --parlays FILE                 optional parlays file.
  --league                       nfl, ncaaf, mlb, nba, wnba or nhl. Use --board-league to mix leagues in one run.
  --push OWNER/REPO              uploads picks.json to that repo's main branch with the GitHub CLI (gh).
  --dry-run                      print the result instead of writing/pushing.

The script accepts the field names the pipeline has used across versions (name/player, hr_odds/odds,
taaj/score/total, tier, why, ...) so it keeps working when a build renames a column.
"""
import argparse, base64, datetime as dt, json, subprocess, sys

# First matching key wins. Add your own names here if a build uses something new.
KEYS = {
    "player": ["player", "name", "batter", "player_name", "athlete"],
    "team":   ["team", "tm", "batter_team", "player_team"],
    "opp":    ["opp", "opponent", "vs", "p_team", "pitcher_team", "opp_team"],
    "market": ["market", "prop", "stat", "prop_type", "type"],
    "line":   ["line", "prop_line", "ou", "threshold"],
    "odds":   ["odds", "hr_odds", "price", "american", "best_odds", "over_odds"],
    "tier":   ["tier", "grade", "rank_tier"],
    "score":  ["score", "taaj", "total", "taaj_score", "composite", "pts", "rating"],
    "why":    ["why", "why_line", "reason", "note", "blurb"],
}
# Extra numbers shown on the TV detail screen when present: source key -> label
STATS = {
    "pitcher": "Pitcher", "p_name": "Pitcher", "opp_pitcher": "Pitcher",
    "barrel": "Barrel%", "barrel_pct": "Barrel%", "hh": "Hard-Hit%", "hardhit": "Hard-Hit%",
    "zone": "Zone", "zonescore": "Zone", "xwoba": "xwOBA", "bat_speed": "Bat speed",
    "p_hr9": "Pitcher HR/9", "park": "Park", "l20": "L20", "l10": "L10", "season_hr": "Season hit rate",
    "hit_rate": "Hit rate", "pf_rating": "PF Rating", "dvp": "DVP rank", "implied_total": "Implied total",
}
LEG_KEYS = ["legs", "picks", "bets", "selections"]
PARLAY_TITLE = ["title", "name", "label", "ticket"]
PARLAY_ODDS = ["odds", "combined_odds", "price", "payout", "american"]
PARLAY_NOTE = ["note", "why", "summary", "desc", "description"]


def first(row, keys):
    for k in keys:
        for rk in (k, k.upper(), k.title()):
            if rk in row and row[rk] not in (None, ""):
                return row[rk]
    return None


def fmt(v):
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") if abs(v) < 1 else f"{v:.1f}".rstrip("0").rstrip(".")
    return v


def rows_of(data):
    """Find the list of row dicts inside whatever shape the file has."""
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for k in ("board", "rows", "picks", "players", "data", "items"):
            if isinstance(data.get(k), list):
                return rows_of(data[k])
        lists = [v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if len(lists) == 1:
            return lists[0]
    return []


def odds_str(v):
    if v is None:
        return ""
    s = str(v).lstrip("'").strip()
    try:
        n = int(float(s))
        return f"+{n}" if n > 0 else str(n)
    except ValueError:
        return s


def to_pick(row, default_market):
    p = {k: first(row, keys) for k, keys in KEYS.items()}
    p["market"] = p["market"] or default_market or ""
    p["odds"] = odds_str(p["odds"])
    if p["team"]:
        p["team"] = str(p["team"]).upper()
    if p["opp"]:
        p["opp"] = str(p["opp"]).upper()
    if p["score"] is not None:
        try:
            p["score"] = round(float(p["score"]), 1)
        except (TypeError, ValueError):
            pass
    stats = {}
    for k, label in STATS.items():
        if k in row and row[k] not in (None, "") and label not in stats:
            stats[label] = fmt(row[k])
    if stats:
        p["stats"] = stats
    return {k: v for k, v in p.items() if v not in (None, "")}


def load(path):
    with open(path) as f:
        return json.load(f)


def parlays_of(data, league):
    if isinstance(data, dict):
        data = next((v for k, v in data.items() if isinstance(v, list)), []) if not any(k in data for k in LEG_KEYS) else [data]
    out = []
    for t in data or []:
        if not isinstance(t, dict):
            continue
        legs = first(t, LEG_KEYS) or []
        legs = [to_pick(l, "") for l in legs if isinstance(l, dict)]
        legs = [{k: l[k] for k in ("player", "team", "market", "line", "odds") if k in l} for l in legs]
        if not legs:
            continue
        item = {"league": t.get("league", league), "title": str(first(t, PARLAY_TITLE) or f"{len(legs)}-leg parlay"),
                "odds": odds_str(first(t, PARLAY_ODDS)), "legs": legs}
        note = first(t, PARLAY_NOTE)
        if note:
            item["note"] = str(note)
        out.append(item)
    return out


def push(repo, content, branch="main"):
    path = "picks.json"
    sha = None
    r = subprocess.run(["gh", "api", f"repos/{repo}/contents/{path}?ref={branch}", "--jq", ".sha"],
                       capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        sha = r.stdout.strip()
    body = {"message": f"picks {dt.date.today().isoformat()}", "branch": branch,
            "content": base64.b64encode(content.encode()).decode()}
    if sha:
        body["sha"] = sha
    r = subprocess.run(["gh", "api", "-X", "PUT", f"repos/{repo}/contents/{path}", "--input", "-"],
                       input=json.dumps(body), capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Push failed: {r.stderr.strip() or r.stdout.strip()}\n"
                 f"Check that `gh auth status` is logged in and you can write to {repo}.")
    print(f"Pushed picks.json to {repo} ({branch}). The TV updates within ~5 minutes.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--league", default="mlb")
    ap.add_argument("--board", action="append", default=[], help="FILE[:TITLE[:MARKET]]")
    ap.add_argument("--board-league", action="append", default=[], help="league for each --board, in order")
    ap.add_argument("--parlays", action="append", default=[])
    ap.add_argument("--top", type=int, default=0, help="keep only the first N rows of each board")
    ap.add_argument("--title", default="TAAJAVEILI")
    ap.add_argument("--merge", help="existing picks.json to merge into (keeps other leagues' boards)")
    ap.add_argument("--out", default="picks.json")
    ap.add_argument("--push", metavar="OWNER/REPO")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.board and not a.parlays:
        ap.error("give at least one --board or --parlays")

    now = dt.datetime.now()
    out = {"title": a.title, "date": now.strftime("%a %b %-d"), "updated": now.strftime("%-I:%M %p"),
           "boards": [], "parlays": []}

    for i, spec in enumerate(a.board):
        parts = spec.split(":", 2)
        path, title, market = parts[0], (parts[1] if len(parts) > 1 else ""), (parts[2] if len(parts) > 2 else "")
        league = (a.board_league[i] if i < len(a.board_league) else a.league).lower()
        rows = rows_of(load(path))
        if a.top:
            rows = rows[:a.top]
        picks = [p for p in (to_pick(r, market) for r in rows) if p.get("player")]
        if not picks:
            print(f"warning: no rows with a player name found in {path}", file=sys.stderr)
        out["boards"].append({"league": league, "title": title or path.rsplit("/", 1)[-1].split(".")[0], "picks": picks})
    for path in a.parlays:
        out["parlays"] += parlays_of(load(path), a.league.lower())

    # Running MLB and NFL separately on the same day? Today's boards from other leagues are kept automatically.
    merge_path = a.merge or a.out
    if merge_path:
        try:
            old = load(merge_path)
            if not a.merge and old.get("date") != out["date"]:
                raise FileNotFoundError  # yesterday's file: start fresh
            mine = {b["league"] for b in out["boards"]} | {p["league"] for p in out["parlays"]}
            out["boards"] = [b for b in old.get("boards", []) if b.get("league") not in mine] + out["boards"]
            out["parlays"] = [p for p in old.get("parlays", []) if p.get("league") not in mine] + out["parlays"]
        except FileNotFoundError:
            pass

    text = json.dumps(out, indent=1, ensure_ascii=False)
    n = sum(len(b["picks"]) for b in out["boards"])
    if a.dry_run:
        print(text)
        return
    with open(a.out, "w") as f:
        f.write(text)
    print(f"Wrote {a.out}: {n} picks on {len(out['boards'])} boards, {len(out['parlays'])} parlays.")
    if a.push:
        push(a.push, text, a.branch)


if __name__ == "__main__":
    main()
