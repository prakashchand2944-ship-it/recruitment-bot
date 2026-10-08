import os
import logging
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify

# =========================================================
# BOT 4 - NOTICE ALERT
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in Render Environment Variables")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Render automatically provides this variable
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()

# Optional manual URL
APP_URL = os.getenv("APP_URL", "").strip()

# Secret webhook path
WEBHOOK_SECRET = os.getenv(
    "WEBHOOK_SECRET",
    "notice-alert-bot4-secret"
).strip()

WEBHOOK_PATH = f"/telegram/{WEBHOOK_SECRET}"

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("BOT4")

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10) "
        "AppleWebKit/537.36 "
        "Chrome/131.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8"
})


# =========================================================
# CHECK CONTROL
# =========================================================

CHECKING = {}
CHECK_LOCK = threading.Lock()


# =========================================================
# RECRUITMENT PORTALS
# =========================================================

PORTALS = [
    {
        "name": "Railway Recruitment Board",
        "url": "https://indianrailways.gov.in/",
        "keywords": [
            "recruitment",
            "vacancy",
            "notification",
            "rrb",
            "rrc",
            "cen"
        ]
    },

    {
        "name": "Staff Selection Commission",
        "url": "https://ssc.gov.in/",
        "keywords": [
            "recruitment",
            "vacancy",
            "notification",
            "notice",
            "exam"
        ]
    },

    {
        "name": "UPSC",
        "url": "https://upsc.gov.in/",
        "keywords": [
            "recruitment",
            "notification",
            "vacancy",
            "examination",
            "advertisement"
        ]
    },

    {
        "name": "India Post",
        "url": "https://www.indiapost.gov.in/",
        "keywords": [
            "recruitment",
            "vacancy",
            "notification",
            "gds"
        ]
    },

    {
        "name": "RPSC",
        "url": "https://rpsc.rajasthan.gov.in/",
        "keywords": [
            "recruitment",
            "advertisement",
            "vacancy",
            "notification",
            "exam"
        ]
    },

    {
        "name": "RSSB",
        "url": "https://rssb.rajasthan.gov.in/",
        "keywords": [
            "recruitment",
            "advertisement",
            "vacancy",
            "notification",
            "exam"
        ]
    }
]


# =========================================================
# TELEGRAM API
# =========================================================

def telegram(method, data=None):

    try:
        response = session.post(
            f"{TELEGRAM_API}/{method}",
            data=data or {},
            timeout=20
        )

        logger.info(
            "Telegram %s -> %s",
            method,
            response.status_code
        )

        return response.json()

    except Exception as e:

        logger.exception(
            "Telegram API error: %s",
            e
        )

        return {
            "ok": False,
            "description": str(e)
        }


def send_message(chat_id, text, keyboard=None):

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if keyboard:
        data["reply_markup"] = keyboard

    return telegram(
        "sendMessage",
        data
    )


def edit_message(chat_id, message_id, text, keyboard=None):

    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if keyboard:
        data["reply_markup"] = keyboard

    return telegram(
        "editMessageText",
        data
    )


def answer_callback(callback_id, text=None):

    data = {
        "callback_query_id": callback_id
    }

    if text:
        data["text"] = text

    return telegram(
        "answerCallbackQuery",
        data
    )


# =========================================================
# MENUS
# =========================================================

def main_menu():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "🔍 Check Recruitment",
                    "callback_data": "CHECK"
                }
            ],
            [
                {
                    "text": "📢 Latest Notices",
                    "callback_data": "LATEST"
                }
            ],
            [
                {
                    "text": "ℹ️ Bot Status",
                    "callback_data": "STATUS"
                }
            ]
        ]
    }


def back_menu():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "🔙 मुख्य मेनू",
                    "callback_data": "MAIN"
                }
            ]
        ]
    }


# =========================================================
# START
# =========================================================

def start_bot(chat_id):

    send_message(
        chat_id,

        "🤖 <b>Notice Alert — Bot 4</b>\n\n"
        "सरकारी भर्ती और recruitment notices "
        "check करने के लिए नीचे विकल्प चुनें 👇",

        main_menu()
    )


# =========================================================
# PORTAL CHECK
# =========================================================

def check_portal(portal):

    name = portal["name"]
    url = portal["url"]
    keywords = portal["keywords"]

    logger.info("Checking: %s", name)

    try:

        response = session.get(
            url,
            timeout=(8, 15),
            allow_redirects=True
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for tag in soup([
            "script",
            "style",
            "noscript"
        ]):
            tag.decompose()

        results = []

        for link in soup.find_all(
            "a",
            href=True
        ):

            title = link.get_text(
                " ",
                strip=True
            )

            href = link.get(
                "href"
            )

            if not title:
                continue

            combined = (
                title + " " + href
            ).lower()

            if any(
                keyword.lower() in combined
                for keyword in keywords
            ):

                if href.startswith("/"):
                    from urllib.parse import urljoin
                    href = urljoin(
                        response.url,
                        href
                    )

                item = {
                    "title": title[:180],
                    "url": href
                }

                if item not in results:
                    results.append(item)

        return {
            "name": name,
            "status": "ok",
            "results": results[:8]
        }

    except requests.exceptions.Timeout:

        return {
            "name": name,
            "status": "error",
            "message": "Connection timeout"
        }

    except requests.exceptions.ConnectionError:

        return {
            "name": name,
            "status": "error",
            "message": "Portal connection refused/unavailable"
        }

    except requests.exceptions.HTTPError as e:

        return {
            "name": name,
            "status": "error",
            "message": f"HTTP error: {e}"
        }

    except Exception as e:

        logger.exception(
            "%s error: %s",
            name,
            e
        )

        return {
            "name": name,
            "status": "error",
            "message": "Portal check failed"
        }


# =========================================================
# CHECK ALL
# =========================================================

def check_all_portals():

    results = []

    for portal in PORTALS:

        result = check_portal(
            portal
        )

        results.append(
            result
        )

    return results


# =========================================================
# FORMAT RESULT
# =========================================================

def make_result_message(results):

    text = (
        "✅ <b>Recruitment checking पूरी हो गई</b>\n\n"
    )

    for result in results:

        name = result["name"]

        if result["status"] == "error":

            text += (
                f"🟠 <b>{name}</b>\n"
                f"Portal अभी उपलब्ध नहीं है।\n\n"
            )

            continue

        notices = result.get(
            "results",
            []
        )

        text += (
            f"🟢 <b>{name}</b>\n"
        )

        if not notices:

            text += (
                "कोई relevant notice link नहीं मिला।\n\n"
            )

            continue

        for notice in notices:

            title = notice["title"]
            url = notice["url"]

            text += (
                f'• <a href="{url}">'
                f"{title}"
                f"</a>\n"
            )

        text += "\n"

    return text


# =========================================================
# BACKGROUND CHECK
# =========================================================

def run_check(
    chat_id,
    status_message_id
):

    try:

        logger.info(
            "BOT 4 check started: %s",
            chat_id
        )

        results = check_all_portals()

        final_text = make_result_message(
            results
        )

        edit_message(
            chat_id,
            status_message_id,
            final_text,
            back_menu()
        )

    except Exception as e:

        logger.exception(
            "Check error: %s",
            e
        )

        edit_message(
            chat_id,
            status_message_id,

            "❌ <b>Checking में समस्या आई।</b>\n\n"
            "किसी portal की समस्या से पूरा bot बंद नहीं हुआ है।",

            back_menu()
        )

    finally:

        with CHECK_LOCK:
            CHECKING.pop(
                chat_id,
                None
            )

        logger.info(
            "BOT 4 check finished: %s",
            chat_id
        )


# =========================================================
# START CHECK
# =========================================================

def start_check(chat_id):

    with CHECK_LOCK:

        if CHECKING.get(chat_id):

            send_message(
                chat_id,
                "⏳ <b>एक checking पहले से चल रही है।</b>\n\n"
                "पहले उसका result आने दें।"
            )

            return

        CHECKING[chat_id] = True

    response = send_message(
        chat_id,

        "🔍 <b>सभी recruitment portals check किए जा रहे हैं...</b>\n\n"
        "⏳ कृपया थोड़ी देर प्रतीक्षा करें।"
    )

    if not response.get("ok"):

        with CHECK_LOCK:
            CHECKING.pop(
                chat_id,
                None
            )

        return

    message_id = response[
        "result"
    ]["message_id"]

    thread = threading.Thread(
        target=run_check,
        args=(
            chat_id,
            message_id
        ),
        daemon=True
    )

    thread.start()


# =========================================================
# CALLBACK
# =========================================================

def handle_callback(callback):

    callback_id = callback.get(
        "id"
    )

    data = callback.get(
        "data",
        ""
    )

    message = callback.get(
        "message",
        {}
    )

    chat = message.get(
        "chat",
        {}
    )

    chat_id = chat.get(
        "id"
    )

    message_id = message.get(
        "message_id"
    )

    answer_callback(
        callback_id
    )

    if not chat_id:
        return

    if data == "MAIN":

        edit_message(
            chat_id,
            message_id,

            "🤖 <b>Notice Alert — Bot 4</b>\n\n"
            "विकल्प चुनें 👇",

            main_menu()
        )

    elif data in (
        "CHECK",
        "LATEST"
    ):

        start_check(
            chat_id
        )

    elif data == "STATUS":

        with CHECK_LOCK:
            running = CHECKING.get(
                chat_id,
                False
            )

        if running:
            status = (
                "🟠 Recruitment checking चल रही है।"
            )
        else:
            status = (
                "🟢 Bot तैयार है।"
            )

        edit_message(
            chat_id,
            message_id,

            "ℹ️ <b>Bot 4 Status</b>\n\n"
            f"{status}\n\n"
            f"🌐 Configured portals: "
            f"<b>{len(PORTALS)}</b>",

            back_menu()
        )


# =========================================================
# UPDATE PROCESSOR
# =========================================================

def process_update(update):

    try:

        # -------------------------
        # Message
        # -------------------------

        message = update.get(
            "message"
        )

        if message:

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
            )

            if chat_id:

                if text.startswith(
                    "/start"
                ):

                    start_bot(
                        chat_id
                    )

                elif text.startswith(
                    "/check"
                ):

                    start_check(
                        chat_id
                    )

                elif text.startswith(
                    "/status"
                ):

                    with CHECK_LOCK:
                        running = CHECKING.get(
                            chat_id,
                            False
                        )

                    send_message(
                        chat_id,

                        "🤖 <b>Bot 4</b>\n\n"
                        + (
                            "🟠 Checking चल रही है।"
                            if running
                            else
                            "🟢 Bot ready है।"
                        )
                    )

                else:

                    start_bot(
                        chat_id
                    )

        # -------------------------
        # Callback
        # -------------------------

        callback = update.get(
            "callback_query"
        )

        if callback:

            handle_callback(
                callback
            )

    except Exception as e:

        logger.exception(
            "Update error: %s",
            e
        )


# =========================================================
# WEBHOOK
# =========================================================

@app.route(
    WEBHOOK_PATH,
    methods=["POST"]
)
def telegram_webhook():

    update = request.get_json(
        silent=True
    )

    if not update:

        return jsonify({
            "ok": False
        }), 400

    # Telegram को तुरंत 200
    # बाकी processing background में
    thread = threading.Thread(
        target=process_update,
        args=(update,),
        daemon=True
    )

    thread.start()

    return jsonify({
        "ok": True
    }), 200


# =========================================================
# HEALTH
# =========================================================

@app.route("/")
def home():

    return (
        "Notice Alert Bot 4 is running.",
        200
    )


@app.route("/health")
def health():

    return jsonify({
        "ok": True,
        "bot": "Notice Alert Bot 4",
        "portals": len(PORTALS)
    })


# =========================================================
# TELEGRAM WEBHOOK INFO
# =========================================================

@app.route("/webhook-info")
def webhook_info():

    return jsonify(
        telegram(
            "getWebhookInfo"
        )
    )


# =========================================================
# SET WEBHOOK
# =========================================================

def setup_webhook():

    base_url = (
        APP_URL
        or RENDER_URL
    ).rstrip("/")

    if not base_url:

        logger.error(
            "Render URL नहीं मिली। "
            "APP_URL Environment Variable सेट करें।"
        )

        return

    webhook_url = (
        base_url +
        WEBHOOK_PATH
    )

    logger.info(
        "BOT 4 webhook setting: %s",
        webhook_url
    )

    result = telegram(
        "setWebhook",
        {
            "url": webhook_url,

            # पुराने pending updates हटाएँ
            "drop_pending_updates": "true",

            "allowed_updates": (
                '["message","callback_query"]'
            )
        }
    )

    logger.info(
        "BOT 4 webhook result: %s",
        result
    )


# =========================================================
# START SERVER
# =========================================================

# Gunicorn के साथ भी webhook सेट करें
try:
    setup_webhook()
except Exception as e:
    logger.exception("Webhook setup failed: %s", e)