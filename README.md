# 🔔 Website Monitor Telegram Bot

A lightweight, automated system powered by **GitHub Actions** and **Python** that monitors a website for updates and sends notifications directly to a Telegram group or channel.

## 🚀 How it Works

1. **GitHub Actions** triggers a Python script on a scheduled cron job (default: hourly).
2. The script (`scraper.py`) scrapes the target website and checks if there are new updates.
   - *Example/Default target:* Monitors the top story on [Hacker News](https://news.ycombinator.com/).
3. If a new update is detected:
   - It sends a markdown-formatted alert to your Telegram Group.
   - It updates `data/state.json` with the new state.
   - GitHub Actions automatically commits and pushes the updated state back to the repository.

---

## 🛠️ Setup Instructions

### Step 1: Create a Telegram Bot
1. Open Telegram, search for `@BotFather`, and start a conversation.
2. Send the `/newbot` command.
3. Follow the instructions to choose a name and username for your bot.
4. Copy the **HTTP API Token** generated (this is your `TELEGRAM_BOT_TOKEN`).

### Step 2: Get your Telegram Chat ID
1. Create a new Telegram Group (or use an existing one).
2. Add your new bot to the group and make it an **Administrator** (with permission to send messages).
3. Send a message in the group (e.g., `/test` or `Hello bot`).
4. In your browser, open the following URL (replace `<YOUR_BOT_TOKEN>` with your bot's token):
   ```text
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
5. Look at the JSON response. Find the `"chat"` object inside the message. The `"id"` field (e.g. `-100123456789`) is your `TELEGRAM_CHAT_ID`. Keep the minus sign.

### Step 3: Configure GitHub Repository Settings

To run this automatically, push this code to your GitHub repository and set up the following:

#### A. Add Secrets
1. Go to your GitHub repository.
2. Click **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret** and add:
   - Name: `TELEGRAM_BOT_TOKEN` | Value: *Your bot token from Step 1*
   - Name: `TELEGRAM_CHAT_ID` | Value: *Your chat ID from Step 2*

#### B. Enable Write Permissions (Crucial!)
Because the bot needs to save its state (so it doesn't send duplicate alerts), it must commit `data/state.json` back to your repo.
1. In your GitHub repository, go to **Settings** > **Actions** > **General**.
2. Scroll down to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

---

## 💻 Running & Testing Locally

### Prerequisites
Make sure you have Python 3 installed.

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test Scraper Logic (Dry Run)
You can test if the website scraper is working without setting up Telegram credentials:
```bash
python test_scraper.py
```
This will fetch the page, parse the target details, and print a preview of the message that would be sent.

### 3. Run Live Locally (With Telegram Notifications)
Set your environment variables and run:
```bash
# Windows (PowerShell)
$env:TELEGRAM_BOT_TOKEN="your-token"
$env:TELEGRAM_CHAT_ID="your-chat-id"
python scraper.py

# macOS/Linux (Bash)
TELEGRAM_BOT_TOKEN="your-token" TELEGRAM_CHAT_ID="your-chat-id" python scraper.py
```

---

## ✏️ Customizing the Scraper

To monitor your own choice of website:
1. Open [scraper.py](scraper.py).
2. Change the `TARGET_URL` default value or pass it as an environment variable.
3. Scroll down to the `# SCRAPING LOGIC` block inside `fetch_and_parse()`.
4. Use `BeautifulSoup` to target the specific HTML elements (classes, IDs, tags) containing your website's updates.
