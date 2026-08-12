import json
import hashlib
from datetime import datetime
from playwright.sync_api import sync_playwright

URL = "https://miragather.com/TOKEN2049SGSideEvents2026"
DATA_FILE = "events.json"

def load_events():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_events(events):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

def generate_id(title, date_str):
    raw = f"{title.strip().lower()}_{date_str.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()

def scrape():
    existing_events = load_events()
    existing_ids = {e["id"] for e in existing_events}
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    new_count = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        rows = page.query_selector_all("table tr, div[class*='event']")
        
        for row in rows:
            text = row.inner_text().strip()
            if not text:
                continue
            
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if len(lines) < 2:
                continue
            
            title = lines[2] if len(lines) > 2 else lines[0]
            event_date = lines[0]
            
            link_elem = row.query_selector("a")
            link = link_elem.get_attribute("href") if link_elem else ""

            event_id = generate_id(title, event_date)

            # Add only if this exact event doesn't exist yet
            if event_id not in existing_ids:
                existing_events.append({
                    "id": event_id,
                    "title": title,
                    "date": event_date,
                    "raw_text": text,
                    "link": link,
                    "added_date": today_str
                })
                existing_ids.add(event_id)
                new_count += 1

        browser.close()

    save_events(existing_events)
    print(f"Scrape complete for {today_str}. Added {new_count} new events.")

if __name__ == "__main__":
    scrape()
