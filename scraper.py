import os
import sys
import json
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# Force UTF-8 encoding for Windows standard output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Configuration
TARGET_VCNT_URL = "https://www.mdsuexam.org/vcnt.php"
TARGET_PANEL_URL = "https://www.mdsuexam.org/MdSmaINpanel.php"
TARGET_FORMACTION_URL = "https://www.mdsuexam.org/FormActIon.php"
TARGET_STUDENT_URL = "https://www.mdsuexam.org/StudentmaINpanel.php"
BASE_URL = "https://www.mdsuexam.org/"


# Load local .env file if it exists
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k.strip()] = v.strip()

STATE_FILE_PATH = os.getenv("STATE_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state.json"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def translate_to_hindi(text):
    """Translates the given English text to Hindi using the free Google Translate API."""
    if not text:
        return ""
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
        return text

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
        if response.status_code != 200:
            print(f"Telegram Markdown error ({response.status_code}): {response.text}. Retrying plain text...", file=sys.stderr)
            payload_plain = dict(payload)
            payload_plain.pop("parse_mode", None)
            response = requests.post(url, json=payload_plain, timeout=15)
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
        return {"seen_pdfs": [], "course_states": {}, "wp_states": {}, "last_check_timestamp": ""}
    
    try:
        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
            if "seen_pdfs" not in state:
                state["seen_pdfs"] = []
            if "course_states" not in state:
                state["course_states"] = {}
            if "wp_states" not in state:
                state["wp_states"] = {}
            return state
    except Exception as e:
        print(f"Warning: Could not read state file, starting fresh. Error: {e}", file=sys.stderr)
        return {"seen_pdfs": [], "course_states": {}, "wp_states": {}, "last_check_timestamp": ""}

def save_state(state):
    """Saves the current state back to state.json."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print(f"State saved to {STATE_FILE_PATH}.")
    except Exception as e:
        print(f"Error saving state file: {e}", file=sys.stderr)

def fetch_working_proxy():
    """Fetches a list of free HTTP proxies and returns the first one that successfully connects to the university portal."""
    print("Fetching free proxy list...")
    proxy_urls = [
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all"
    ]
    
    proxies_list = []
    for url in proxy_urls:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                proxies_list.extend(r.text.strip().split('\n'))
        except Exception:
            continue
            
    import random
    proxies_list = list(set([p.strip() for p in proxies_list if p.strip()]))
    random.shuffle(proxies_list)
    
    print(f"Loaded {len(proxies_list)} raw proxies. Testing for a working connection to bypass Cloudflare/firewall...")
    
    for proxy in proxies_list[:35]:
        proxy_dict = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }
        try:
            # We use a separate fresh session for testing proxy to prevent cookie issues
            test_session = requests.Session()
            test_session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.mdsuexam.org/"
            })
            # Disable verification for testing proxy
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            test_res = test_session.get("https://www.mdsuexam.org/vcnt.php", proxies=proxy_dict, timeout=6, verify=False)
            if test_res.status_code == 200 and "f1" in test_res.text:
                print(f"Found working proxy: {proxy}")
                return proxy_dict
        except Exception:
            continue
            
    print("Could not find any working free proxy.")
    return None

def fetch_panel_pages():
    """Performs the full POST redirection sequence to fetch MdSmaINpanel.php and StudentmaINpanel.php."""
    GOOGLE_SCRIPT_PROXY_URL = os.getenv("GOOGLE_SCRIPT_PROXY_URL")
    
    if GOOGLE_SCRIPT_PROXY_URL:
        print("Fetching MDSU panel pages through Google Apps Script Proxy...")
        try:
            r = requests.get(GOOGLE_SCRIPT_PROXY_URL, timeout=30)
            r.raise_for_status()
            data = r.json()
            if data.get("success"):
                return data["html_mdsma"], data["html_student"]
            else:
                print(f"Proxy returned error: {data.get('error')}. Falling back to direct connection...", file=sys.stderr)
        except Exception as e:
            print(f"Failed to fetch through Google Apps Script Proxy: {e}. Falling back to direct connection...", file=sys.stderr)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.mdsuexam.org/"
    })

    print("Step 1: Fetching vcnt.php...")
    try:
        r1 = session.get(TARGET_VCNT_URL, timeout=20)
        r1.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            print("Direct access blocked (403). Attempting to use a free proxy...")
            proxy = fetch_working_proxy()
            if proxy:
                session.proxies = proxy
                # Disable verification since free proxies often fail SSL validation
                session.verify = False
                # Retry with proxy
                r1 = session.get(TARGET_VCNT_URL, timeout=20)
                r1.raise_for_status()
            else:
                raise e
        else:
            raise e



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
    html_student = re.sub(r'</td>\s*<tr>\s*<tr', r'</td></tr><tr', html_student)

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

    rows = soup.find_all("tr", {"bgcolor": ["#BBD9F7", "#D9EAFB"]})
    print(f"Found {len(rows)} course rows in Student Panel.")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        raw_name = cols[0].get_text(strip=True)
        if ":" in raw_name:
            code, name = raw_name.split(":", 1)
            code = code.strip()
            name = name.strip()
        else:
            code = raw_name
            name = raw_name

        name = name.replace("(REVISED)", "").strip()

        time_table_a = cols[1].find("a", href=True)
        time_table_link = time_table_a["href"].strip() if time_table_a else ""

        admit_card_a = cols[2].find("a")
        has_admit_card = True if (admit_card_a and "Admit Card" in admit_card_a.get_text()) else False

        result_a = cols[4].find("a")
        has_result = True if (result_a and "Result" in result_a.get_text()) else False

        courses[code] = {
            "name": name,
            "time_table": time_table_link,
            "admit_card": has_admit_card,
            "result": has_result
        }

    return courses


def find_matching_wp_link(query):
    """Searches mdsuplus.com WordPress API to find a matching post/page URL for the given query."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Try searching posts
    try:
        url = f"https://mdsuplus.com/wp-json/wp/v2/posts?search={quote(query)}&per_page=1"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        posts = response.json()
        if posts and len(posts) > 0:
            return posts[0].get("link")
    except Exception as e:
        print(f"WP post search failed for '{query}': {e}", file=sys.stderr)

    # Try searching pages
    try:
        url = f"https://mdsuplus.com/wp-json/wp/v2/pages?search={quote(query)}&per_page=1"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        pages = response.json()
        if pages and len(pages) > 0:
            return pages[0].get("link")
    except Exception as e:
        print(f"WP page search failed for '{query}': {e}", file=sys.stderr)

    # Fallback default link if not found
    return "https://mdsuplus.com/"

def escape_md(text):
    """Escapes Markdown formatting characters in raw text."""
    if not text:
        return ""
    for ch in ['_', '*', '[', ']', '`']:
        text = text.replace(ch, f'\\{ch}')
    return text

def build_telegram_message(title, category, url=None):
    """Builds a formatted message exactly in the user's template."""
    title_hindi = translate_to_hindi(title)
    
    # Search for matching mdsuplus.com link instead of sending raw university URL
    wp_link = find_matching_wp_link(title)
    
    safe_title_hindi = escape_md(title_hindi)
    safe_title = escape_md(title)
    
    if category == "result":
        status_text = f"एमडीएसयू {safe_title_hindi} का रिजल्ट जारी कर दिया गया है।\n\n({safe_title})"
        direct_url = "https://www.mdsuexam.org/"
    elif category == "admit_card":
        status_text = f"एमडीएसयू {safe_title_hindi} का एडमिट कार्ड जारी कर दिया गया है।\n\n({safe_title})"
        direct_url = "https://www.mdsuexam.org/"
    elif category == "time_table":
        status_text = f"एमडीएसयू {safe_title_hindi} का टाइम टेबल जारी कर दिया गया है।\n\n({safe_title})"
        direct_url = url if url else "https://www.mdsuexam.org/"
    else:
        status_text = f"एमडीएसयू: {safe_title_hindi}\n\n({safe_title})"
        direct_url = url if url else "https://www.mdsuexam.org/"

    message = (
        "*MDSU Latest Update*\n\n"
        f"{status_text}\n\n"
        "👇👇👇👇👇👇👇👇\n\n"
        f"🔗 *Read Update:* {wp_link}\n"
        f"📥 *Direct Link:* {direct_url}\n\n"
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
    seen_pdfs_list = state.get("seen_pdfs", [])
    seen_pdfs_set = set(seen_pdfs_list)
    old_courses = state.get("course_states", {})

    # Fetch all data
    try:
        html_mdsma, html_student = fetch_panel_pages()
        notifications = parse_notifications(html_mdsma)
        current_courses = parse_student_courses(html_student)
    except Exception as e:
        print(f"Scraping MDSU failed: {e}", file=sys.stderr)
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
        if notif["id"] not in seen_pdfs_set:
            new_pdfs.append(notif)

    if os.getenv("TEST_SEND") == "true":
        print("Test run requested via environment variable. Adding a test notification...")
        new_pdfs.append({
            "id": "test_notif_id_123",
            "title": "vigypati no 230 dt 10-7-26 reg date extended for form filling of UG(NEP) sem 2,4 & 6 exam June, 2026",
            "url": "https://mdsuexam.org/PDF/P105154.pdf"
        })

    # Process Course-specific Updates
    new_alerts = []
    for code, curr in current_courses.items():
        old = old_courses.get(code)
        if old:
            if curr["result"] and not old.get("result"):
                new_alerts.append({"title": curr["name"], "category": "result"})
            if curr["admit_card"] and not old.get("admit_card"):
                new_alerts.append({"title": curr["name"], "category": "admit_card"})
            if curr["time_table"] and curr["time_table"] != old.get("time_table"):
                url = urljoin(BASE_URL, curr["time_table"])
                new_alerts.append({"title": curr["name"], "category": "time_table", "url": url})

    # Update states
    state["course_states"] = current_courses

    # If first run, save state and exit
    if is_first_run:
        state["seen_pdfs"] = [notif["id"] for notif in notifications]
        state["course_states"] = current_courses
        state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_state(state)
        print("State seeded successfully. No notifications sent.")
        return

    success_count = 0

    # 1. Send alerts for new general notifications
    new_pdfs.reverse()
    for notif in new_pdfs:
        message = build_telegram_message(notif["title"], "general", notif["url"])
        print(f"Sending general notification: {notif['title']}")
        if send_telegram_notification(message):
            if notif["id"] not in seen_pdfs_set:
                seen_pdfs_list.append(notif["id"])
                seen_pdfs_set.add(notif["id"])
            success_count += 1
        else:
            break

    # 2. Send alerts for new course updates (results/admit cards)
    for alert in new_alerts:
        message = build_telegram_message(alert["title"], alert["category"], alert.get("url"))
        print(f"Sending course update ({alert['category']}): {alert['title']}")
        if send_telegram_notification(message):
            success_count += 1
        else:
            break

    # Save state preserving last 300 seen PDFs
    state["seen_pdfs"] = seen_pdfs_list[-300:]
    state["last_check_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_state(state)
    print(f"Completed run. Successfully sent {success_count} notifications.")

if __name__ == "__main__":
    main()
