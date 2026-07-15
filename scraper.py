import os
import sys
import json
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configuration
TARGET_VCNT_URL = "https://mdsuexam.org/vcnt.php"
TARGET_PANEL_URL = "https://mdsuexam.org/MdSmaINpanel.php"
BASE_URL = "https://mdsuexam.org/"
STATE_FILE_PATH = os.getenv("STATE_FILE", "data/state.json")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_notification(message):
    """Sends a markdown-formatted message to the specified Telegram chat/group."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables are not set.", file=sys.stderr)
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        print("Telegram notification sent successfully.")
        return True
    except Exception as e:
        print(f"Failed to send Telegram message: {e}", file=sys.stderr)
        return False

def load_state():
    """Loads the previous run state from state.json."""
    if not os.path.exists(STATE_FILE_PATH):
        # Create directories if they do not exist
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        return {"seen_pdfs": [], "last_check_timestamp": ""}
    
    try:
        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
            # Ensure seen_pdfs exists in state
            if "seen_pdfs" not in state:
                state["seen_pdfs"] = []
            return state
    except Exception as e:
        print(f"Warning: Could not read state file, starting fresh. Error: {e}", file=sys.stderr)
        return {"seen_pdfs": [], "last_check_timestamp": ""}

def save_state(state):
    """Saves the current state back to state.json."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print(f"State saved to {STATE_FILE_PATH}.")
    except Exception as e:
        print(f"Error saving state file: {e}", file=sys.stderr)

def fetch_and_parse_mdsu():
    """Simulates the MDSU redirection sequence and scrapes the latest notifications."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://mdsuexam.org/"
    })

    print("Step 1: Fetching vcnt.php to obtain security variables...")
    r1 = session.get(TARGET_VCNT_URL, timeout=20)
    r1.raise_for_status()

    # Parse form values from vcnt.php
    soup1 = BeautifulSoup(r1.text, "html.parser")
    form = soup1.find("form", {"name": "f1"})
    if not form:
        raise ValueError("Could not find submission form in vcnt.php response.")

    post_data = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        val = inp.get("value", "")
        if name:
            post_data[name] = val

    # Add submit button value if it exists
    if "sbt" not in post_data and soup1.find("input", {"id": "sbt"}):
        post_data["sbt"] = "Wait.."

    action = form.get("action", "MdSmaINpanel.php")
    action_url = urljoin(BASE_URL, action)

    print("Step 2: Submitting POST request to access MdSmaINpanel.php...")
    r2 = session.post(action_url, data=post_data, timeout=20)
    r2.raise_for_status()

    if "Security Code does not matched" in r2.text:
        raise ValueError("MDSU security code verification failed. The website might have changed its mechanism.")

    print("Step 3: Parsing MDSU Exam Panel page content...")
    soup2 = BeautifulSoup(r2.text, "html.parser")
    
    # Extract all links that contain 'PDF/' in their href
    notifications = []
    
    # Target all anchor tags containing pdf links
    for a in soup2.find_all("a", href=True):
        href = a["href"].strip()
        if "PDF/" in href and href.lower().endswith(".pdf"):
            # Extract clean title text
            title = a.get_text(strip=True)
            if not title:
                # Fallback to parent elements if text is empty
                title = a.parent.get_text(strip=True)
            
            # Clean up title
            title = " ".join(title.split())
            if not title:
                title = href.split("/")[-1]

            absolute_url = urljoin(BASE_URL, href)
            notifications.append({
                "id": href, # We use the relative PDF link as a unique ID
                "title": title,
                "url": absolute_url
            })

    print(f"Successfully parsed {len(notifications)} notifications.")
    return notifications

def main():
    state = load_state()
    seen_pdfs = set(state.get("seen_pdfs", []))
    
    try:
        notifications = fetch_and_parse_mdsu()
    except Exception as e:
        print(f"Scraping failed: {e}", file=sys.stderr)
        sys.exit(1)
        
    if not notifications:
        print("No notifications found on the webpage.")
        state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_state(state)
        return

    # If first run (no historical seen PDFs), seed the state and exit without sending notifications
    if not state.get("seen_pdfs"):
        print("First run detected. Seeding state with existing notifications...")
        state["seen_pdfs"] = [notif["id"] for notif in notifications]
        state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_state(state)
        print(f"Seeded state with {len(notifications)} notifications. No alerts sent.")
        return

    # Check for new notifications
    new_notifications = []
    for notif in notifications:
        if notif["id"] not in seen_pdfs:
            new_notifications.append(notif)

    print(f"Found {len(new_notifications)} new notifications.")
    
    if new_notifications:
        # Sort or process in chronological order (optional, here we process as they are ordered)
        # Note: In HTML, the latest notifications are usually at the top, so we reverse it to notify old ones first.
        new_notifications.reverse()
        
        success_count = 0
        for notif in new_notifications:
            message = (
                "🔔 *MDSU Exam Update!*\n\n"
                f"📝 *Title:* {notif['title']}\n\n"
                f"🔗 [Download PDF]({notif['url']})"
            )
            
            print(f"Sending alert for: {notif['title']}")
            if send_telegram_notification(message):
                seen_pdfs.add(notif["id"])
                success_count += 1
            else:
                print(f"Failed to send notification for: {notif['id']}")
                break # Stop processing to avoid losing sync if API is down
        
        # Save updated seen list (limit to last 200 items to avoid infinite size growth)
        updated_seen_list = list(seen_pdfs)[-200:]
        state["seen_pdfs"] = updated_seen_list
        state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_state(state)
        print(f"Completed run. Successfully notified {success_count} updates.")
    else:
        print("No new updates. All notifications match the last seen state.")
        state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_state(state)

if __name__ == "__main__":
    main()
