import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from flask import Flask

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8794314361:AAEXgvzW2E8KVACi-NnIQI0NCzE8SHWr58s"
GEMINI_API_KEY = "AQ.Ab8RN6L01GyaDIWE_tA8amlG19II63e4AylDxyeG8SKoBpiq_A"

TARGET_CHAT_ID = None 
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

AVAILABLE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest"
]

# All Central & Rajasthan Recruitment Portals with Keywords for Smart Search
AUTO_CHECK_URLS = {
    "Rajasthan RSSB / RSMSSB": {"url": "https://rsmssb.rajasthan.gov.in", "keys": ["rssb", "rsmssb", "rajasthan", "gram vikas", "patwari"]},
    "Rajasthan RPSC": {"url": "https://rpsc.rajasthan.gov.in", "keys": ["rpsc", "ras", "school lecturer"]},
    "Teacher Grade 3rd / REET (RBSE)": {"url": "https://rajeduboard.rajasthan.gov.in", "keys": ["reet", "grade 3", "rbse", "teacher"]},
    "Rajasthan SSO Portal": {"url": "https://sso.rajasthan.gov.in", "keys": ["sso"]},
    "Rajasthan Medical & Health (Raj Health)": {"url": "https://rajhealth.rajasthan.gov.in", "keys": ["medical", "health", "nurse", "anm", "gnm"]},
    "Rajasthan High Court (RHC)": {"url": "https://hcraj.nic.in", "keys": ["high court", "hc", "clerk", "steno"]},
    "SSC (Staff Selection Commission)": {"url": "https://ssc.gov.in", "keys": ["ssc", "cgl", "chsl", "gd", "mts"]},
    "UPSC (Union Public Service Commission)": {"url": "https://upsc.gov.in", "keys": ["upsc", "civil services", "ias", "ips", "nda", "cds"]},
    "Railway Recruitment Board (RRB)": {"url": "https://indianrailways.gov.in", "keys": ["railway", "rrb", "rrc", "ntpc", "group d", "alp"]},
    "IBPS (Banking)": {"url": "https://ibps.in", "keys": ["ibps", "bank", "sbi", "po", "clerk"]},
    "NTA (CTET/National Testing)": {"url": "https://nta.ac.in", "keys": ["nta", "ctet", "neet", "cuet"]},
    "NCS Central Govt Portal": {"url": "https://ncs.gov.in", "keys": ["ncs", "central"]}
}

SEEN_PDF_LINKS = set()

def clean_url(text: str) -> str:
    import re
    url_pattern = r'https?://[^\s\)\]]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None

def fetch_webpage_details(url: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        keywords = ['recruitment', 'notification', 'advt', 'advertisement', 'press', 'notice', 'reet', 'result', 'exam', 'pdf']
        
        pdf_links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            link_text = a_tag.get_text().strip().lower()
            
            if href.lower().endswith('.pdf') or any(kw in link_text for kw in keywords) or any(kw in href.lower() for kw in keywords):
                if '.pdf' in href.lower():
                    full_pdf_url = urljoin(url, href)
                    if full_pdf_url not in pdf_links and full_pdf_url.startswith("http"):
                        pdf_links.append(full_pdf_url)
        
        for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            element.decompose()
            
        text = soup.get_text(separator=' ')
        clean_text = ' '.join(text.split())[:3500]
        
        return clean_text, pdf_links
    except Exception as e:
        print(f"Scraping error: {e}")
        return None, []

def is_valid_recruitment_text(text: str) -> bool:
    if not text or len(text.strip()) < 100:
        return False
    error_keywords = ["access denied", "403 forbidden", "404 not found", "error", "service unavailable", "enable javascript"]
    low_text = text.lower()
    if any(err in low_text for err in error_keywords) and len(text) < 300:
        return False
    return True

def call_gemini_api(prompt_text: str) -> str:
    headers = {'Content-Type': 'application/json'}
    formatted_prompt = (
        "You are an expert government job analyst. Carefully analyze the text provided below and extract "
        "the exact recruitment/exam details. Present it in clear Hindi with the following strict structure. "
        "If the text has NO recruitment details or is an error page, reply strictly with: 'NO_RECRUITMENT_DATA'\n\n"
        "📢 *RECRUITMENT NOTIFICATION SUMMARY*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 *विभाग / बोर्ड:* \n"
        "💼 *पद का नाम (Post):* \n"
        "🔢 *कुल पद (Total Vacancies):* \n"
        "📅 *महत्वपूर्ण तिथियां (Dates):* \n"
        "🎂 *आयु सीमा (Age Limit):* \n"
        "🎓 *शैक्षणिक योग्यता (Qualification):* \n"
        "💰 *आवेदन शुल्क / वेतन (Fee/Pay):* \n"
        "📝 *आवेदन कैसे करें (How to Apply):* \n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Official Web Text:\n{prompt_text[:2500]}"
    )
    data = {"contents": [{"parts": [{"text": formatted_prompt}]}]}
    
    for attempt in range(2):
        for model in AVAILABLE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            try:
                res = requests.post(url, headers=headers, json=data, timeout=15)
                res_json = res.json()
                if 'candidates' in res_json and len(res_json['candidates']) > 0:
                    candidate = res_json['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        return candidate['content']['parts'][0]['text']
                time.sleep(1.5)
            except Exception:
                time.sleep(1)
        time.sleep(3)
    return "⚠️ High Demand Error: API busy hai."

def send_telegram_message(chat_id: int, text: str):
    if not chat_id:
        return
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

# --- BACKGROUND AUTOMATIC CHECKER ---
def auto_check_job():
    global TARGET_CHAT_ID, SEEN_PDF_LINKS
    print("Auto-checking portals...")
    
    while True:
        time.sleep(10)
        if TARGET_CHAT_ID:
            for portal_name, data in AUTO_CHECK_URLS.items():
                portal_url = data["url"]
                web_text, pdf_links = fetch_webpage_details(portal_url)
                
                if not is_valid_recruitment_text(web_text):
                    continue

                new_pdfs = [pdf for pdf in pdf_links if pdf not in SEEN_PDF_LINKS]
                if new_pdfs:
                    summary = call_gemini_api(web_text)
                    if "NO_RECRUITMENT_DATA" not in summary and summary.count("जानकारी उपलब्ध नहीं") < 5:
                        alert_msg = f"🔔 *NEW UPDATE: {portal_name.upper()}*\n\n" + summary
                        alert_msg += "\n\n📄 *OFFICIAL NOTIFICATION PDF:* \n"
                        for idx, pdf in enumerate(new_pdfs[:3], 1):
                            SEEN_PDF_LINKS.add(pdf)
                            alert_msg += f"🔗 [Download Official PDF {idx}]({pdf})\n"
                        send_telegram_message(TARGET_CHAT_ID, alert_msg)
                time.sleep(4)
        time.sleep(12 * 3600)

def process_updates(offset=None):
    url = f"{TELEGRAM_API_URL}/getUpdates"
    params = {"timeout": 30, "offset": offset}
    try:
        res = requests.get(url, params=params, timeout=35)
        return res.json()
    except Exception as e:
        return None

# --- FLASK WEB SERVER FOR RENDER 24/7 UPTIME ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Recruitment Bot is active and running 24/7!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def main():
    global TARGET_CHAT_ID
    print("Bot is running with Smart On-Demand & Auto-Monitoring...")
    
    # Flask सर्वर को बैकग्राउंड थ्रेड में चलाना
    threading.Thread(target=run_flask, daemon=True).start()
    # ऑटो-चेकर को बैकग्राउंड थ्रेड में चलाना
    threading.Thread(target=auto_check_job, daemon=True).start()
    
    last_update_id = None
    
    while True:
        updates = process_updates(last_update_id)
        if updates and updates.get("ok"):
            for result in updates.get("result", []):
                last_update_id = result["update_id"] + 1
                
                message = result.get("message")
                if not message or "text" not in message:
                    continue
                
                chat_id = message["chat"]["id"]
                TARGET_CHAT_ID = chat_id 
                user_text = message["text"].lower()
                
                # Check if user sent a direct URL
                url = clean_url(user_text)
                if url:
                    send_telegram_message(chat_id, "🔍 *Link analyze ho raha hai... Wait karein...*")
                    web_text, pdf_links = fetch_webpage_details(url)
                    if not is_valid_recruitment_text(web_text):
                        send_telegram_message(chat_id, "ℹ️ Filhal is link par koi new update nahi hai.")
                        continue
                    summary = call_gemini_api(web_text)
                    if "NO_RECRUITMENT_DATA" in summary or summary.count("जानकारी उपलब्ध नहीं") >= 5:
                        send_telegram_message(chat_id, "ℹ️ Filhal is link par koi new update nahi hai.")
                    else:
                        if pdf_links:
                            summary += "\n\n📄 *OFFICIAL NOTIFICATION PDF LINKS:*\n"
                            for idx, pdf in enumerate(pdf_links[:5], 1):
                                summary += f"🔗 [Download Official PDF {idx}]({pdf})\n"
                        send_telegram_message(chat_id, summary)
                    continue

                # Check if user asked for a specific portal by name
                matched_portal = None
                matched_url = None
                for portal_name, data in AUTO_CHECK_URLS.items():
                    if any(key in user_text for key in data["keys"]):
                        matched_portal = portal_name
                        matched_url = data["url"]
                        break
                
                if matched_portal:
                    send_telegram_message(chat_id, f"🔍 *{matched_portal}* portal check kiya ja raha hai...")
                    web_text, pdf_links = fetch_webpage_details(matched_url)
                    
                    if not is_valid_recruitment_text(web_text):
                        send_telegram_message(chat_id, f"ℹ️ *{matched_portal}:* Filhal koi new update nahi hai.")
                        continue
                        
                    summary = call_gemini_api(web_text)
                    if "NO_RECRUITMENT_DATA" in summary or summary.count("जानकारी उपलब्ध नहीं") >= 5:
                        send_telegram_message(chat_id, f"ℹ️ *{matched_portal}:* Filhal koi new update nahi hai.")
                    else:
                        response_msg = f"📌 *LATEST UPDATE FROM {matched_portal.upper()}:*\n\n" + summary
                        if pdf_links:
                            response_msg += "\n\n📄 *OFFICIAL PDF LINKS:*\n"
                            for idx, pdf in enumerate(pdf_links[:3], 1):
                                response_msg += f"🔗 [Download PDF {idx}]({pdf})\n"
                        send_telegram_message(chat_id, response_msg)
                else:
                    send_telegram_message(chat_id, "🤖 Main automatic monitoring kar raha hoon. Aap chahein toh kisi bhi portal ka naam likh sakte hain (jaise: 'Railway ke update batao', 'SSC ka kya hai').")
        
        time.sleep(1)

if __name__ == '__main__':
    main()

