"""Generate github-dashboard.svg from live GitHub data (run by GitHub Actions)."""
import os, sys, json, math, datetime, collections, urllib.request

USER = os.environ.get("GH_USER", "huubangdoan")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = os.environ.get("OUT", "github-dashboard.svg")

QUERY = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from,to:$to){
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar{ totalContributions
        weeks{ contributionDays{ date contributionCount contributionLevel weekday } } }
    }
    repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC){
      totalCount nodes{ primaryLanguage{ name } }
    }
  }
}"""
LEVELS = {"NONE":0,"FIRST_QUARTILE":1,"SECOND_QUARTILE":2,"THIRD_QUARTILE":3,"FOURTH_QUARTILE":4}

def fetch():
    if not TOKEN:
        sys.exit("GH_TOKEN is required")
    now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
    to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    from_time = (now - datetime.timedelta(days=364)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = json.dumps({"query": QUERY, "variables": {
        "login": USER,
        "from": from_time,
        "to": to}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", body,
        {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in data: sys.exit(str(data["errors"]))
    return data["data"]["user"]

STYLE = """<style>
.f,.c,.bv,.bh{animation:none!important;opacity:1!important;transform:none!important}
</style>"""

def render(u):
    cc = u["contributionsCollection"]; cal = cc["contributionCalendar"]
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    total = cal["totalContributions"]; commits = cc["totalCommitContributions"]; prs = cc["totalPullRequestContributions"]
    active = sum(1 for d in days if d["contributionCount"] > 0)
    best = cur = 0
    for d in days:
        cur = cur + 1 if d["contributionCount"] > 0 else 0; best = max(best, cur)
    first, last = days[0]["date"], days[-1]["date"]
    mon = collections.OrderedDict(); wk = [0]*7
    for d in days:
        dt = datetime.date.fromisoformat(d["date"]); c = d["contributionCount"]
        mon[(dt.year, dt.month)] = mon.get((dt.year, dt.month), 0) + c
        wk[dt.weekday()] += c
    langs = collections.Counter(n["primaryLanguage"]["name"] for n in u["repositories"]["nodes"] if n["primaryLanguage"])

    # Minimal-ink palette: white paper, black text, one blue
    INK, MUTE, BLUE, NAVY, GRID = "#111111", "#6b7280", "#2f6fe4", "#0b3d91", "#e5e7eb"
    LV = ["#eef1f6", "#c6dafc", "#7aa7f5", BLUE, NAVY]
    F = "font-family=\"-apple-system,'Segoe UI',Helvetica,Arial,sans-serif\""
    W, H = 1000, 660
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" {F}>', STYLE,
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    def t(x, y, s, size=12, fill=INK, w=400, a="start", d=0.0):
        o.append(f'<text class="f" style="animation-delay:{d:.2f}s" x="{x}" y="{y}" font-size="{size}" font-weight="{w}" fill="{fill}" text-anchor="{a}">{s}</text>')

    t(40, 52, "GitHub activity", 24, INK, 700, d=0.0)
    t(40, 74, f"{first} to {last}", 12, MUTE, d=0.1)
    stats = ([(f"{total:,}", "contributions"), (f"{commits:,}", "commits"), (str(prs), "pull requests"), (str(active), "active days")]
             if commits is not None else
             [(f"{total:,}", "contributions"), (str(active), "active days"), (str(best), "longest streak (days)"), (str(u["repositories"]["totalCount"]), "public repos")])
    for i, (n, l) in enumerate(stats):
        t(40 + i*235, 134, n, 36, INK, 700, d=0.15 + i*0.12); t(40 + i*235, 156, l, 12, MUTE, d=0.25 + i*0.12)

    # Calendar: cells pop in as a left-to-right sweep
    t(40, 206, "Contribution calendar", 14, INK, 700, d=0.5)
    cx0, cy0, cs, g = 76, 240, 14, 3; last_m = None
    for col, w in enumerate(weeks):
        for d in w["contributionDays"]:
            lv = LEVELS.get(d["contributionLevel"], 0) if isinstance(d["contributionLevel"], str) else d["contributionLevel"]
            o.append(f'<rect class="c" style="animation-delay:{0.6 + col*0.018:.3f}s" x="{cx0+col*(cs+g)}" y="{cy0+d["weekday"]*(cs+g)}" width="{cs}" height="{cs}" fill="{LV[lv]}"><title>{d["contributionCount"]} on {d["date"]}</title></rect>')
        dt = datetime.date.fromisoformat(w["contributionDays"][0]["date"])
        if dt.month != last_m and dt.day <= 21:
            t(cx0 + col*(cs+g), cy0 - 8, dt.strftime("%b"), 11, MUTE, d=0.6 + col*0.018); last_m = dt.month
    for r, n in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        t(40, cy0 + r*(cs+g) + 11, n, 11, MUTE, d=0.6)
    yb = cy0 + 7*(cs+g)
    t(cx0, yb + 20, f"{active} days with a contribution", 11, MUTE, d=1.6)
    t(790, yb + 20, "Less", 11, MUTE, 400, "end", d=1.6)
    for i in range(5): o.append(f'<rect class="f" style="animation-delay:1.6s" x="{798+i*17}" y="{yb+9}" width="{cs}" height="{cs}" fill="{LV[i]}"/>')
    t(890, yb + 20, "More", 11, MUTE, d=1.6)

    # Three small multiples, no boxes: bars grow from the baseline
    py = 430; pw = 270; xs = [40, 365, 690]; base = 590; hmax = 100
    for x, (ti, su) in zip(xs, [("Monthly rhythm", "contributions per month"), ("Language mix", "primary language, public repos"), ("Weekday pulse", "contributions by day of week")]):
        t(x, py, ti, 14, INK, 700, d=1.5); t(x, py + 17, su, 11, MUTE, d=1.6)
    def bars(x, vals, labels, color_fn, d0):
        n = len(vals); slot = pw / n; bw = slot * 0.62; mx = max(vals) or 1
        o.append(f'<line class="f" style="animation-delay:{d0:.2f}s" x1="{x}" y1="{base}" x2="{x+pw}" y2="{base}" stroke="{GRID}"/>')
        for i, v in enumerate(vals):
            h = v / mx * hmax; bx = x + i*slot + (slot - bw)/2; dl = d0 + i*0.06
            if v: o.append(f'<rect class="bv" style="animation-delay:{dl:.2f}s" x="{bx:.1f}" y="{base-h:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{color_fn(i, v)}"/>')
            t(f"{bx+bw/2:.1f}", f"{base-h-5:.1f}", v, 10, MUTE if v != mx else INK, 400 if v != mx else 700, "middle", d=dl + 0.5)
            t(f"{bx+bw/2:.1f}", base + 15, labels[i], 10, MUTE, 400, "middle", d=d0)
    mv = list(mon.values()); mm = max(mv)
    bars(xs[0], mv, [datetime.date(k[0], k[1], 1).strftime("%b")[0] for k in mon], lambda i, v: NAVY if v == mm else BLUE, 1.7)
    wm = max(wk)
    bars(xs[2], wk, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], lambda i, v: NAVY if v == wm else BLUE, 1.9)
    # Language: horizontal bars grow left to right (no donut)
    top = langs.most_common(6); lm = top[0][1] if top else 1
    for i, (lg, c) in enumerate(top):
        y = 478 + i*20; dl = 1.8 + i*0.1
        t(xs[1], y + 10, lg, 12, INK, d=dl)
        o.append(f'<rect class="bh" style="animation-delay:{dl:.2f}s" x="{xs[1]+115}" y="{y}" width="{c/lm*120:.1f}" height="12" fill="{NAVY if c == lm else BLUE}"/>')
        t(xs[1] + 115 + c/lm*120 + 6, y + 10, c, 11, MUTE, d=dl + 0.6)
    o.append("</svg>")
    return "\n".join(o)

if __name__ == "__main__":
    user = json.load(open(sys.argv[1]))["data"]["user"] if len(sys.argv) > 1 else fetch()
    open(OUT, "w", encoding="utf-8").write(render(user))
    print("wrote", OUT)