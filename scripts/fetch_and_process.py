import os, csv, json, io
import requests

API_KEY = os.environ["GDRIVE_API_KEY"]
FOLDER_ID = os.environ["GDRIVE_FOLDER_ID"]
DRIVE_API = "https://www.googleapis.com/drive/v3"

FIELDNAMES = ["date", "headline", "url", "categories", "summary", "vibe", "in_top7", "source"]


def list_csv_files():
    """List every CSV Cowork has dropped in the shared Drive folder."""
    params = {
        "q": f"'{FOLDER_ID}' in parents and mimeType='text/csv' and trashed=false",
        "fields": "files(id,name,modifiedTime)",
        "key": API_KEY,
        "pageSize": 1000,
    }
    r = requests.get(f"{DRIVE_API}/files", params=params)
    r.raise_for_status()
    return r.json().get("files", [])


def download_file(file_id):
    r = requests.get(f"{DRIVE_API}/files/{file_id}", params={"alt": "media", "key": API_KEY})
    r.raise_for_status()
    return r.text


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

    files = list_csv_files()
    print(f"Found {len(files)} CSV file(s) in Drive folder.")

    added = 0
    for f in files:
        try:
            content = download_file(f["id"])
        except Exception as e:
            print(f"  skip {f['name']}: {e}")
            continue
        for row in csv.DictReader(io.StringIO(content)):
            url = (row.get("url") or "").strip()
            if not url or url in seen_urls:
                continue  # dedup — safe to re-run this script any time
            items.append({k: (row.get(k) or "").strip() for k in FIELDNAMES})
            seen_urls.add(url)
            added += 1

    print(f"Added {added} new item(s). Total logged: {len(items)}.")
    save_items_csv("data/items.csv", items)

    # ---- rebuild the aggregate the frontend reads — unaffected by CSV vs JSON upstream ----
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
            bucket["yellow"] += 1  # "neutral" or anything unexpected defaults here

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
