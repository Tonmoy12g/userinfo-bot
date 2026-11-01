"""
Telegram ID & Info Finder Bot (Ultra ID Finder Pro)
Author: Tonmoy Developer
Features:
- Native Telegram Peer Request Buttons (Telegram Bot API 6.5+ / 7.0+)
  • 👤 ইউজার খুঁজুন (Request Users) [Primary Blue]
  • 🌐 Public Group [Success Green] | 🔒 Private Group [Danger Red]
  • 🌐 Public Channel [Success Green] | 🔒 Private Channel [Danger Red]
  • 🤖 Bots [Primary Blue] | Premium ⭐ [Success Green]
- Full-Color Custom Buttons (Bot API 9.4+ style: primary, success, danger)
- Forward Message ID & Info Extractor (Forward any message from channel/user to get ID)
- Self ID Finder (/id, /me)
- Bot-Level Force Subscribe (Grow Telegram Channel)
- Admin Panel with Broadcast (/admin)
- 24/7 Render Keep-Alive Server (HEAD/GET UptimeRobot Support)
- SQLite Database for User Storage & Stats
"""

import os
import sys
import time
import json
import sqlite3
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Any, Optional
import requests

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("IDFinderBot")

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "TonmoyDeveloperBD24")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "TonmoyDeveloperBD24")

# ==================== RENDER / WEB SERVICE KEEP-ALIVE ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Telegram ID Finder Bot is running 24/7 on Render!")

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass

def start_render_health_server():
    port = int(os.getenv("PORT", "8080"))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Render Web Service health check listening on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Could not start health check server on port {port}: {e}")

# ==================== DATABASE SETUP ====================
DB_FILE = "id_finder_bot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        searches_count INTEGER DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_username', ?)", (SUPPORT_USERNAME,))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_username', ?)", (CHANNEL_USERNAME,))
    # Force Subscribe Channels
    c.execute('''CREATE TABLE IF NOT EXISTS force_channels (
        channel_username TEXT PRIMARY KEY,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # Add default channel if not exists
    default_ch = CHANNEL_USERNAME if CHANNEL_USERNAME.startswith("@") else f"@{CHANNEL_USERNAME}"
    c.execute("INSERT OR IGNORE INTO force_channels (channel_username) VALUES (?)", (default_ch,))

    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_force_channels() -> List[str]:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT channel_username FROM force_channels ORDER BY added_at ASC")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_force_channel(channel: str):
    ch = channel.strip()
    if not ch.startswith("@") and not ch.startswith("-100"):
        ch = "@" + ch
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO force_channels (channel_username) VALUES (?)", (ch,))
    conn.commit()
    conn.close()

def remove_force_channel(channel: str):
    ch = channel.strip()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM force_channels WHERE channel_username = ? OR channel_username = ?", (ch, ch.replace("@", "")))
    conn.commit()
    conn.close()

def increment_search_count(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET searches_count = searches_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ==================== TELEGRAM API CLIENT ====================
class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session = requests.Session()

    def request(self, method: str, data: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}/{method}"
        try:
            res = self.session.post(url, json=data, timeout=30)
            return res.json()
        except Exception as e:
            logger.error(f"Error calling {method}: {e}")
            return {"ok": False, "description": str(e)}

    def send_message(self, chat_id: Any, text: str, reply_markup: Optional[Dict] = None, parse_mode: str = "HTML") -> Dict:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.request("sendMessage", payload)

    def answer_callback(self, callback_query_id: str, text: Optional[str] = None, show_alert: bool = False) -> Dict:
        payload = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text
        return self.request("answerCallbackQuery", payload)

    def get_chat(self, chat_id: Any) -> Dict:
        return self.request("getChat", {"chat_id": chat_id})

    def get_chat_member(self, chat_id: Any, user_id: int) -> Dict:
        return self.request("getChatMember", {"chat_id": chat_id, "user_id": user_id})

    def get_me(self) -> Dict:
        return self.request("getMe")

# State tracking for admin multi-step
user_states: Dict[int, Dict] = {}

# ==================== NATIVE REQUEST KEYBOARD ====================
def main_finder_keyboard(user_id: int = 0):
    """
    Original, High-Tech Custom Layout for Tonmoy Developer:
    - Row 1: ⚡ ইউজার আইডি স্ক্যানার (Primary Blue)
    - Row 2: 🚀 পাবলিক গ্রুপ ফাইন্ডার (Success Green) | 🛡️ প্রাইভেট গ্রুপ আইডি (Danger Red)
    - Row 3: 📢 পাবলিক চ্যানেল ইনফো (Success Green) | 🔐 সিক্রেট চ্যানেল আইডি (Danger Red)
    - Row 4: 🤖 অল বট ইন্সপেক্টর (Primary Blue) | 👑 ভিআইপি প্রিমিয়াম মেম্বার (Success Green)
    - Row 5: 👤 আমার প্রোফাইল ও আইডি (Primary Blue) | 📊 লাইভ স্ট্যাটাস (Success Green)
    """
    keyboard_buttons = [
        # Row 1: User Scanner
        [
            {
                "text": "⚡ ইউজার আইডি স্ক্যানার",
                "request_users": {
                    "request_id": 1,
                    "user_is_bot": False,
                    "max_quantity": 5,
                    "request_name": True,
                    "request_username": True
                },
                "style": "primary"
            }
        ],
        # Row 2: Groups (Public & Private)
        [
            {
                "text": "🚀 পাবলিক গ্রুপ ফাইন্ডার",
                "request_chat": {
                    "request_id": 2,
                    "chat_is_channel": False,
                    "chat_is_public": True,
                    "request_title": True,
                    "request_username": True
                },
                "style": "success"
            },
            {
                "text": "🛡️ প্রাইভেট গ্রুপ আইডি",
                "request_chat": {
                    "request_id": 3,
                    "chat_is_channel": False,
                    "chat_is_public": False,
                    "request_title": True
                },
                "style": "danger"
            }
        ],
        # Row 3: Channels (Public & Private)
        [
            {
                "text": "📢 পাবলিক চ্যানেল ইনফো",
                "request_chat": {
                    "request_id": 4,
                    "chat_is_channel": True,
                    "chat_is_public": True,
                    "request_title": True,
                    "request_username": True
                },
                "style": "success"
            },
            {
                "text": "🔐 সিক্রেট চ্যানেল আইডি",
                "request_chat": {
                    "request_id": 5,
                    "chat_is_channel": True,
                    "chat_is_public": False,
                    "request_title": True
                },
                "style": "danger"
            }
        ],
        # Row 4: Bots & VIP Premium Members
        [
            {
                "text": "🤖 অল বট ইন্সপেক্টর",
                "request_users": {
                    "request_id": 6,
                    "user_is_bot": True,
                    "max_quantity": 5,
                    "request_name": True,
                    "request_username": True
                },
                "style": "primary"
            },
            {
                "text": "👑 ভিআইপি প্রিমিয়াম মেম্বার",
                "request_users": {
                    "request_id": 7,
                    "user_is_premium": True,
                    "max_quantity": 5,
                    "request_name": True,
                    "request_username": True
                },
                "style": "success"
            }
        ],
        # Row 5: Self Info & Stats
        [
            {
                "text": "👤 আমার প্রোফাইল ও আইডি",
                "style": "primary"
            },
            {
                "text": "📊 লাইভ স্ট্যাটাস",
                "style": "success"
            }
        ]
    ]

    if user_id == ADMIN_ID:
        keyboard_buttons.append([{"text": "⚙️ Admin Dashboard", "style": "danger"}])

    return {
        "keyboard": keyboard_buttons,
        "resize_keyboard": True
    }

# ==================== FORCE SUBSCRIBE VERIFICATION ====================
def check_user_force_sub(bot: TelegramBot, user_id: int) -> (bool, List[str]):
    if user_id == ADMIN_ID:
        return True, []

    channels = get_force_channels()
    if not channels:
        return True, []

    missing = []
    for ch in channels:
        chk = bot.get_chat_member(ch, user_id)
        if chk.get("ok"):
            status = chk["result"].get("status")
            if status in ["left", "kicked"]:
                missing.append(ch)
    return (len(missing) == 0), missing

def build_force_sub_prompt(missing_channels: List[str]):
    text = (
        "👋 <b>আসসালামু আলাইকুম!</b>\n\n"
        "✨ আমাদের <b>আইডি ও ইনফো ফাইন্ডার বটটি</b> ব্যবহার করার পূর্বে আপনাকে অবশ্যই আমাদের চ্যানেলে যুক্ত হতে হবে।\n\n"
        "👇 <b>নিচের চ্যানেলে জয়েন করে '✅ জয়েন করেছি / Verify' বাটনে চাপ দিন:</b>"
    )
    buttons = []
    for ch in missing_channels:
        clean_un = ch.replace("@", "")
        buttons.append([{"text": f"📢 জয়েন করুন: {ch}", "url": f"https://t.me/{clean_un}", "style": "primary"}])
    buttons.append([{"text": "✅ জয়েন করেছি / Verify", "callback_data": "verify_fsub", "style": "success"}])
    return text, {"inline_keyboard": buttons}

# ==================== MESSAGE HANDLER ====================
def handle_message(bot: TelegramBot, msg: Dict, bot_username: str):
    chat_id = msg["chat"]["id"]
    chat_type = msg["chat"].get("type", "private")
    user_id = msg["from"]["id"]
    text = msg.get("text", "").strip()
    first_name = msg["from"].get("first_name", "User")
    username = msg["from"].get("username", "")

    # Save/Update user
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)", (user_id, first_name, username))
    conn.commit()
    conn.close()

    # Cancel command
    if text == "/cancel":
        if user_id in user_states:
            del user_states[user_id]
            bot.send_message(chat_id, "❌ কার্যক্রম বাতিল করা হয়েছে।", reply_markup=main_finder_keyboard(user_id))
            return

    # Admin State Handler
    if chat_type == "private" and user_id in user_states and user_id == ADMIN_ID:
        state = user_states[user_id]
        step = state.get("step")

        if step == "waiting_for_broadcast":
            del user_states[user_id]
            bot.send_message(chat_id, "⏳ <b>ব্রডকাস্ট শুরু হয়েছে... অপেক্ষা করুন।</b>")

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT user_id FROM users")
            all_users = c.fetchall()
            conn.close()

            success_cnt = 0
            fail_cnt = 0
            for (uid,) in all_users:
                res = bot.send_message(uid, f"📢 <b>অফিসিয়াল নোটিশ:</b>\n\n{text}")
                if res.get("ok"):
                    success_cnt += 1
                else:
                    fail_cnt += 1
                time.sleep(0.04)

            bot.send_message(
                chat_id,
                f"✅ <b>ব্রডকাস্ট সম্পন্ন!</b>\n\n👥 মোট ইউজার: {len(all_users)}\n📤 সফল: {success_cnt}\n🚫 ব্লক/ব্যর্থ: {fail_cnt}",
                reply_markup=main_finder_keyboard(user_id)
            )
            return

        elif step == "waiting_for_fsub_add":
            del user_states[user_id]
            entries = text.replace(",", "\n").split("\n")
            added = []
            for e in entries:
                e = e.strip()
                if e:
                    add_force_channel(e)
                    added.append(e)

            bot.send_message(
                chat_id,
                f"✅ সফলভাবে {len(added)}টি ফোর্স চ্যানেল যোগ করা হয়েছে!\n\n" + "\n".join([f"• {c}" for c in added]),
                reply_markup=main_finder_keyboard(user_id)
            )
            send_admin_panel(bot, chat_id)
            return

    # Check Force Subscribe for normal users in private chat
    if chat_type == "private" and user_id != ADMIN_ID:
        is_subbed, missing = check_user_force_sub(bot, user_id)
        if not is_subbed:
            fs_text, fs_markup = build_force_sub_prompt(missing)
            bot.send_message(chat_id, fs_text, reply_markup=fs_markup)
            return

    # ==================== HANDLE USERS SHARED (Peer Picked) ====================
    # When user picks someone via "👤 ইউজার খুঁজুন", "🤖 Bots", or "Premium ⭐"
    if "users_shared" in msg:
        shared = msg["users_shared"]
        req_id = shared.get("request_id", 0)
        users_list = shared.get("users", [])

        # Label based on request_id
        card_titles = {
            1: "ইউজার তথ্য 👤",
            6: "বট তথ্য 🤖",
            7: "প্রিমিয়াম ইউজার তথ্য ⭐"
        }
        c_title_label = card_titles.get(req_id, "ইউজার তথ্য 👤")
        is_premium_req = (req_id == 7)

        increment_search_count(user_id)

        for u in users_list:
            s_uid = u.get("user_id")
            s_first = u.get("first_name", "")
            s_last = u.get("last_name", "")
            s_uname = u.get("username", "")

            prem_str = "✅ হ্যাঁ" if is_premium_req else "❌ না"
            profile_url = f"https://t.me/{s_uname}" if s_uname else f"tg://user?id={s_uid}"

            card = (
                "┏─━─━─━─━─━─━─━─━─━─━─━─━─━─┓\n"
                f"  <b>{c_title_label}</b>\n"
                "┗─━─━─━─━─━─━─━─━─━─━─━─━─━─┛\n"
                f"  📛 <b>নাম ➔</b> {s_first if s_first else 'N/A'}\n"
                f"  📇 <b>পদবি ➔</b> {s_last if s_last else 'N/A'}\n"
                f"  🔗 <b>ইউজারনেম ➔</b> @{s_uname if s_uname else 'N/A'}\n"
                f"  🆔 <b>ইউজার আইডি ➔</b> <code>{s_uid}</code>\n"
                f"  💎 <b>প্রিমিয়াম ➔</b> {prem_str}\n"
                f"  🌐 <b>প্রোফাইল লিংক ➔</b> {profile_url}"
            )
            bot.send_message(chat_id, card, reply_markup=main_finder_keyboard(user_id))
        return

    # ==================== HANDLE CHAT SHARED (Group/Channel Picked) ====================
    # When user picks via Public/Private Group or Channel
    if "chat_shared" in msg:
        shared = msg["chat_shared"]
        req_id = shared.get("request_id", 0)
        c_id = shared.get("chat_id")
        c_title = shared.get("title", "")
        c_uname = shared.get("username", "")

        chat_labels = {
            2: "পাবলিক গ্রুপ তথ্য 👥",
            3: "প্রাইভেট গ্রুপ তথ্য 👥",
            4: "পাবলিক চ্যানেল তথ্য 📢",
            5: "প্রাইভেট চ্যানেল তথ্য 📢"
        }
        chat_type_str = chat_labels.get(req_id, "চ্যাট তথ্য 📁")

        # Telegram channels & supergroups use -100 prefix
        formatted_id = c_id
        if not str(formatted_id).startswith("-100") and (req_id in [4, 5, 2, 3]):
            formatted_id = f"-100{abs(c_id)}"

        increment_search_count(user_id)

        link_str = f"https://t.me/{c_uname}" if c_uname else "N/A"
        uname_str = f"@{c_uname}" if c_uname else "N/A"

        card = (
            "┏─━─━─━─━─━─━─━─━─━─━─━─━─━─┓\n"
            f"  <b>{chat_type_str}</b>\n"
            "┗─━─━─━─━─━─━─━─━─━─━─━─━─━─┛\n"
            f"  📛 <b>টাইটেল ➔</b> {c_title if c_title else 'N/A'}\n"
            f"  🔗 <b>ইউজারনেম ➔</b> {uname_str}\n"
            f"  🆔 <b>চ্যাট আইডি ➔</b> <code>{formatted_id}</code>\n"
            f"  🌐 <b>লিংক ➔</b> {link_str}"
        )
        bot.send_message(chat_id, card, reply_markup=main_finder_keyboard(user_id))
        return

    # ==================== HANDLE FORWARDED MESSAGES ====================
    # User forwards any message from any channel, group or user to find their ID
    if "forward_origin" in msg or "forward_from" in msg or "forward_from_chat" in msg:
        increment_search_count(user_id)

        f_type = "অজানা"
        f_name = "N/A"
        f_id = "N/A"
        f_un = ""

        if "forward_from" in msg:
            # Forwarded from a user or bot
            u = msg["forward_from"]
            f_type = "🤖 বট" if u.get("is_bot") else "👤 ব্যবহারকারী"
            f_name = u.get("first_name", "") + " " + u.get("last_name", "")
            f_id = u.get("id")
            f_un = u.get("username", "")

        elif "forward_from_chat" in msg:
            # Forwarded from a channel or group
            ch = msg["forward_from_chat"]
            f_type = "📢 চ্যানেল" if ch.get("type") == "channel" else "👥 গ্রুপ"
            f_name = ch.get("title", "")
            f_id = ch.get("id")
            f_un = ch.get("username", "")

        elif "forward_origin" in msg:
            # New Telegram Bot API forward_origin structure
            orig = msg["forward_origin"]
            o_type = orig.get("type")

            if o_type == "user":
                u = orig.get("sender_user", {})
                f_type = "👤 ব্যবহারকারী"
                f_name = u.get("first_name", "") + " " + u.get("last_name", "")
                f_id = u.get("id")
                f_un = u.get("username", "")

            elif o_type == "channel":
                ch = orig.get("chat", {})
                f_type = "📢 চ্যানেল"
                f_name = ch.get("title", "")
                f_id = ch.get("id")
                f_un = ch.get("username", "")

            elif o_type == "chat":
                ch = orig.get("sender_chat", {})
                f_type = "👥 গ্রুপ"
                f_name = ch.get("title", "")
                f_id = ch.get("id")
                f_un = ch.get("username", "")

            elif o_type == "hidden_user":
                f_type = "👤 প্রাইভেট ইউজার (Hidden)"
                f_name = orig.get("sender_user_name", "গোপন ইউজার")
                f_id = "প্রাইভেসি সেটিংয়ের কারণে আইডি গোপন রাখা হয়েছে।"

        card = (
            "╭━━━━━━━━━━━━━━━━━━━━━╮\n"
            "   📩 <b>ফরওয়ার্ডকৃত মেসেজ তথ্য</b>\n"
            "╰━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            f"📌 <b>টাইপ:</b> {f_type}\n"
            f"🏷️ <b>নাম / শিরোনাম:</b> {f_name.strip()}\n"
            f"🔢 <b>নিউমেরিক আইডি:</b> <code>{f_id}</code>\n"
        )
        if f_un:
            card += f"👤 <b>ইউজারনেম:</b> @{f_un}\n"

        card += "━━━━━━━━━━━━━━━━━━━━\n💡 <i>আইডি নম্বরে ট্যাপ করলেই স্বয়ংক্রিয়ভাবে কপি হয়ে যাবে!</i>"
        bot.send_message(chat_id, card, reply_markup=main_finder_keyboard(user_id))
        return

    # ==================== COMMANDS ====================
    if text == "/start" or text.startswith("/start"):
        welcome = (
            f"👋 <b>আসসালামু আলাইকুম, {first_name}!</b>\n\n"
            "✨ <b>Ultra ID & Info Finder Bot</b>-এ আপনাকে স্বাগতম!\n\n"
            "🚀 <b>এই বট দিয়ে যা যা করতে পারবেন:</b>\n"
            "• 👤 যেকোনো ইউজারের আইডি ও তথ্য বের করা\n"
            "• 🌐 পাবলিক ও প্রাইভেট গ্রুপের সঠিক আইডি (-100...) বের করা\n"
            "• 📢 পাবলিক ও প্রাইভেট চ্যানেলের আইডি বের করা\n"
            "• 🤖 যেকোনো টেলিগ্রাম বটের আইডি বের করা\n"
            "• ⭐ টেলিগ্রাম প্রিমিয়াম ইউজার ডিটেক্ট করা\n"
            "• 📩 যেকোনো মেসেজ <b>ফরওয়ার্ড (Forward)</b> করলেই তার সোর্স আইডি বের করা!\n\n"
            "👇 <b>নিচের রঙিন বাটনগুলোতে চাপ দিয়ে সহজেই যেকোনো আইডি খুঁজে নিন:</b>"
        )
        bot.send_message(chat_id, welcome, reply_markup=main_finder_keyboard(user_id))

    elif text in ["/id", "/me", "👤 আমার প্রোফাইল ও আইডি", "আমার আইডি"]:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT searches_count FROM users WHERE user_id = ?", (user_id,))
        s_res = c.fetchone()
        user_searches = s_res[0] if s_res else 0
        conn.close()

        me_card = (
            "┏─━─━─━─━─━─━─━─━─━─━─━─━─━─┓\n"
            "  <b>USER INFO 👤</b>\n"
            "┗─━─━─━─━─━─━─━─━─━─━─━─━─━─┛\n"
            f"  📛 <b>First Name:</b> {first_name}\n"
            f"  📇 <b>Last Name:</b> {msg['from'].get('last_name', 'N/A')}\n"
            f"  🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"  🔗 <b>Username:</b> @{username if username else 'N/A'}\n"
            f"  💎 <b>Premium:</b> {'✅' if msg['from'].get('is_premium') else '❌'}\n"
            f"  🌐 <b>Profile:</b> t.me/{username if username else user_id}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 <b>মোট সার্চ করেছেন:</b> {user_searches} বার"
        )
        bot.send_message(chat_id, me_card, reply_markup=main_finder_keyboard(user_id))

    elif text in ["/stats", "📊 লাইভ স্ট্যাটাস"]:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        u_count = c.fetchone()[0]
        c.execute("SELECT SUM(searches_count) FROM users")
        s_count = c.fetchone()[0] or 0
        conn.close()

        channel_un = get_setting("channel_username", CHANNEL_USERNAME)

        stats_card = (
            "╭━━━━━━━━━━━━━━━━━━━━━╮\n"
            "   📊 <b>বট লাইভ স্ট্যাটিস্টিক্স</b>\n"
            "╰━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            f"👥 <b>মোট ব্যবহারকারী:</b> {u_count} জন\n"
            f"🔍 <b>মোট আইডি স্ক্যান:</b> {s_count} বার\n"
            "⚡ <b>সার্ভার স্ট্যাটাস:</b> সক্রিয় (100% Online)\n"
            f"📢 <b>অফিসিয়াল চ্যানেল:</b> @{channel_un}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>TeleScan Pro — Tonmoy Developer</i>"
        )
        bot.send_message(chat_id, stats_card, reply_markup=main_finder_keyboard(user_id))

    elif (text in ["/admin", "⚙️ Admin Dashboard", "Admin Panel"]) and user_id == ADMIN_ID:
        send_admin_panel(bot, chat_id)

    else:
        # If user types any random text or username
        hint = (
            "💡 <b>টিপস:</b>\n"
            "• যেকোনো ইউজার, গ্রুপ বা চ্যানেলের আইডি পেতে নিচের <b>রঙিন বাটনগুলোতে</b> ক্লিক করুন।\n"
            "• অথবা যেকোনো চ্যানেল/গ্রুপের একটি মেসেজ এই বটে <b>Forward</b> করে পাঠিয়ে দিন, বট সাথে সাথে তার সঠিক আইডি জানিয়ে দেবে!"
        )
        bot.send_message(chat_id, hint, reply_markup=main_finder_keyboard(user_id))

def send_admin_panel(bot: TelegramBot, chat_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    u_count = c.fetchone()[0]
    c.execute("SELECT SUM(searches_count) FROM users")
    s_count = c.fetchone()[0] or 0
    conn.close()

    f_channels = get_force_channels()
    f_list = "\n".join([f"  {idx}. {ch}" for idx, ch in enumerate(f_channels, 1)]) if f_channels else "  <i>(কোনো চ্যানেল নেই)</i>"

    admin_msg = (
        "👑 <b>ID Finder Bot — অ্যাডমিন প্যানেল</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>মোট ব্যবহারকারী:</b> {u_count} জন\n"
        f"🔍 <b>মোট আইডি সার্চ:</b> {s_count} বার\n\n"
        f"🛡️ <b>ফোর্স সাবস্ক্রাইব চ্যানেলসমূহ ({len(f_channels)} টি):</b>\n{f_list}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <i>নিচের অপশনগুলো দিয়ে নিয়ন্ত্রণ করুন:</i>"
    )

    markup = {
        "inline_keyboard": [
            [{"text": "📢 ব্রডকাস্ট মেসেজ পাঠান", "callback_data": "adm_broadcast", "style": "primary"}],
            [{"text": "➕ ফোর্স চ্যানেল যোগ করুন", "callback_data": "adm_add_fsub", "style": "success"}],
            [{"text": "🗑️ ফোর্স চ্যানেল রিমুভ", "callback_data": "adm_del_fsub", "style": "danger"}],
            [{"text": "🔄 রিফ্রেশ", "callback_data": "adm_refresh", "style": "primary"}]
        ]
    }
    bot.send_message(chat_id, admin_msg, reply_markup=markup)

# ==================== CALLBACK HANDLER ====================
def handle_callback_query(bot: TelegramBot, cb: Dict, bot_username: str):
    cb_id = cb["id"]
    from_user = cb["from"]
    user_id = from_user["id"]
    data = cb.get("data", "")
    message = cb.get("message")
    if not message:
        bot.answer_callback(cb_id)
        return

    chat_id = message["chat"]["id"]

    # Verify force subscribe button
    if data == "verify_fsub":
        is_subbed, missing = check_user_force_sub(bot, user_id)
        if is_subbed:
            bot.answer_callback(cb_id, "✅ ভেরিফিকেশন সফল হয়েছে! স্বাগতম!", show_alert=True)
            welcome = (
                f"👋 <b>আসসালামু আলাইকুম, {from_user.get('first_name', 'User')}!</b>\n\n"
                "✨ <b>Ultra ID & Info Finder Bot</b>-এ আপনাকে স্বাগতম!\n\n"
                "👇 <b>নিচের রঙিন বাটনগুলোতে চাপ দিয়ে সহজেই যেকোনো আইডি খুঁজে নিন:</b>"
            )
            bot.send_message(chat_id, welcome, reply_markup=main_finder_keyboard(user_id))
        else:
            bot.answer_callback(cb_id, "⚠️ আপনি এখনো সবকটি চ্যানেলে জয়েন করেননি! দয়া করে জয়েন করুন।", show_alert=True)
        return

    # Admin Panel Callbacks
    if data.startswith("adm_") and user_id == ADMIN_ID:
        if data == "adm_broadcast":
            user_states[user_id] = {"step": "waiting_for_broadcast"}
            bot.answer_callback(cb_id)
            bot.send_message(
                chat_id,
                "📢 <b>সকল ব্যবহারকারীদের জন্য ব্রডকাস্ট মেসেজ পাঠান:</b>\n\nমেসেজটি লিখে পাঠান (বাতিল করতে /cancel লিখুন)।"
            )
            return

        elif data == "adm_add_fsub":
            user_states[user_id] = {"step": "waiting_for_fsub_add"}
            bot.answer_callback(cb_id)
            bot.send_message(
                chat_id,
                "🛡️ <b>ফোর্স চ্যানেল যোগ করুন:</b>\n\nইউজারনেম পাঠান (যেমন: @TonmoyDeveloperBD24)। কমা দিয়ে একাধিক পাঠাতে পারেন।"
            )
            return

        elif data == "adm_del_fsub":
            f_channels = get_force_channels()
            bot.answer_callback(cb_id)
            if not f_channels:
                bot.send_message(chat_id, "ℹ️ কোনো ফোর্স চ্যানেল নেই।")
                return

            buttons = []
            for ch in f_channels:
                buttons.append([{"text": f"❌ মুছুন: {ch}", "callback_data": f"adm_rm:{ch}", "style": "danger"}])
            buttons.append([{"text": "🔙 ব্যাক", "callback_data": "adm_refresh", "style": "primary"}])

            bot.send_message(chat_id, "🗑️ কোন চ্যানেলটি মুছতে চান সিলেক্ট করুন:", reply_markup={"inline_keyboard": buttons})
            return

        elif data.startswith("adm_rm:"):
            ch = data.replace("adm_rm:", "")
            remove_force_channel(ch)
            bot.answer_callback(cb_id, f"✅ {ch} মুছে ফেলা হয়েছে!", show_alert=True)
            send_admin_panel(bot, chat_id)
            return

        elif data == "adm_refresh":
            bot.answer_callback(cb_id, "🔄 রিফ্রেশ করা হয়েছে!")
            send_admin_panel(bot, chat_id)
            return

# ==================== RUN BOT ====================
def run_bot():
    init_db()

    # Start health check server for 24/7 Render keep-alive
    if "PORT" in os.environ or os.getenv("RENDER"):
        t = threading.Thread(target=start_render_health_server, daemon=True)
        t.start()
        logger.info("Render background health check server started.")

    bot = TelegramBot(BOT_TOKEN)

    logger.info("Connecting to Telegram Bot API...")
    me = bot.get_me()
    if not me.get("ok"):
        logger.error(f"Failed to connect: {me}")
        print("\n❌ ত্রুটি: BOT_TOKEN সঠিক নয়! অনুগ্রহ করে @BotFather থেকে পাওয়া টোকেন বসান।\n")
        return

    bot_info = me["result"]
    bot_username = bot_info["username"]

    print(f"\n=======================================================")
    print(f"🚀 Telegram ID & Info Finder Bot চালু হয়েছে: @{bot_username}")
    print(f"🎨 ফুল কালার বাটন ও Peer Request ফিচার সক্রিয়!")
    print(f"=======================================================\n")

    offset = 0
    while True:
        try:
            updates_res = bot.request("getUpdates", {
                "offset": offset,
                "timeout": 20,
                "allowed_updates": ["message", "callback_query"]
            })
            if not updates_res.get("ok"):
                time.sleep(2)
                continue

            updates = updates_res.get("result", [])
            for update in updates:
                offset = update["update_id"] + 1

                if "message" in update:
                    handle_message(bot, update["message"], bot_username)
                elif "callback_query" in update:
                    handle_callback_query(bot, update["callback_query"], bot_username)

        except Exception as e:
            logger.error(f"Polling loop exception: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_bot()