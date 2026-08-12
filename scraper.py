import json
import re
import urllib.request
import urllib.error
from datetime import datetime
from playwright.sync_api import sync_playwright

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
    print(f"Opening browser for {URL}...")
    
    html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()

        # Abort images and fonts to load the page faster
        page.route("**/*.{png,jpg,jpeg,svg,woff,woff2}", lambda route: route.abort())

        # Load DOM
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        
        # Check for presence in DOM tree rather than visual visibility
        page.wait_for_selector("script#__NEXT_DATA__", state="attached", timeout=15000)
        
        html = page.content()
        browser.close()

    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not match:
        print("Error: Could not find __NEXT_DATA__ block in source HTML.")
        return

    data = json.loads(match.group(1))
    page_props = data.get("props", {}).get("pageProps", {})
    
    raw_list = (
        page_props.get("allFeaturedEvents", []) + 
        page_props.get("sideEvents", []) + 
        page_props.get("mainEvents", [])
    )

    # 1. Fetch existing IDs from Supabase
    existing_ids = set()
    try:
        req_get = urllib.request.Request(
            f"{SUPABASE_URL}?select=id",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        with urllib.request.urlopen(req_get) as response:
            existing_data = json.loads(response.read().decode('utf-8'))
            existing_ids = {str(item['id']) for item in existing_data}
            print(f"Found {len(existing_ids)} existing events in Supabase.")
    except Exception as err:
        print(f"Notice: Supabase read warning: {err}")

    # 2. Extract new records
    records = []
    seen = set()

    for item in raw_list:
        e = item.get("event") or item
        event_id = str(e.get("id") or item.get("id") or "")
        
        if not event_id or event_id in seen:
            continue
        seen.add(event_id)

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
        print("No new events found today. Supabase is up to date!")
        return

    print(f"Pushing {len(records)} new events to Supabase...")

    # 3. Post new records to Supabase
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
            print(f"Success! Inserted {len(records)} events into Supabase (HTTP {response.status}).")
    except urllib.error.HTTPError as err:
        print(f"Error posting to Supabase: HTTP {err.code} - {err.read().decode('utf-8')}")
        raise err

if __name__ == "__main__":
    scrape_and_sync()
