import sys
import os

try:
    from scraper import fetch_and_parse_mdsu
    print("Initializing MDSU Scraper local test...")
    print("--------------------------------------------------")
    
    notifications = fetch_and_parse_mdsu()
    
    print("--------------------------------------------------")
    print(f"✅ Web scraping was successful! Found {len(notifications)} notifications.")
    print("\nTop 5 Latest Notifications:")
    
    for i, notif in enumerate(notifications[:5], 1):
        print(f"\n[{i}] ID: {notif['id']}")
        print(f"    Title: {notif['title']}")
        print(f"    URL: {notif['url']}")
        
    print("--------------------------------------------------")

except ImportError:
    print("Error: Could not import fetch_and_parse_mdsu from scraper.py. Make sure scraper.py is in the same directory.")
except Exception as e:
    print("❌ Scraping failed. Details of the error:")
    import traceback
    traceback.print_exc()
