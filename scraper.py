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
        
        print(f"Opening {URL}...")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        # Select individual event containers/rows
        cards = page.query_selector_all("tr, div[class*='event'], div[class*='row']")
        print(f"Processing {len(cards)} elements...")

        for card in cards:
            try:
                text = card.inner_text().strip()
                if not text:
                    continue
                
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                
                # Filter out system numbers, button text, or tiny lines
                filtered_lines = [
                    l for l in lines 
                    if l not in ["Interested", "Going", "Add to calendar", "Link to website", "Open in a new tab"] 
                    and not l.startswith("+") 
                    and not l.isdigit()
                ]

                if len(filtered_lines) < 2:
                    continue

                # Parse layout fields
                event_date = filtered_lines[0]
                event_time = "ALL DAY"
                
                # Check if second line is a time indicator
                start_idx = 1
                if any(k in filtered_lines[1].upper() for k in ["AM", "PM", "ALL DAY"]):
                    event_time = filtered_lines[1]
                    start_idx = 2

                if len(filtered_lines) <= start_idx:
                    continue

                title = filtered_lines[start_idx]
                host = filtered_lines[start_idx + 1] if len(filtered_lines) > (start_idx + 1) else ""

                # Extract hyperlink
                link_elem = card.query_selector("a[href*='http']")
                link = link_elem.get_attribute("href") if link_elem else ""

                event_id = generate_id(title, event_date)

                if event_id not in existing_ids:
                    existing_events.append({
                        "id": event_id,
                        "event_date": event_date,
                        "event_time": event_time,
                        "title": title,
                        "host": host,
                        "link": link,
                        "added_date": today_str
                    })
                    existing_ids.add(event_id)
                    new_count += 1
            except Exception as e:
                continue

        browser.close()

    save_events(existing_events)
    print(f"Scrape complete for {today_str}. Added {new_count} new events.")

if __name__ == "__main__":
    scrape()
