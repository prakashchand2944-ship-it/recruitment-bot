import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from flask import Flask, request


# =========================================================
# CONFIGURATION
# =========================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

RENDER_URL = "https://recruitment-bot-4.onrender.com"

TELEGRAM_API_URL = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else ""
)

AVAILABLE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest"
]

TARGET_CHAT_ID = None
SEEN_PDF_LINKS = set()
CHECK_INTERVAL = 3600


# =========================================================
# PORTALS
# =========================================================

AUTO_CHECK_URLS = {
    "Rajasthan RSSB / RSMSSB": {
        "url": "https://rsmssb.rajasthan.gov.in",
        "keys": ["rssb", "rsmssb", "rajasthan", "gram vikas", "patwari"]
    },

    "Rajasthan RPSC": {
        "url": "https://rpsc.rajasthan.gov.in",
        "keys": ["rpsc", "ras", "school lecturer"]
    },

    "Teacher Grade 3rd / REET": {
        "url": "https://rajeduboard.rajasthan.gov.in",
        "keys": ["reet", "grade 3", "rbse", "teacher"]
    },

    "Rajasthan SSO Portal": {
        "url": "https://sso.rajasthan.gov.in",
        "keys": ["sso"]
    },

    "Rajasthan Medical & Health": {
        "url": "https://rajhealth.rajasthan.gov.in",
        "keys": ["medical", "health", "nurse", "anm", "gnm"]
    },

    "Rajasthan High Court": {
        "url": "https://hcraj.nic.in",
        "keys": ["high court", "hc", "clerk", "steno"]
    },

    "SSC": {
        "url": "https://ssc.gov.in",
        "keys": ["ssc", "cgl", "chsl", "gd", "mts"]
    },

    "UPSC": {
        "url": "https://upsc.gov.in",
        "keys": ["upsc", "civil services", "ias", "ips", "nda", "cds"]
    },

    "Railway Recruitment Board": {
        "url": "https://indianrailways.gov.in",
        "keys": ["railway", "rrb", "rrc", "ntpc", "group d", "alp"]
    },

    "IBPS": {
        "url": "https://ibps.in",
        "keys": ["ibps", "bank", "sbi", "po", "clerk"]
    },

    "NTA": {
        "url": "https://nta.ac.in",
        "keys": ["nta", "ctet", "neet", "cuet"]
    },

    "NCS Central Govt Portal": {
        "url": "https://ncs.gov.in",
        "keys": ["ncs", "central"]
    }
}


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Recruitment Bot Webhook is active!"


# =========================================================
# TELEGRAM
# =========================================================

def send_telegram_message(chat_id, text):

    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN missing")
        return False

    if not chat_id:
        return False

    url = f"{TELEGRAM_API_URL}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=20
        )

        print(
            "Telegram response:",
            response.status_code,
            response.text[:500]
        )

        return response.ok

    except Exception as e:
        print("Telegram send error:", e)
        return False


# =========================================================
# WEBHOOK
# =========================================================

def set_webhook():

    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is missing")
        return

    webhook_url = f"{RENDER_URL}/webhook"

    url = f"{TELEGRAM_API_URL}/setWebhook"

    try:
        response = requests.get(
            url,
            params={"url": webhook_url},
            timeout=20
        )

        print("Webhook setup response:")
        print(response.text)

    except Exception as e:
        print("Webhook setup error:", e)


def get_webhook_info():

    if not TELEGRAM_BOT_TOKEN:
        return

    try:
        url = f"{TELEGRAM_API_URL}/getWebhookInfo"

        response = requests.get(
            url,
            timeout=20
        )

        print("Webhook info:")
        print(response.text)

    except Exception as e:
        print("Webhook info error:", e)


# =========================================================
# URL CLEANER
# =========================================================

def clean_url(text):

    import re

    if not text:
        return None

    url_pattern = r'https?://[^\s\)\]]+'

    match = re.search(
        url_pattern,
        text
    )

    return match.group(0) if match else None


# =========================================================
# WEBSITE FETCHER
# =========================================================

def fetch_webpage_details(url):

    headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        keywords = [
            "recruitment",
            "notification",
            "advt",
            "advertisement",
            "press",
            "notice",
            "reet",
            "result",
            "exam",
            "pdf",
            "vacancy",
            "vacancies",
            "recruit"
        ]

        pdf_links = []

        for a_tag in soup.find_all(
            "a",
            href=True
        ):

            href = a_tag["href"].strip()

            link_text = (
                a_tag.get_text()
                .strip()
                .lower()
            )

            full_url = urljoin(
                url,
                href
            )

            href_lower = href.lower()

            if (
                href_lower.endswith(".pdf")
                or ".pdf" in href_lower
                or any(
                    keyword in link_text
                    for keyword in keywords
                )
                or any(
                    keyword in href_lower
                    for keyword in keywords
                )
            ):

                if (
                    ".pdf" in href_lower
                    and full_url.startswith("http")
                    and full_url not in pdf_links
                ):
                    pdf_links.append(full_url)

        for element in soup([
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "noscript"
        ]):
            element.decompose()

        text = soup.get_text(
            separator=" "
        )

        clean_text = " ".join(
            text.split()
        )

        clean_text = clean_text[:5000]

        return clean_text, pdf_links

    except Exception as e:

        print(
            f"Scraping error for {url}:",
            e
        )

        return None, []


def is_valid_recruitment_text(text):

    if not text:
        return False

    if len(text.strip()) < 100:
        return False

    error_keywords = [
        "access denied",
        "403 forbidden",
        "404 not found",
        "service unavailable",
        "enable javascript"
    ]

    low_text = text.lower()

    if (
        any(
            error in low_text
            for error in error_keywords
        )
        and len(text) < 500
    ):
        return False

    return True


# =========================================================
# GEMINI
# =========================================================

def call_gemini_api(prompt_text):

    if not GEMINI_API_KEY:

        return (
            "⚠️ Gemini API Key उपलब्ध नहीं है। "
            "Render Environment Variables में "
            "GEMINI_API_KEY चेक करें।"
        )

    headers = {
        "Content-Type": "application/json"
    }

    formatted_prompt = f"""
You are an expert Indian government recruitment analyst.

Analyze the official website text below.

Your job is to identify ONLY genuine recruitment,
vacancy, application or recruitment notification information.

Ignore:
- Results
- Admit cards
- Answer keys
- Old notices
- Exam schedules without recruitment
- General news
- Error pages

If there is no genuine recruitment information,
reply exactly:

NO_RECRUITMENT_DATA

If recruitment information exists, answer in clear Hindi
using this structure:

📢 RECRUITMENT NOTIFICATION

━━━━━━━━━━━━━━━━━━━━━━

📌 विभाग / बोर्ड:
💼 पद का नाम:
🔢 कुल पद:
📅 महत्वपूर्ण तिथियां:
🎂 आयु सीमा:
🎓 शैक्षणिक योग्यता:
💰 आवेदन शुल्क:
💵 वेतन / Pay:
📝 आवेदन कैसे करें:
🔗 आधिकारिक वेबसाइट:

━━━━━━━━━━━━━━━━━━━━━━

Official Web Text:

{prompt_text[:4500]}
"""

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": formatted_prompt
                    }
                ]
            }
        ]
    }

    for model in AVAILABLE_MODELS:

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{model}:generateContent"
            f"?key={GEMINI_API_KEY}"
        )

        try:

            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )

            print(
                f"Gemini {model}:",
                response.status_code
            )

            response_json = response.json()

            if (
                "candidates" in response_json
                and response_json["candidates"]
            ):

                candidate = response_json["candidates"][0]

                content = candidate.get(
                    "content",
                    {}
                )

                parts = content.get(
                    "parts",
                    []
                )

                if parts:

                    return parts[0].get(
                        "text",
                        "NO_RECRUITMENT_DATA"
                    )

            time.sleep(2)

        except Exception as e:

            print(
                f"Gemini error ({model}):",
                e
            )

            time.sleep(2)

    return (
        "⚠️ Gemini अभी response नहीं दे रहा है। "
        "कुछ देर बाद दोबारा कोशिश करें।"
    )


# =========================================================
# PORTAL CHECK
# =========================================================

def check_portal(
    portal_name,
    portal_data
):

    portal_url = portal_data["url"]

    print(
        f"Checking: {portal_name}"
    )

    web_text, pdf_links = (
        fetch_webpage_details(
            portal_url
        )
    )

    if not is_valid_recruitment_text(
        web_text
    ):

        print(
            f"Invalid page: {portal_name}"
        )

        return None, []

    summary = call_gemini_api(
        web_text
    )

    if (
        not summary
        or "NO_RECRUITMENT_DATA"
        in summary
    ):

        return None, pdf_links

    return summary, pdf_links


def send_portal_update(
    chat_id,
    portal_name,
    portal_data
):

    send_telegram_message(
        chat_id,
        f"🔍 *{portal_name}* का official portal check किया जा रहा है..."
    )

    summary, pdf_links = check_portal(
        portal_name,
        portal_data
    )

    if not summary:

        send_telegram_message(
            chat_id,
            f"ℹ️ *{portal_name}* पर फिलहाल "
            "कोई स्पष्ट नई recruitment notification नहीं मिली।"
        )

        return

    response_msg = (
        f"📢 *LATEST UPDATE — "
        f"{portal_name.upper()}*\n\n"
        f"{summary}"
    )

    if pdf_links:

        response_msg += (
            "\n\n📄 *OFFICIAL PDF LINKS:*\n"
        )

        for index, pdf in enumerate(
            pdf_links[:5],
            1
        ):

            response_msg += (
                f"{index}. [Official PDF]({pdf})\n"
            )

    send_telegram_message(
        chat_id,
        response_msg
    )
# =========================================================
# BACKGROUND AUTOMATIC CHECKER
# =========================================================

def auto_check_job():

    global TARGET_CHAT_ID
    global SEEN_PDF_LINKS

    print(
        "Automatic recruitment checker started."
    )

    time.sleep(20)

    while True:

        try:

            if TARGET_CHAT_ID:

                print(
                    "Starting automatic portal scan..."
                )

                for portal_name, portal_data in AUTO_CHECK_URLS.items():

                    try:

                        web_text, pdf_links = (
                            fetch_webpage_details(
                                portal_data["url"]
                            )
                        )

                        if not is_valid_recruitment_text(
                            web_text
                        ):
                            continue

                        new_pdfs = [
                            pdf
                            for pdf in pdf_links
                            if pdf not in SEEN_PDF_LINKS
                        ]

                        if new_pdfs:

                            summary = call_gemini_api(
                                web_text
                            )

                            if (
                                summary
                                and
                                "NO_RECRUITMENT_DATA"
                                not in summary
                            ):

                                alert_msg = (
                                    "🔔 *NEW RECRUITMENT UPDATE*\n\n"
                                    f"📌 *Portal:* {portal_name}\n\n"
                                    f"{summary}"
                                )

                                alert_msg += (
                                    "\n\n📄 *OFFICIAL NOTIFICATION PDF:*\n"
                                )

                                for index, pdf in enumerate(
                                    new_pdfs[:3],
                                    1
                                ):

                                    alert_msg += (
                                        f"{index}. "
                                        f"[Official PDF]({pdf})\n"
                                    )

                                    SEEN_PDF_LINKS.add(
                                        pdf
                                    )

                                send_telegram_message(
                                    TARGET_CHAT_ID,
                                    alert_msg
                                )

                        time.sleep(5)

                    except Exception as e:

                        print(
                            f"Portal checker error "
                            f"{portal_name}:",
                            e
                        )

            else:

                print(
                    "TARGET_CHAT_ID not set. "
                    "Send /start to the bot first."
                )

            print(
                "Automatic scan finished. "
                f"Next scan in {CHECK_INTERVAL} seconds."
            )

            time.sleep(
                CHECK_INTERVAL
            )

        except Exception as e:

            print(
                "Automatic checker error:",
                e
            )

            time.sleep(60)


# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook_handler():

    global TARGET_CHAT_ID

    try:

        data = request.get_json(
            silent=True
        )

        if not data:
            return "OK", 200

        if "message" not in data:
            return "OK", 200

        message = data["message"]

        chat = message.get(
            "chat",
            {}
        )

        chat_id = chat.get(
            "id"
        )

        text = message.get(
            "text",
            ""
        ).strip()

        if not chat_id:
            return "OK", 200

        TARGET_CHAT_ID = chat_id

        user_text = text.lower()

        print(
            f"Telegram message received: {text}"
        )

        # =================================================
        # START
        # =================================================

        if user_text in [
            "/start",
            "start"
        ]:

            send_telegram_message(
                chat_id,
                """🤖 *Government Recruitment Bot*

नमस्ते! 👋

मैं सरकारी भर्ती notifications को monitor करने में आपकी मदद कर सकता हूँ।

📌 *Commands:*

/start — Bot शुरू करें
/status — Bot की स्थिति
/check — सभी portals check करें

आप सीधे लिख सकते हैं:

• Railway के update
• SSC के update
• RPSC के update
• RSSB के update
• REET के update
• Rajasthan High Court के update

या किसी official website का link भेज सकते हैं।

🔔 नई recruitment notification मिलने पर मैं आपको alert भेजूँगा।"""
            )

            return "OK", 200


        # =================================================
        # STATUS
        # =================================================

        if user_text == "/status":

            send_telegram_message(
                chat_id,
                """✅ *BOT STATUS*

🟢 Render Server: Online
🟢 Telegram Webhook: Active
🟢 Recruitment Monitor: Ready
🟢 Gemini Analyzer: Configured

आप `/check` भेजकर portal checking शुरू कर सकते हैं।"""
            )

            return "OK", 200


        # =================================================
        # MANUAL CHECK
        # =================================================

        if user_text == "/check":

            send_telegram_message(
                chat_id,
                "🔍 सभी recruitment portals check किए जा रहे हैं..."
            )

            for portal_name, portal_data in AUTO_CHECK_URLS.items():

                try:

                    summary, pdf_links = check_portal(
                        portal_name,
                        portal_data
                    )

                    if summary:

                        msg = (
                            f"📢 *{portal_name}*\n\n"
                            f"{summary}"
                        )

                        if pdf_links:

                            msg += (
                                "\n\n📄 *Official PDFs:*\n"
                            )

                            for index, pdf in enumerate(
                                pdf_links[:3],
                                1
                            ):

                                msg += (
                                    f"{index}. "
                                    f"[PDF]({pdf})\n"
                                )

                        send_telegram_message(
                            chat_id,
                            msg
                        )

                except Exception as e:

                    print(
                        f"Manual check error: {e}"
                    )

            send_telegram_message(
                chat_id,
                "✅ सभी portals की checking पूरी हो गई।"
            )

            return "OK", 200


        # =================================================
        # DIRECT URL
        # =================================================

        url = clean_url(
            text
        )

        if url:

            send_telegram_message(
                chat_id,
                "🔍 *Link analyze हो रहा है...*\nकृपया थोड़ा इंतजार करें।"
            )

            web_text, pdf_links = (
                fetch_webpage_details(
                    url
                )
            )

            if not is_valid_recruitment_text(
                web_text
            ):

                send_telegram_message(
                    chat_id,
                    "ℹ️ इस link से उपयोगी recruitment information नहीं मिल पाई।"
                )

                return "OK", 200

            summary = call_gemini_api(
                web_text
            )

            if (
                not summary
                or "NO_RECRUITMENT_DATA"
                in summary
            ):

                send_telegram_message(
                    chat_id,
                    "ℹ️ इस link पर फिलहाल कोई स्पष्ट नई recruitment notification नहीं मिली।"
                )

            else:

                if pdf_links:

                    summary += (
                        "\n\n📄 *OFFICIAL PDF LINKS:*\n"
                    )

                    for index, pdf in enumerate(
                        pdf_links[:5],
                        1
                    ):

                        summary += (
                            f"{index}. "
                            f"[Official PDF {index}]({pdf})\n"
                        )

                send_telegram_message(
                    chat_id,
                    summary
                )

            return "OK", 200


        # =================================================
        # PORTAL NAME
        # =================================================

        matched_portal = None
        matched_data = None

        for portal_name, portal_data in AUTO_CHECK_URLS.items():

            if any(
                key in user_text
                for key in portal_data["keys"]
            ):

                matched_portal = portal_name
                matched_data = portal_data
                break

        if matched_portal:

            send_portal_update(
                chat_id,
                matched_portal,
                matched_data
            )

            return "OK", 200


        # =================================================
        # DEFAULT RESPONSE
        # =================================================

        send_telegram_message(
            chat_id,
            """🤖 मैं recruitment monitoring कर रहा हूँ।

आप `/start` भेज सकते हैं।

या लिखें:

🚆 Railway update
📋 SSC update
🏛️ RPSC update
📚 RSSB update
👨‍🏫 REET update
⚖️ High Court update

या किसी official website का link भेजें।"""
        )

        return "OK", 200

    except Exception as e:

        print(
            "Webhook handler error:",
            e
        )

        return "OK", 200


# =========================================================
# STARTUP
# =========================================================

def startup():

    print(
        "======================================"
    )

    print(
        "Government Recruitment Bot Starting..."
    )

    print(
        "======================================"
    )

    if not TELEGRAM_BOT_TOKEN:

        print(
            "❌ TELEGRAM_BOT_TOKEN missing!"
        )

    else:

        print(
            "✅ Telegram Bot Token loaded."
        )

        set_webhook()

        get_webhook_info()

    if not GEMINI_API_KEY:

        print(
            "❌ GEMINI_API_KEY missing!"
        )

    else:

        print(
            "✅ Gemini API Key loaded."
        )

    checker_thread = threading.Thread(
        target=auto_check_job,
        daemon=True
    )

    checker_thread.start()

    print(
        "✅ Background recruitment checker started."
    )


# =========================================================
# START BOT
# =========================================================

startup()


# =========================================================
# LOCAL DEVELOPMENT
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )