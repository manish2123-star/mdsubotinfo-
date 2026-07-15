import sys
import os

# Set dry run mode environment variable
os.environ["STATE_FILE"] = "data/state_test.json"

try:
    from scraper import fetch_and_parse
    print("Initializing test run...")
    print("--------------------------------------------------")
    
    unique_id, message = fetch_and_parse()
    
    print("--------------------------------------------------")
    print("✅ Web scraping was successful!")
    print(f"🔑 Extracted Unique ID: {unique_id}")
    print("\n📝 Formatted Telegram Message Preview:")
    print(message)
    print("--------------------------------------------------")

except ImportError:
    print("Error: Could not import fetch_and_parse from scraper.py. Make sure scraper.py exists in the same folder.")
except Exception as e:
    print("❌ Scraping failed. Details of the error:")
    import traceback
    traceback.print_exc()
