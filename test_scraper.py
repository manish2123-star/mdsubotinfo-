import sys
import os

# Reconfigure stdout to UTF-8 to prevent UnicodeEncodeError with Hindi/Devnagari text on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    # Fallback for older python versions if needed
    import sys
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Set dry run mode environment variables
os.environ["STATE_FILE"] = "data/state_test.json"

try:
    from scraper import fetch_panel_pages, parse_notifications, parse_student_courses, build_telegram_message
    print("Initializing MDSU Scraper local test...")
    print("--------------------------------------------------")
    
    html_mdsma, html_student = fetch_panel_pages()
    notifications = parse_notifications(html_mdsma)
    courses = parse_student_courses(html_student)
    
    print("--------------------------------------------------")
    print("SUCCESS: Web scraping was successful!")
    print(f"Found {len(notifications)} general notifications.")
    print(f"Found {len(courses)} courses in the student panel.")
    
    print("\nTop 5 Latest General Notifications:")
    for i, notif in enumerate(notifications[:5], 1):
        print(f"[{i}] ID: {notif['id']}")
        print(f"    Title: {notif['title']}")
        print(f"    URL: {notif['url']}")
        
    print("\nFirst 5 Courses from Student Panel:")
    course_list = list(courses.items())
    for i, (code, details) in enumerate(course_list[:5], 1):
        print(f"[{i}] Code: {code}")
        print(f"    Name: {details['name']}")
        print(f"    Time Table: {details['time_table'] or 'N/A'}")
        print(f"    Admit Card: {'Available' if details['admit_card'] else 'N/A'}")
        print(f"    Result: {'Available' if details['result'] else 'N/A'}")
        
    print("--------------------------------------------------")
    
    print("\nFormatted Telegram Message Preview for Latest Notification:")
    print("--------------------------------------------------")
    
    # Skip the generic pinned help guidelines (usually the first 3 items) if list is long enough
    if len(notifications) > 3:
        latest_notif = notifications[3]
    elif len(notifications) > 0:
        latest_notif = notifications[0]
    else:
        latest_notif = None
        
    if latest_notif:
        print(f"English Title: {latest_notif['title']}")
        print(f"Generating Hindi translation and WordPress post link matching...")
        preview_msg = build_telegram_message(latest_notif["title"], "general", latest_notif["url"])
        print("\n=== Telegram Message Preview ===")
        print(preview_msg)
        print("================================")
    else:
        print("No notifications found to preview.")
        
    print("--------------------------------------------------")

except ImportError:
    print("Error: Could not import functions from scraper.py. Make sure scraper.py is in the same directory.")
except Exception as e:
    print("ERROR: Scraping failed. Details of the error:")
    import traceback
    traceback.print_exc()
