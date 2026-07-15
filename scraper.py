import os
import sys
import json
import datetime
import requests
from bs4 import BeautifulSoup

# Configuration - can be overridden via environment variables
TARGET_URL = os.getenv("TARGET_URL", "https://news.ycombinator.com/")
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
        response = requests.post(url, json=payload, timeout=10)
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
        return {"last_seen_id": "", "last_check_timestamp": ""}
    
    try:
        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not read state file, starting fresh. Error: {e}", file=sys.stderr)
        return {"last_seen_id": "", "last_check_timestamp": ""}

def save_state(state):
    """Saves the current state back to state.json."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print(f"State saved to {STATE_FILE_PATH}.")
    except Exception as e:
        print(f"Error saving state file: {e}", file=sys.stderr)

def fetch_and_parse():
    """Fetches the target webpage and extracts the latest update information."""
    print(f"Fetching website: {TARGET_URL} ...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    response = requests.get(TARGET_URL, headers=headers, timeout=15)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # =========================================================================
    # SCRAPING LOGIC (EDIT THIS SECTION FOR YOUR TARGET WEBSITE)
    # =========================================================================
    # By default, we scrape the top article on Hacker News (news.ycombinator.com)
    # as a template example.
    
    if "news.ycombinator.com" in TARGET_URL:
        # Find the first item link and title
        title_span = soup.select_one(".titleline > a")
        if not title_span:
            raise ValueError("Could not find the article element on Hacker News page.")
        
        title = title_span.get_text(strip=True)
        link = title_span.get("href")
        
        # Use link as the unique ID for this update
        unique_id = link
        
        # Formulate message
        message = (
            "🔔 *New Hacker News Top Story!*\n\n"
            f"📌 *Title:* {title}\n"
            f"🔗 [Read Article]({link})"
        )
        
        return unique_id, message
    
    else:
        # Generic fallback logic (e.g. tracking page title changes)
        title_element = soup.find("title")
        title_text = title_element.get_text(strip=True) if title_element else "No Title Found"
        
        # We can also check the body length or first H1
        h1_element = soup.find("h1")
        h1_text = h1_element.get_text(strip=True) if h1_element else ""
        
        unique_id = h1_text if h1_text else title_text
        
        message = (
            f"🔔 *Website Update Detected!*\n\n"
            f"🌐 *Site:* {TARGET_URL}\n"
            f"📝 *Main Heading:* {h1_text or 'N/A'}\n"
            f"📄 *Title:* {title_text}"
        )
        
        return unique_id, message
    # =========================================================================

def main():
    state = load_state()
    
    try:
        unique_id, message = fetch_and_parse()
    except Exception as e:
        print(f"Scraping failed: {e}", file=sys.stderr)
        sys.exit(1)
        
    last_seen_id = state.get("last_seen_id", "")
    
    print(f"Current Update ID: {unique_id}")
    print(f"Last Seen ID: {last_seen_id}")
    
    # Check if we have a new update
    if unique_id != last_seen_id:
        print("New update detected! Sending notification...")
        
        # Send Telegram message
        success = send_telegram_notification(message)
        
        if success:
            # Update state only if notification is sent successfully (or change this if you want to update anyway)
            state["last_seen_id"] = unique_id
            state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save_state(state)
        else:
            print("Failed to send notification. State not updated.", file=sys.stderr)
            sys.exit(1)
    else:
        print("No new updates. Website matches the last seen state.")
        # Update check timestamp even if no new update is detected
        state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_state(state)

if __name__ == "__main__":
    main()
