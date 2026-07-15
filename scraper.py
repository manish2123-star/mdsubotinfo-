import os
import sys
import json
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# Configuration
TARGET_VCNT_URL = "https://mdsuexam.org/vcnt.php"
TARGET_PANEL_URL = "https://mdsuexam.org/MdSmaINpanel.php"
TARGET_FORMACTION_URL = "https://mdsuexam.org/FormActIon.php"
TARGET_STUDENT_URL = "https://mdsuexam.org/StudentmaINpanel.php"
BASE_URL = "https://mdsuexam.org/"
STATE_FILE_PATH = os.getenv("STATE_FILE", "data/state.json")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def translate_to_hindi(text):
    """Translates the given English text to Hindi using the free Google Translate API."""
    if not text:
        return ""
    
    # Clean up input text
    text = " ".join(text.split())
    
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=hi&dt=t&q={quote(text)}"
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        data = response.json()
        translated_text = "".join([sentence[0] for sentence in data[0] if sentence[0]])
        return translated_text
    except Exception as e:
        print(f"Translation failed for '{text}': {e}", file=sys.stderr)
        return text # fallback to english if translation fails

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
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        return {"seen_pdfs": [], "course_states": {}, "last_check_timestamp": ""}
    
    try:
        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
            if "seen_pdfs" not in state:
                state["seen_pdfs"] = []
            if "course_states" not in state:
                state["course_states"] = {}
            return state
    except Exception as e:
        print(f"Warning: Could not read state file, starting fresh. Error: {e}", file=sys.stderr)
        return {"seen_pdfs": [], "course_states": {}, "last_check_timestamp": ""}

def save_state(state):
    """Saves the current state back to state.json."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print(f"State saved to {STATE_FILE_PATH}.")
    except Exception as e:
        print(f"Error saving state file: {e}", file=sys.stderr)

def fetch_panel_pages():
    """Performs the full POST redirection sequence to fetch MdSmaINpanel.php and StudentmaINpanel.php."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://mdsuexam.org/"
    })

    print("Step 1: Fetching vcnt.php...")
    r1 = session.get(TARGET_VCNT_URL, timeout=20)
    r1.raise_for_status()

    # Parse inputs from vcnt.php
    soup1 = BeautifulSoup(r1.text, "html.parser")
    form1 = soup1.find("form", {"name": "f1"})
    if not form1:
        raise ValueError("Could not find form f1 in vcnt.php response.")

    post_data1 = {}
    for inp in form1.find_all("input"):
        name = inp.get("name")
        val = inp.get("value", "")
        if name:
            post_data1[name] = val
    if "sbt" not in post_data1 and soup1.find("input", {"id": "sbt"}):
        post_data1["sbt"] = "Wait.."

    action1 = form1.get("action", "MdSmaINpanel.php")
    action_url1 = urljoin(BASE_URL, action1)

    print("Step 2: Accessing MdSmaINpanel.php...")
    r2 = session.post(action_url1, data=post_data1, timeout=20)
    r2.raise_for_status()
    if "Security Code does not matched" in r2.text:
        raise ValueError("Security verification failed at MdSmaINpanel.php.")

    html_mdsma = r2.text

    # Parse inputs from MdSmaINpanel.php to POST to FormActIon.php
    soup2 = BeautifulSoup(html_mdsma, "html.parser")
    form2 = soup2.find("form", {"name": "f1"})
    post_data2 = {}
    if form2:
        for inp in form2.find_all("input"):
            name = inp.get("name")
            val = inp.get("value", "")
            if name:
                post_data2[name] = val
    post_data2["flag"] = "1" # Access Student Panel

    print("Step 3: Redirecting through FormActIon.php...")
    r3 = session.post(TARGET_FORMACTION_URL, data=post_data2, timeout=20)
    r3.raise_for_status()
    html_formaction = r3.text

    # Parse inputs from FormActIon.php response to POST to StudentmaINpanel.php
    soup3 = BeautifulSoup(html_formaction, "html.parser")
    form3 = soup3.find("form", {"name": "f1"})
    post_data3 = {}
    if form3:
        for inp in form3.find_all("input"):
            name = inp.get("name")
            val = inp.get("value", "")
            if name:
                post_data3[name] = val
    else:
        # Fallback regex extraction of inputs
        for tag in soup3.find_all("input"):
            name = tag.get("name")
            val = tag.get("value", "")
            if name:
                post_data3[name] = val

    print("Step 4: Accessing StudentmaINpanel.php...")
    r4 = session.post(TARGET_STUDENT_URL, data=post_data3, timeout=20)
    r4.raise_for_status()
    if "Security Code does not matched" in r4.text:
        raise ValueError("Security verification failed at StudentmaINpanel.php.")

    html_student = r4.text

    # Clean up broken HTML developer markup where rows end with <tr> instead of </tr>
    import re
    html_student = re.sub(r'<tr>(\s*<tr)', r'</tr>\1', html_student)
    html_student = re.sub(r'</td>\s*<tr>\s*<tr', r'</td></tr>\1', html_student)

    return html_mdsma, html_student

def parse_notifications(html_mdsma):
    """Parses general notification PDF files from the main board."""
    soup = BeautifulSoup(html_mdsma, "html.parser")
    notifications = []
    
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if "PDF/" in href and href.lower().endswith(".pdf"):
            title = a.get_text(strip=True)
            if not title:
                title = a.parent.get_text(strip=True)
            
            title = " ".join(title.split())
            if not title:
                title = href.split("/")[-1]

            absolute_url = urljoin(BASE_URL, href)
            notifications.append({
                "id": href,
                "title": title,
                "url": absolute_url
            })
    return notifications

def parse_student_courses(html_student):
    """Parses the course updates table from the student panel page."""
    soup = BeautifulSoup(html_student, "html.parser")
    courses = {}

    # Find the main exam status table. It contains rows with bgcolor #BBD9F7 or #D9EAFB
    rows = soup.find_all("tr", {"bgcolor": ["#BBD9F7", "#D9EAFB"]})
    print(f"Found {len(rows)} course rows in Student Panel.")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        # Column 1: Course Name (e.g. "SMAT4: M.Sc. MATHEMATICS...")
        raw_name = cols[0].get_text(strip=True)
        if ":" in raw_name:
            code, name = raw_name.split(":", 1)
            code = code.strip()
            name = name.strip()
        else:
            code = raw_name
            name = raw_name

        # Clean course name (remove any trailing "(REVISED)", etc.)
        name = name.replace("(REVISED)", "").strip()

        # Column 2: Time Table Link
        time_table_a = cols[1].find("a", href=True)
        time_table_link = time_table_a["href"].strip() if time_table_a else ""

        # Column 3: Admit Card Link
        admit_card_a = cols[2].find("a")
        has_admit_card = True if (admit_card_a and "Admit Card" in admit_card_a.get_text()) else False

        # Column 5: Result Link
        result_a = cols[4].find("a")
        has_result = True if (result_a and "Result" in result_a.get_text()) else False

        courses[code] = {
            "name": name,
            "time_table": time_table_link,
            "admit_card": has_admit_card,
            "result": has_result
        }

    return courses

def build_telegram_message(title, category, url=None):
    """Builds a formatted message exactly in the user's template."""
    title_hindi = translate_to_hindi(title)
    
    if category == "result":
        status_text = f"एमडीएसयू {title_hindi} का रिजल्ट जारी कर दिया गया है।"
    elif category == "admit_card":
        status_text = f"एमडीएसयू {title_hindi} का एडमिट कार्ड जारी कर दिया गया है।"
    elif category == "time_table":
        status_text = f"एमडीएसयू {title_hindi} का टाइम टेबल जारी कर दिया गया है।"
    else:
        status_text = f"एमडीएसयू: {title_hindi}"

    link_text = ""
    if url:
        link_text = f"🔗 *Download Link:* {url}\n\n"

    message = (
        "*MDSU Latest Update*\n\n"
        f"{status_text}\n\n"
        "👇👇👇👇👇👇👇👇\n\n"
        f"{link_text}"
        "👉सबसे पहले लेटेस्ट अपडेट पाने के लिए हमारे व्हाट्सएप एवं टेलीग्राम चैनल को जरूर फॉलो करें 👈\n\n"
        "*👇👇👇Join Now👇👇👇*\n\n"
        "*Join Whatsapp Channel*\n\n"
        "https://whatsapp.com/channel/0029Vb87pC44Y9liEfVCsK1Q\n\n"
        "*Join Telegram Channel*\n\n"
        "https://t.me/mdsuplus1"
    )
    return message

def main():
    state = load_state()
    seen_pdfs = set(state.get("seen_pdfs", []))
    old_courses = state.get("course_states", {})

    try:
        html_mdsma, html_student = fetch_panel_pages()
        notifications = parse_notifications(html_mdsma)
        current_courses = parse_student_courses(html_student)
    except Exception as e:
        print(f"Scraping failed: {e}", file=sys.stderr)
        sys.exit(1)

    # -------------------------------------------------------------
    # Seeding Check (First Run Protection)
    # -------------------------------------------------------------
    is_first_run = False
    if not state.get("seen_pdfs") and not old_courses:
        is_first_run = True
        print("First run detected. Seeding state lists...")

    # Process General Notification PDFs
    new_pdfs = []
    for notif in notifications:
        if notif["id"] not in seen_pdfs:
            new_pdfs.append(notif)

    # Process Course-specific Updates (Results, Admit cards, Time tables)
    new_alerts = []
    for code, curr in current_courses.items():
        old = old_courses.get(code)
        
        if old:
            # Check for newly declared result
            if curr["result"] and not old.get("result"):
                new_alerts.append({"title": curr["name"], "category": "result"})
            # Check for newly released admit card
            if curr["admit_card"] and not old.get("admit_card"):
                new_alerts.append({"title": curr["name"], "category": "admit_card"})
            # Check for updated time table
            if curr["time_table"] and curr["time_table"] != old.get("time_table"):
                url = urljoin(BASE_URL, curr["time_table"])
                new_alerts.append({"title": curr["name"], "category": "time_table", "url": url})

    # Save current courses to state (always update state regardless of first run)
    state["course_states"] = current_courses

    # If first run, save state and exit without sending messages
    if is_first_run:
        state["seen_pdfs"] = [notif["id"] for notif in notifications]
        state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_state(state)
        print("State seeded successfully. No notifications sent.")
        return

    # Send alerts for new general notifications
    success_count = 0
    new_pdfs.reverse() # Notify oldest new updates first
    for notif in new_pdfs:
        message = build_telegram_message(notif["title"], "general", notif["url"])
        print(f"Sending general notification: {notif['title']}")
        if send_telegram_notification(message):
            seen_pdfs.add(notif["id"])
            success_count += 1
        else:
            break

    # Send alerts for new course updates (results/admit cards)
    for alert in new_alerts:
        message = build_telegram_message(alert["title"], alert["category"], alert.get("url"))
        print(f"Sending course update ({alert['category']}): {alert['title']}")
        if send_telegram_notification(message):
            success_count += 1
        else:
            break

    # Save state
    state["seen_pdfs"] = list(seen_pdfs)[-200:] # Keep last 200 PDFs
    state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_state(state)
    print(f"Completed run. Successfully sent {success_count} notifications.")

if __name__ == "__main__":
    main()
