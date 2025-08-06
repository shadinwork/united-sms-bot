import os
import requests
from telegram import Bot
from telegram.constants import ParseMode
import time
import re
from bs4 import BeautifulSoup
from threading import Thread

# Configuration from Railway environment variables
PANEL_URL = os.getenv("PANEL_URL", "http://54.37.83.141/ints/agent/SMSCDRStats")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PANEL_USERNAME = os.getenv("PANEL_USERNAME")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))

# Initialize bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def keep_alive():
    """Ping the app to prevent sleeping"""
    while True:
        time.sleep(300)
        try:
            requests.get("https://your-app-name.up.railway.app")
        except:
            pass

def login_to_panel():
    """Login to United SMS panel and return session"""
    session = requests.Session()
    login_url = PANEL_URL.replace("SMSCDRStats", "login")
    login_data = {
        "username": PANEL_USERNAME,
        "password": PANEL_PASSWORD,
        "login": "Login"
    }
    try:
        response = session.post(login_url, data=login_data)
        if "SMSCDRStats" in response.text or "Dashboard" in response.text:
            print("✓ Login successful")
            return session
        else:
            print("× Login failed - check credentials")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def scrape_sms_stats(session):
    """Scrape SMS CDR Stats page for OTP messages"""
    try:
        response = session.get(PANEL_URL)
        soup = BeautifulSoup(response.text, 'html.parser')
        messages = []
        
        # Find SMS table
        table = soup.find('table', {'class': 'table'})
        
        if table:
            for row in table.find_all('tr')[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 4:
                    message = {
                        'number': cols[0].text.strip(),
                        'client': cols[1].text.strip(),
                        'text': cols[2].text.strip(),
                        'time': cols[3].text.strip() if len(cols) > 3 else "N/A"
                    }
                    if re.search(r'OTP|verification|কোড|code', message['text'], re.IGNORECASE):
                        messages.append(message)
        return messages
    except Exception as e:
        print(f"Scraping error: {e}")
        return []

def send_to_telegram(message):
    """Send formatted message to Telegram"""
    otp_code = re.search(r'\b\d{4,6}\b', message['text'])
    formatted = f"""
🔐 *New OTP Received* 🔐
📞 *From:* `{message['number']}`
👤 *Client:* {message['client']}
🕒 *Time:* {message['time']}
🔢 *OTP Code:* `{otp_code.group() if otp_code else 'Not found'}`
📝 *Message:*
{message['text'][:150]}...
"""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=formatted,
            parse_mode=ParseMode.MARKDOWN
        )
        print(f"✓ OTP forwarded from {message['number']}")
    except Exception as e:
        print(f"Telegram send error: {e}")

def monitor_otp_messages():
    """Main monitoring loop"""
    session = login_to_panel()
    if not session:
        return
    
    last_messages = []
    
    while True:
        try:
            current_messages = scrape_sms_stats(session)
            new_messages = [m for m in current_messages if m not in last_messages]
            
            for msg in new_messages:
                send_to_telegram(msg)
            
            last_messages = current_messages
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Monitoring error: {e}")
            time.sleep(60)
            session = login_to_panel()

if __name__ == "__main__":
    print("🚂 Starting United SMS OTP Forwarder on Railway")
    
    # Start keep-alive thread
    Thread(target=keep_alive, daemon=True).start()
    
    # Start monitoring
    monitor_otp_messages()
