import os, csv, json, io, re
import requests

TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL = os.environ["SLACK_CHANNEL_ID"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

FIELDNAMES = ["date", "headline", "url", "categories", "summary", "vibe", "in_top7", "source"]


def get_today_csv_block():
    """Find the most recent message containing a fenced ```csv block."""
    resp = requests.get(
        "https://slack.com/api/conversations.history",
        headers=HEADERS,
        params={"channel": CHANNEL, "limit": 5},
    ).json()
    for msg in resp.get("messages", []):
        text = msg.get("text", "")
        m = re.search(r"```csv\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            return m.group(1)
    return None


def load_items_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_items_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in FIELDNAMES})


def main():
    items = load_items_csv("data/items.csv")
    seen_urls = {row["url"] for row in items if row.get("url")}

    csv_text = get_today_csv_block()
    added = 0
    if csv_text:
        for row in csv.DictReader(io.StringIO(csv_text)):
            url = (row.get("url") or "").strip()
            if not url or url in seen_urls:
                continue  # dedup — safe to re-run this script any time
            items.append({k: (row.get(k) or "").strip() for k in FIELDNAMES})
            seen_urls.add(url)
            added += 1
        print(f"Added {added} new item(s). Total logged: {len(items)}.")
    else:
        print("No CSV block found in recent messages — skipping (gap will show in chart).")

    save_items_csv("data/items.csv", items)

    by_date = {}
    for row in items:
        d = row.get("date", "").strip()
        if not d:
            continue
        vibe = (row.get("vibe") or "").strip().lower()
        bucket = by_date.setdefault(d, {"green": 0, "yellow": 0, "red": 0})
        if vibe == "positive":
            bucket["green"] += 1
        elif vibe == "negative":
            bucket["red"] += 1
        else:
            bucket["yellow"] += 1

    summary = [
        {"date": d, **by_date[d], "total": sum(by_date[d].values())}
        for d in sorted(by_date.keys())
    ]

    os.makedirs("data", exist_ok=True)
    with open("data/daily_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"daily_summary.json rebuilt — {len(summary)} day(s) on file.")


if __name__ == "__main__":
    main()
