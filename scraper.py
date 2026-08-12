import json
import re
import urllib.request
from datetime import datetime

URL = "https://miragather.com/TOKEN2049SGSideEvents2026"
SUPABASE_URL = "https://vsvaqpsmrokvrbzwjfzv.supabase.co/rest/v1/events"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZzdmFxcHNtcm9rdnJiendqZnp2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODUyNDQ0MTMsImV4cCI6MjEwMDgyMDQxM30.BRlFMLivOdSgpxA_p6T85NnKZ7nFIqJgN9B06rbcEv0"

def parse_date_time(e):
    raw_start = e.get("start") or e.get("startDate")
    if not raw_start:
        return e.get("weekday", "TBD"), "ALL DAY"
    
    try:
        dt = datetime.fromisoformat(raw_start.replace('Z', '+00:00'))
        date_str = dt.strftime("%a, %d %b")
        time_str = "ALL DAY" if (dt.hour == 0 and dt.minute == 0) else dt.strftime("%I:%M %p")
        return date_str, time_str
    except Exception:
        return e.get("weekday", "TBD"), "ALL DAY"

def scrape_and_sync():
    print(f"Fetching {URL}...")
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read().decode('utf-8')

    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not match:
        print("Error: Could not find __NEXT_DATA__ block.")
        return

    data = json.loads(match.group(1))
    page_props = data.get("props", {}).get("pageProps", {})
    
    raw_list = (
        page_props.get("allFeaturedEvents", []) + 
        page_props.get("sideEvents", []) + 
        page_props.get("mainEvents", [])
    )

    # Fetch existing IDs from Supabase to prevent overwriting 'applied' or 'not_relevant' statuses
    existing_ids = set()
    try:
        req_get = urllib.request.Request(
            f"{SUPABASE_URL}?select=id",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        with urllib.request.urlopen(req_get) as response:
            existing_data = json.loads(response.read().decode('utf-8'))
            existing_ids = {str(item['id']) for item in existing_data}
    except Exception as err:
        print(f"Notice: Could not fetch existing records ({err}). Proceeding with upsert.")

    records = []
    seen = set()

    for item in raw_list:
        e = item.get("event") or item
        event_id = str(e.get("id") or item.get("id") or "")
        
        if not event_id or event_id in seen:
            continue
        seen.add(event_id)

        # Only insert new events as 'active'; preserve existing records
        if event_id not in existing_ids:
            date_str, time_str = parse_date_time(e)
            name = e.get("name") or e.get("event") or "Untitled Event"
            slug = e.get("slug")
            website = e.get("website") or (f"https://miragather.com/event/{slug}" if slug else "#")

            records.append({
                "id": event_id,
                "name": name,
                "start_date": date_str,
                "location": time_str,
                "website": website,
                "status": "active"
            })

    if not records:
        print("No new events found today.")
        return

    # Push new records to Supabase
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    req_push = urllib.request.Request(
        SUPABASE_URL, 
        data=json.dumps(records).encode('utf-8'), 
        headers=headers, 
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req_push) as response:
            print(f"Successfully added {len(records)} new events to Supabase!")
    except Exception as err:
        print(f"Failed to update Supabase: {err}")

if __name__ == "__main__":
    scrape_and_sync()
