#!/usr/bin/env python3
"""Downloads the contribution calendar and the pull requests into tools/profile/data/.

The calendar is read from the public profile page, so it matches the graph shown on
GitHub (private contributions included when the profile shares them). If that page
ever changes shape, it falls back to the GraphQL API, which needs GITHUB_TOKEN.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
USER = json.loads((HERE / "config.json").read_text())["user"]
TOKEN = os.environ.get("GITHUB_TOKEN")

GRAPHQL = """query($login: String!) { user(login: $login) { contributionsCollection {
  contributionCalendar { weeks { contributionDays { date contributionCount } } } } } }"""


def get(url, body=None, token=TOKEN):
    headers = {"User-Agent": f"{USER}-profile", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode()


def calendar_from_page():
    page = get(f"https://github.com/users/{USER}/contributions", token=None)
    dates = {cid: date for date, cid in re.findall(
        r'data-date="([0-9-]+)" id="(contribution-day-component-[\d-]+)"', page)}
    days = {}
    for cid, tip in re.findall(r'<tool-tip[^>]*for="(contribution-day-component-[\d-]+)"[^>]*>([^<]*)</tool-tip>', page):
        m = re.match(r"(\d+) contribution", tip)
        days[dates[cid]] = int(m.group(1)) if m else 0
    return days


def calendar_from_api():
    body = json.dumps({"query": GRAPHQL, "variables": {"login": USER}}).encode()
    res = json.loads(get("https://api.github.com/graphql", body))
    if "errors" in res:
        raise SystemExit(f"GraphQL: {res['errors']}")
    weeks = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def calendar():
    try:
        days = calendar_from_page()
        if len(days) >= 300:
            return days
        print(f"Profile page gave only {len(days)} days, trying the API.")
    except Exception as exc:  # noqa: BLE001 - any failure here means "use the API"
        print(f"Profile page failed ({exc}), trying the API.")
    if not TOKEN:
        raise SystemExit("Could not read the calendar and there is no GITHUB_TOKEN for the API.")
    return calendar_from_api()


def pulls():
    q = urllib.parse.quote(f"author:{USER} type:pr is:public")
    res = json.loads(get(f"https://api.github.com/search/issues?q={q}&sort=created&order=desc&per_page=100"))
    return [{
        "title": i["title"],
        "url": i["html_url"],
        "repo": i["repository_url"].split("/repos/")[1],
        "created": i["created_at"][:10],
        "state": i["state"],
        "merged": bool(i["pull_request"].get("merged_at")),
    } for i in res["items"]]


def main():
    DATA.mkdir(exist_ok=True)
    days = dict(sorted(calendar().items()))
    prs = pulls()
    (DATA / "calendar.json").write_text(json.dumps(days, indent=0) + "\n")
    (DATA / "pulls.json").write_text(json.dumps(prs, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(days)} days, {sum(days.values())} contributions, {len(prs)} pull requests")


if __name__ == "__main__":
    main()
