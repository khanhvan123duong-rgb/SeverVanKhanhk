#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# TELEGRAM BOT - SPAM OTP VIP - VAN KHANH & MINH THU
# Server: https://vkhanhxhthuminhthu.onrender.com
# ============================================================

import os, json, time, hashlib, threading, logging
import requests
from flask import Flask, render_template_string

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN  = "7698662964:AAHTjfzdksHrtJ6asdrBAc_5zPkWwwBYOCk"
ADMIN_IDS  = [8401914033]
SERVER_URL = "https://vkhanhxhthuminhthu.onrender.com"
SELF_URL   = "https://vkhanhxhthuminhthu.onrender.com"
BOT_URL    = f"https://api.telegram.org/bot{BOT_TOKEN}"
FOOTER     = "\n\n──────────────────────\n📞 Telegram Hỗ Trợ - Báo Lỗi @vkhanh3010"

# Giới hạn số lần spam
LIMIT_NORMAL = 5    # Không VIP: 1-5
LIMIT_VIP    = 30   # Có VIP:    1-30

# ============================================================
# IMPORT OTP FUNCTIONS FROM TOOL
# ============================================================
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tool as _tool
OTP_FUNCTIONS = _tool.OTP_FUNCTIONS

# ============================================================
# DATA STORAGE (in-memory + JSON file)
# ============================================================
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_data.json")

def _load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {"users": {}, "admins": list(ADMIN_IDS), "seen_users": []}

_data = _load_data()

def _save():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def _get_admins():
    return set(_data.get("admins", list(ADMIN_IDS)))

def _get_seen():
    return set(str(x) for x in _data.get("seen_users", []))

# ============================================================
# HWID GENERATION (SHA256 of Telegram user_id)
# ============================================================
def make_hwid(user_id: int) -> str:
    return hashlib.sha256(str(user_id).encode()).hexdigest()[:20].upper()

# ============================================================
# SERVER API CALLS
# ============================================================
def api_verify(key: str, hwid: str) -> dict:
    try:
        r = requests.post(f"{SERVER_URL}/api/verify",
                          json={"key": key, "hwid": hwid}, timeout=15)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def api_getkey(hwid: str) -> dict:
    try:
        r = requests.get(f"{SERVER_URL}/api/getkey",
                         params={"hwid": hwid}, timeout=15)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def api_submit_device(hwid: str) -> dict:
    try:
        r = requests.post(f"{SERVER_URL}/api/submit_device_request",
                          json={"device_id": hwid, "val": "1",
                                "unit": "ngay", "note": "Bot Telegram"},
                          timeout=15)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def api_check_device(hwid: str) -> dict:
    try:
        r = requests.post(f"{SERVER_URL}/api/check-device",
                          json={"device_id": hwid}, timeout=15)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ============================================================
# USER HELPERS
# ============================================================
def get_user(user_id: int) -> dict:
    return _data.get("users", {}).get(str(user_id), {})

def is_activated(user_id: int):
    """Returns (bool, user_dict)"""
    u = get_user(user_id)
    if not u or not u.get("activated"):
        return False, u
    is_perm = u.get("is_permanent", False)
    if is_perm:
        return True, u
    expiry = u.get("expiry", 0)
    if expiry and expiry > 0 and time.time() < expiry:
        return True, u
    if not expiry and u.get("server_verified"):
        return True, u
    return False, u

def is_vip(user_id: int) -> bool:
    """Kiểm tra user có VIP hợp lệ không (lưu trong bot_data.json)."""
    u = get_user(user_id)
    if not u:
        return False
    if not u.get("vip"):
        return False
    if u.get("vip_permanent"):
        return True
    vip_expiry = u.get("vip_expiry", 0)
    if vip_expiry and vip_expiry > 0 and time.time() < vip_expiry:
        return True
    return False

def is_banned(user_id: int) -> bool:
    """Kiểm tra user có bị cấm không."""
    u = get_user(user_id)
    return bool(u.get("banned", False))

def get_sms_limit(user_id: int) -> int:
    """Trả về giới hạn số lần spam của user."""
    if is_vip(user_id):
        return LIMIT_VIP
    return LIMIT_NORMAL

def format_expiry(user_id: int) -> str:
    u = get_user(user_id)
    if not u:
        return "N/A"
    if u.get("is_permanent"):
        return "♾️ Vĩnh viễn"
    expiry = u.get("expiry", 0)
    if not expiry or expiry <= 0:
        return "Đã duyệt (không xác định hạn)"
    left = expiry - time.time()
    if left <= 0:
        return "⚠️ Hết hạn"
    d, rem = divmod(int(left), 86400)
    h, rem2 = divmod(rem, 3600)
    m = rem2 // 60
    parts = []
    if d: parts.append(f"{d} ngày")
    if h: parts.append(f"{h} giờ")
    if m: parts.append(f"{m} phút")
    return " ".join(parts) or "< 1 phút"

def format_vip_expiry(user_id: int) -> str:
    u = get_user(user_id)
    if not u or not u.get("vip"):
        return "❌ Không có VIP"
    if u.get("vip_permanent"):
        return "♾️ VIP Vĩnh Viễn"
    vip_expiry = u.get("vip_expiry", 0)
    if not vip_expiry or vip_expiry <= 0:
        return "❌ VIP hết hạn"
    left = vip_expiry - time.time()
    if left <= 0:
        return "⚠️ VIP hết hạn"
    d, rem = divmod(int(left), 86400)
    h, rem2 = divmod(rem, 3600)
    m = rem2 // 60
    parts = []
    if d: parts.append(f"{d} ngày")
    if h: parts.append(f"{h} giờ")
    if m: parts.append(f"{m} phút")
    return "💎 VIP còn: " + (" ".join(parts) or "< 1 phút")

def detect_carrier(phone: str) -> str:
    p = phone.lstrip('+').strip()
    if p.startswith('84'):
        p = '0' + p[2:]
    if len(p) < 10:
        return "Không xác định"
    pre3 = p[:3]
    viettel    = {'032','033','034','035','036','037','038','039','086','096','097','098'}
    mobifone   = {'070','076','077','078','079','089','090','093'}
    vinaphone  = {'081','082','083','084','085','088','091','094'}
    vietnamob  = {'052','056','058','092'}
    gmobile    = {'059','099'}
    if pre3 in viettel:   return "Viettel"
    if pre3 in mobifone:  return "Mobifone"
    if pre3 in vinaphone: return "Vinaphone"
    if pre3 in vietnamob: return "Vietnamobile"
    if pre3 in gmobile:   return "Gmobile"
    return "Không xác định"

# ============================================================
# TELEGRAM API HELPERS
# ============================================================
def _tg(method: str, **kwargs) -> dict:
    try:
        r = requests.post(f"{BOT_URL}/{method}", json=kwargs, timeout=30)
        return r.json()
    except Exception:
        return {}

def send(chat_id, text, reply_markup=None, parse_mode="HTML",
         disable_web_page_preview=True) -> dict:
    kw = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode,
          "disable_web_page_preview": disable_web_page_preview}
    if reply_markup:
        kw["reply_markup"] = reply_markup
    return _tg("sendMessage", **kw)

def edit_msg(chat_id, msg_id, text, reply_markup=None, parse_mode="HTML") -> dict:
    kw = {"chat_id": chat_id, "message_id": msg_id, "text": text,
          "parse_mode": parse_mode, "disable_web_page_preview": True}
    if reply_markup:
        kw["reply_markup"] = reply_markup
    return _tg("editMessageText", **kw)

def answer_cb(cb_id, text=None, alert=False) -> dict:
    kw = {"callback_query_id": cb_id}
    if text:
        kw["text"] = text
        kw["show_alert"] = alert
    return _tg("answerCallbackQuery", **kw)

def notify_admins(text: str, exclude_id: int = None):
    for aid in _get_admins():
        if aid != exclude_id:
            try:
                send(int(aid), text)
            except Exception:
                pass

# ============================================================
# KEYBOARDS
# ============================================================
def kb_activation():
    return {"inline_keyboard": [
        [{"text": "🔑 Nhập Key Kích Hoạt",             "callback_data": "act_key"}],
        [{"text": "📲 Gửi HWID Xin Admin Duyệt",       "callback_data": "act_submit"}],
        [{"text": "🔗 Lấy Link Key Miễn Phí (2/ngày)", "callback_data": "act_link"}],
        [{"text": "✅ Kiểm Tra Đã Được Admin Duyệt",   "callback_data": "act_check"}],
    ]}

def kb_main():
    return {"inline_keyboard": [
        [{"text": "📱 Hướng dẫn /sms",         "callback_data": "help_sms"}],
        [{"text": "👤 Thông tin tài khoản",     "callback_data": "my_info"}],
        [{"text": "🔄 Kiểm tra hạn dùng",      "callback_data": "act_check"}],
    ]}

# ============================================================
# STATE MACHINE (per-user multi-step input)
# ============================================================
_user_state: dict = {}   # {user_id: str}

def set_state(user_id: int, state: str):
    _user_state[user_id] = state

def get_state(user_id: int) -> str:
    return _user_state.get(user_id, "")

def clear_state(user_id: int):
    _user_state.pop(user_id, None)

# ============================================================
# SPAM RUNNER
# ============================================================
def _safe_call(fn, sdt: str) -> bool:
    try:
        fn(sdt)
        return True
    except Exception:
        return False

def run_spam(sdt: str, rounds: int):
    """Run all OTP_FUNCTIONS <rounds> times. Returns (ok, fail)."""
    total_ok = total_fail = 0
    for _ in range(rounds):
        results = []
        lock = threading.Lock()
        def _worker(fn, phone, res, lk):
            ok = _safe_call(fn, phone)
            with lk:
                res.append(ok)
        threads = [threading.Thread(target=_worker, args=(fn, sdt, results, lock), daemon=True)
                   for fn in OTP_FUNCTIONS]
        for t in threads: t.start()
        for t in threads: t.join()
        ok = sum(1 for r in results if r)
        total_ok += ok
        total_fail += len(results) - ok
    return total_ok, total_fail

# ============================================================
# COMMAND HANDLERS
# ============================================================

def cmd_start(msg: dict):
    user_id   = msg["from"]["id"]
    uid       = str(user_id)
    first_name= msg["from"].get("first_name", "Bạn")
    username  = msg["from"].get("username", "")
    chat_id   = msg["chat"]["id"]

    # Kiểm tra bị cấm
    if is_banned(user_id):
        return send(chat_id, "🚫 Tài khoản của bạn đã bị cấm sử dụng bot." + FOOTER)

    # Upsert user record
    _data.setdefault("users", {}).setdefault(uid, {
        "first_name": first_name, "username": username,
        "first_seen": time.time(), "activated": False
    })
    _data["users"][uid]["first_name"] = first_name
    _data["users"][uid]["username"]   = username
    _save()

    # One-time new-user notification
    seen = _get_seen()
    if uid not in seen:
        _data.setdefault("seen_users", []).append(uid)
        _save()
        hwid = make_hwid(user_id)
        notify_admins(
            f"🆕 <b>Người dùng mới!</b>\n"
            f"👤 Tên: {first_name}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📛 Username: @{username or 'N/A'}\n"
            f"🔑 HWID: <code>{hwid}</code>",
            exclude_id=user_id if user_id in _get_admins() else None
        )

    act, uinfo = is_activated(user_id)
    hwid = make_hwid(user_id)
    vip_status = is_vip(user_id)
    limit = get_sms_limit(user_id)

    if not act:
        txt = (
            f"👋 Xin chào <b>{first_name}</b>!\n\n"
            f"🔒 Bạn cần <b>kích hoạt tài khoản</b> trước khi sử dụng bot.\n\n"
            f"🆔 HWID của bạn:\n<code>{hwid}</code>\n\n"
            f"Chọn phương thức kích hoạt bên dưới:"
            f"{FOOTER}"
        )
        send(chat_id, txt, reply_markup=kb_activation())
    else:
        key_disp = uinfo.get("key","N/A")
        if key_disp == "__da_duyet__": key_disp = "Duyệt HWID"
        vip_line = f"💎 VIP: {format_vip_expiry(user_id)}" if vip_status else "💎 VIP: ❌ Chưa có"
        txt = (
            f"✅ Xin chào <b>{first_name}</b>! Tài khoản đã kích hoạt.\n\n"
            f"🔑 Key: <code>{key_disp}</code>\n"
            f"⏳ Hạn dùng: {format_expiry(user_id)}\n"
            f"{vip_line}\n"
            f"📊 Giới hạn SMS: 1–{limit} lần\n\n"
            f"▸ /sms [SĐT] [Số lần] — Spam OTP\n"
            f"▸ /help — Hướng dẫn\n"
            f"▸ /info — Thông tin tài khoản"
            f"{FOOTER}"
        )
        send(chat_id, txt, reply_markup=kb_main())


def cmd_help(msg: dict):
    user_id = msg["from"]["id"]
    chat_id = msg["chat"]["id"]

    if is_banned(user_id):
        return send(chat_id, "🚫 Tài khoản của bạn đã bị cấm sử dụng bot." + FOOTER)

    act, _  = is_activated(user_id)
    if not act:
        return send(chat_id,
            "🔒 Bạn chưa kích hoạt! Dùng /start để kích hoạt." + FOOTER,
            reply_markup=kb_activation())

    vip_status = is_vip(user_id)
    limit = get_sms_limit(user_id)

    txt = (
        "📖 <b>HƯỚNG DẪN SỬ DỤNG BOT</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📱 <b>Lệnh chính:</b>\n"
        "▸ /sms [SĐT] [Số lần] — Gửi OTP spam\n"
        f"  Ví dụ: <code>/sms 0912345678 3</code>\n\n"
        "▸ /info — Thông tin tài khoản\n"
        "▸ /help — Hướng dẫn\n"
        "▸ /start — Menu chính\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>Giới hạn:</b>\n"
        f"• Không VIP: tối đa <b>{LIMIT_NORMAL} lần</b> mỗi lần gửi\n"
        f"• Có VIP 💎: tối đa <b>{LIMIT_VIP} lần</b> mỗi lần gửi\n"
        f"• Bạn hiện tại: 1–<b>{limit}</b> lần\n\n"
        "⏳ <b>Cooldown:</b>\n"
        f"• Không VIP: Chờ 60 giây sau mỗi lần dùng SMS\n"
        f"• Có VIP 💎: Không bị delay\n"
        f"• Bot tự cập nhật kết quả sau khi hoàn thành"
        f"{FOOTER}"
    )
    send(chat_id, txt)


def cmd_info(msg: dict):
    user_id = msg["from"]["id"]
    chat_id = msg["chat"]["id"]

    if is_banned(user_id):
        return send(chat_id, "🚫 Tài khoản của bạn đã bị cấm sử dụng bot." + FOOTER)

    act, uinfo = is_activated(user_id)
    if not act:
        return send(chat_id,
            "🔒 Chưa kích hoạt! Dùng /start để kích hoạt." + FOOTER,
            reply_markup=kb_activation())

    hwid = make_hwid(user_id)
    key_disp = uinfo.get("key","N/A")
    if key_disp == "__da_duyet__": key_disp = "Duyệt HWID (không có key)"
    vip_status = is_vip(user_id)
    limit = get_sms_limit(user_id)

    txt = (
        "👤 <b>THÔNG TIN TÀI KHOẢN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Tên: {uinfo.get('first_name','N/A')}\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"🔑 HWID: <code>{hwid}</code>\n"
        f"🗝️ Key: <code>{key_disp}</code>\n"
        f"⏳ Hạn sử dụng: {format_expiry(user_id)}\n"
        f"💎 VIP: {format_vip_expiry(user_id)}\n"
        f"📊 Giới hạn SMS: 1–{limit} lần\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
        f"{FOOTER}"
    )
    send(chat_id, txt)


def cmd_sms(msg: dict):
    user_id    = msg["from"]["id"]
    uid        = str(user_id)
    chat_id    = msg["chat"]["id"]
    first_name = msg["from"].get("first_name", "User")
    username   = msg["from"].get("username", "")

    # Kiểm tra bị cấm
    if is_banned(user_id):
        return send(chat_id, "🚫 Tài khoản của bạn đã bị cấm sử dụng bot." + FOOTER)

    act, uinfo = is_activated(user_id)
    if not act:
        return send(chat_id,
            "🔒 Bạn chưa kích hoạt! Dùng /start để kích hoạt." + FOOTER,
            reply_markup=kb_activation())

    parts = msg.get("text","").split()
    if len(parts) < 3:
        return send(chat_id,
            "❌ <b>Sai cú pháp!</b>\n"
            "Dùng: <code>/sms [SĐT] [Số lần]</code>\n"
            "Ví dụ: <code>/sms 0912345678 3</code>"
            f"{FOOTER}")

    phone = parts[1].strip()
    limit = get_sms_limit(user_id)
    vip_user = is_vip(user_id)

    try:
        count = int(parts[2])
        if not (1 <= count <= limit):
            raise ValueError()
    except ValueError:
        return send(chat_id,
            f"❌ Số lần không hợp lệ.\n"
            f"{'💎 VIP' if vip_user else '👤 Thường'}: nhập từ 1 đến {limit}."
            f"{FOOTER}")

    # Kiểm tra cooldown 60 giây (chỉ áp dụng cho không VIP)
    if not vip_user:
        last_sms = uinfo.get("last_sms_time", 0)
        if last_sms and last_sms > 0:
            elapsed = time.time() - last_sms
            if elapsed < 60:
                remaining = int(60 - elapsed)
                return send(chat_id,
                    f"⏳ Quý Khách Không Có VIP Vui Lòng Chờ <b>{remaining} Giây</b> "
                    f"Hoặc Liên Hệ Admin.... Để Có VIP"
                    f"{FOOTER}")

    hwid       = make_hwid(user_id)
    key_disp   = uinfo.get("key","N/A")
    if key_disp == "__da_duyet__": key_disp = "Duyệt HWID"
    carrier    = detect_carrier(phone)
    user_disp  = f"{first_name} (@{username})" if username else first_name

    # Cập nhật last_sms_time
    _data.setdefault("users", {}).setdefault(uid, {})["last_sms_time"] = time.time()
    _save()

    # Notify admins
    notify_admins(
        f"📨 <b>YÊU CẦU /sms MỚI</b>\n"
        f"👤 {user_disp} [<code>{user_id}</code>]\n"
        f"📱 SĐT: <code>{phone}</code>\n"
        f"🔢 Số lần: {count}\n"
        f"💎 VIP: {'✅' if vip_user else '❌'}\n"
        f"🔑 HWID: <code>{hwid}</code>"
    )

    # Bắt đầu spam ngay (không delay)
    init_txt = (
        "🚀 <b>ĐANG KHỞI CHẠY SPAM OTP...</b>\n\n"
        f"📱 Số ĐT: <code>{phone}</code>\n"
        f"🔢 Số lần: {count}\n"
        f"📡 Nhà mạng: {carrier}\n"
        f"💎 VIP: {'✅ Có' if vip_user else '❌ Không'}\n"
        f"⚡ Trạng thái: 🔄 Đang gửi...\n"
        f"👤 Người YC: {user_disp} [<code>{user_id}</code>]"
        f"{FOOTER}"
    )
    resp   = send(chat_id, init_txt)
    msg_id = resp.get("result", {}).get("message_id")
    threading.Thread(
        target=_do_spam,
        args=(chat_id, msg_id, user_id, phone, count,
              carrier, hwid, key_disp, user_disp, vip_user),
        daemon=True
    ).start()


def _do_spam(chat_id, msg_id, user_id, phone, count,
             carrier, hwid, key_disp, user_disp, vip_user=False):
    total_ok, total_fail = run_spam(phone, count)
    done_txt = (
        "✅ <b>HOÀN THÀNH SPAM OTP</b>\n\n"
        f"📱 Số ĐT: <code>{phone}</code>\n"
        f"🔢 Số lần: {count}\n"
        f"📡 Nhà mạng: {carrier}\n"
        f"💎 VIP: {'✅ Có' if vip_user else '❌ Không'}\n"
        f"⚡ Trạng thái: ✅ Hoàn thành\n"
        f"👤 Người YC: {user_disp} [<code>{user_id}</code>]\n"
        f"📊 Kết quả: ✅ {total_ok} thành công / ❌ {total_fail} thất bại"
        f"{FOOTER}"
    )
    if msg_id:
        edit_msg(chat_id, msg_id, done_txt)


# ============================================================
# CALLBACK QUERY HANDLER
# ============================================================
def handle_callback(cb: dict):
    cb_id      = cb["id"]
    user_id    = cb["from"]["id"]
    uid        = str(user_id)
    chat_id    = cb["message"]["chat"]["id"]
    msg_id     = cb["message"]["message_id"]
    data       = cb.get("data","")
    first_name = cb["from"].get("first_name","Bạn")
    username   = cb["from"].get("username","")

    answer_cb(cb_id)

    # Kiểm tra bị cấm
    if is_banned(user_id) and data not in ("act_key", "act_submit", "act_link", "act_check"):
        return send(chat_id, "🚫 Tài khoản của bạn đã bị cấm sử dụng bot." + FOOTER)

    hwid = make_hwid(user_id)

    # --- Activation callbacks ---
    if data == "act_key":
        set_state(user_id, "waiting_key")
        send(chat_id,
            f"🔑 <b>NHẬP KEY KÍCH HOẠT</b>\n\n"
            f"🆔 HWID của bạn:\n<code>{hwid}</code>\n\n"
            f"Hãy nhập Key của bạn vào đây:"
            f"{FOOTER}")

    elif data == "act_submit":
        resp = api_submit_device(hwid)
        st = resp.get("status","")
        if st == "success":
            txt = (f"✅ <b>Đã gửi HWID thành công!</b>\n\n"
                   f"🆔 HWID: <code>{hwid}</code>\n"
                   f"📌 Mã YC: <code>{resp.get('req_id','N/A')}</code>\n\n"
                   f"⏳ Vui lòng chờ Admin duyệt. Sau đó nhấn 'Kiểm Tra Đã Được Duyệt'.")
        elif st == "already_approved":
            txt = "✅ HWID của bạn đã được duyệt! Nhấn 'Kiểm Tra Đã Được Duyệt' để vào tool."
        elif st == "exists":
            txt = "⏳ HWID đang chờ duyệt. Nhấn 'Kiểm Tra Đã Được Duyệt' để kiểm tra."
        else:
            txt = f"❌ Lỗi: {resp.get('message', resp.get('msg','Không xác định'))}"
        send(chat_id, txt + FOOTER, reply_markup=kb_activation())

    elif data == "act_link":
        resp = api_getkey(hwid)
        st = resp.get("status","")
        if st == "success":
            link = resp.get("link","")
            txt = (f"🔗 <b>Link nhận Key miễn phí:</b>\n\n"
                   f"{link}\n\n"
                   f"⚠️ Tối đa 2 link/ngày. Link hết hạn sau 24 giờ.")
        elif st == "limit":
            txt = "❌ Đã đạt giới hạn 2 link/ngày. Thử lại vào ngày mai."
        else:
            txt = f"❌ Lỗi: {resp.get('message','Không xác định')}"
        send(chat_id, txt + FOOTER, reply_markup=kb_activation())

    elif data == "act_check":
        resp = api_check_device(hwid)
        st = resp.get("status","")
        if st == "approved":
            raw_exp = resp.get("expiry")
            is_perm = bool(resp.get("is_permanent", False))
            try:
                expiry = float(raw_exp) if raw_exp is not None else 0.0
            except Exception:
                expiry = 0.0
            kf = resp.get("key") or "__da_duyet__"
            _data.setdefault("users", {}).setdefault(uid, {}).update({
                "first_name": first_name, "username": username,
                "activated": True, "key": kf, "expiry": expiry,
                "is_permanent": is_perm, "server_verified": True,
                "activated_at": time.time(), "hwid": hwid
            })
            _save()
            notify_admins(
                f"✅ <b>Kích hoạt qua HWID!</b>\n"
                f"👤 {first_name} [<code>{user_id}</code>]\n"
                f"🔑 HWID: <code>{hwid}</code>\n"
                f"🗝️ Key: <code>{kf}</code>"
            )
            txt = (f"✅ <b>KÍCH HOẠT THÀNH CÔNG!</b>\n\n"
                   f"🔑 HWID: <code>{hwid}</code>\n"
                   f"⏳ Còn lại: {resp.get('time_left','N/A')}\n"
                   f"📅 Hết hạn: {resp.get('expiry_str','N/A')}\n\n"
                   f"🎉 Dùng /sms để bắt đầu spam OTP!")
            send(chat_id, txt + FOOTER)
        elif st == "expired":
            txt = (f"❌ HWID đã hết hạn!\n"
                   f"Hết hạn: {resp.get('expiry_str','N/A')}\n"
                   f"Liên hệ Admin để gia hạn.")
            send(chat_id, txt + FOOTER, reply_markup=kb_activation())
        elif st == "not_found":
            txt = "⏳ HWID chưa được duyệt hoặc chưa gửi yêu cầu. Hãy gửi HWID trước."
            send(chat_id, txt + FOOTER, reply_markup=kb_activation())
        else:
            txt = f"❌ Lỗi: {resp.get('message','Không xác định')}"
            send(chat_id, txt + FOOTER, reply_markup=kb_activation())

    elif data == "help_sms":
        vip_user = is_vip(user_id)
        limit = get_sms_limit(user_id)
        txt = (
            "📖 <b>HƯỚNG DẪN /sms</b>\n\n"
            "Cú pháp: <code>/sms [SĐT] [Số lần]</code>\n"
            "Ví dụ: <code>/sms 0912345678 3</code>\n\n"
            f"💎 VIP của bạn: {'✅ Có' if vip_user else '❌ Không'}\n"
            f"📊 Giới hạn: 1–{limit} lần\n\n"
            f"Bot sẽ gửi OTP tới {len(OTP_FUNCTIONS)}+ dịch vụ.\n"
            "Kết quả tự cập nhật sau khi hoàn thành."
        )
        send(chat_id, txt + FOOTER)

    elif data == "my_info":
        act, uinfo = is_activated(user_id)
        if act and uinfo:
            key_disp = uinfo.get("key","N/A")
            if key_disp == "__da_duyet__": key_disp = "Duyệt HWID"
            vip_user = is_vip(user_id)
            limit = get_sms_limit(user_id)
            txt = (
                f"👤 <b>THÔNG TIN</b>\n"
                f"🔑 HWID: <code>{hwid}</code>\n"
                f"🗝️ Key: <code>{key_disp}</code>\n"
                f"⏳ Hạn: {format_expiry(user_id)}\n"
                f"💎 VIP: {format_vip_expiry(user_id)}\n"
                f"📊 Giới hạn SMS: 1–{limit} lần"
            )
        else:
            txt = "🔒 Chưa kích hoạt."
        send(chat_id, txt + FOOTER)


# ============================================================
# TEXT MESSAGE HANDLER (multi-step activation)
# ============================================================
def handle_text(msg: dict):
    user_id    = msg["from"]["id"]
    uid        = str(user_id)
    chat_id    = msg["chat"]["id"]
    text_in    = msg.get("text","").strip()
    first_name = msg["from"].get("first_name","")
    username   = msg["from"].get("username","")
    state      = get_state(user_id)

    if is_banned(user_id):
        return send(chat_id, "🚫 Tài khoản của bạn đã bị cấm sử dụng bot." + FOOTER)

    if state == "waiting_key":
        clear_state(user_id)
        hwid = make_hwid(user_id)
        resp = api_verify(text_in, hwid)
        st = resp.get("status","")
        if st == "success":
            raw_exp = resp.get("expiry")
            is_perm = bool(resp.get("is_permanent", False))
            try:
                expiry = float(raw_exp) if raw_exp is not None else 0.0
            except Exception:
                expiry = 0.0
            _data.setdefault("users",{}).setdefault(uid,{}).update({
                "first_name": first_name, "username": username,
                "activated": True, "key": text_in, "expiry": expiry,
                "is_permanent": is_perm, "server_verified": True,
                "activated_at": time.time(), "hwid": hwid
            })
            _save()
            notify_admins(
                f"🔑 <b>Key kích hoạt thành công!</b>\n"
                f"👤 {first_name} [<code>{user_id}</code>]\n"
                f"🔑 Key: <code>{text_in}</code>\n"
                f"🆔 HWID: <code>{hwid}</code>"
            )
            txt = (
                f"✅ <b>KÍCH HOẠT THÀNH CÔNG!</b>\n\n"
                f"🗝️ Key: <code>{text_in}</code>\n"
                f"⏳ Còn lại: {resp.get('time_left','N/A')}\n"
                f"📅 Hết hạn: {resp.get('expiry_str','N/A')}\n\n"
                f"🎉 Dùng /sms để bắt đầu spam OTP!"
                f"{FOOTER}"
            )
            send(chat_id, txt, reply_markup=kb_main())
        else:
            msgs = {
                "expired":      f"❌ Key đã hết hạn! Hết hạn: {resp.get('expiry_str','N/A')}",
                "device_limit": f"❌ Key đạt giới hạn thiết bị tối đa ({resp.get('max_devices','?')} thiết bị).",
                "invalid":      "❌ Key không tồn tại! Kiểm tra lại.",
            }
            txt = msgs.get(st, f"❌ Lỗi: {resp.get('message','Không xác định')}")
            send(chat_id, txt + FOOTER, reply_markup=kb_activation())
        return

    # Not in any state
    act, _ = is_activated(user_id)
    if not act:
        send(chat_id,
            "🔒 Bạn chưa kích hoạt! Dùng /start để kích hoạt." + FOOTER,
            reply_markup=kb_activation())


# ============================================================
# ADMIN COMMANDS
# ============================================================
def is_admin(user_id: int) -> bool:
    return user_id in _get_admins()

def _parse_vip_duration(val_str: str, unit_str: str):
    """
    Trả về (vip_expiry: float, vip_permanent: bool)
    unit: ngay / gio / thang / forever / vinh-vien
    """
    unit_lower = unit_str.lower().strip()
    if unit_lower in ("forever", "vinhvien", "vinh-vien", "vinh_vien", "permanent"):
        return 0.0, True
    try:
        val = float(val_str)
    except ValueError:
        return 0.0, False
    multipliers = {
        "ngay": 86400,
        "gio":  3600,
        "thang": 2592000,  # 30 days
        "day":  86400,
        "hour": 3600,
        "month": 2592000,
    }
    mult = multipliers.get(unit_lower, 86400)
    expiry = time.time() + val * mult
    return expiry, False

def cmd_admin(msg: dict):
    user_id = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    if not is_admin(user_id):
        return send(chat_id, "❌ Bạn không có quyền Admin!" + FOOTER)

    text  = msg.get("text","").strip()
    parts = text.split(None, 4)
    cmd   = parts[0].lstrip('/').split('@')[0].lower()

    # ── /admin ── Bảng lệnh admin
    if cmd == "admin":
        users  = _data.get("users",{})
        act_ct = sum(1 for u in users.values() if u.get("activated"))
        vip_ct = sum(1 for uid_s, u in users.items()
                     if u.get("vip") and is_vip(int(uid_s)))
        ban_ct = sum(1 for u in users.values() if u.get("banned"))
        txt = (
            "👑 <b>ADMIN PANEL</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Tổng users: {len(users)}\n"
            f"✅ Đã kích hoạt: {act_ct}\n"
            f"💎 Đang có VIP: {vip_ct}\n"
            f"🚫 Bị cấm: {ban_ct}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Lệnh Admin:</b>\n"
            "/addvip [ID] [val] [unit] — Thêm VIP\n"
            "  Ví dụ: /addvip 123456789 30 ngay\n"
            "  VIP vĩnh viễn: /addvip 123456789 0 forever\n"
            "/delvip [ID] — Xóa VIP\n"
            "/banuser [ID] — Cấm user\n"
            "/unban [ID] — Bỏ cấm user\n"
            "/listuser — Danh sách người dùng\n"
            "/broadcast [nội dung] — Gửi tới tất cả"
        )
        send(chat_id, txt + FOOTER)

    # ── /addvip [ID] [val] [unit] ──
    elif cmd == "addvip":
        if len(parts) < 4:
            return send(chat_id,
                "Dùng: /addvip [ID] [val] [unit]\n"
                "Ví dụ: /addvip 123456789 30 ngay\n"
                "VIP vĩnh viễn: /addvip 123456789 0 forever" + FOOTER)
        try:
            target_id = int(parts[1])
        except ValueError:
            return send(chat_id, "❌ ID không hợp lệ!" + FOOTER)
        val_str  = parts[2]
        unit_str = parts[3]
        vip_expiry, vip_perm = _parse_vip_duration(val_str, unit_str)
        uid_s = str(target_id)
        _data.setdefault("users", {}).setdefault(uid_s, {
            "first_name": "N/A", "username": "", "first_seen": time.time(), "activated": True
        })
        _data["users"][uid_s]["vip"]          = True
        _data["users"][uid_s]["vip_permanent"] = vip_perm
        _data["users"][uid_s]["vip_expiry"]    = vip_expiry
        _save()
        if vip_perm:
            exp_txt = "♾️ Vĩnh viễn"
        else:
            left = vip_expiry - time.time()
            d = int(left // 86400); h = int((left % 86400) // 3600)
            exp_txt = f"{d} ngày {h} giờ"
        txt = (
            f"✅ <b>Đã thêm VIP!</b>\n"
            f"🆔 User ID: <code>{target_id}</code>\n"
            f"💎 Hạn VIP: {exp_txt}\n"
            f"📊 Giới hạn SMS: 1–{LIMIT_VIP} lần"
        )
        send(chat_id, txt + FOOTER)
        # Thông báo cho user
        try:
            send(target_id,
                f"🎉 <b>Bạn đã được cấp VIP!</b>\n\n"
                f"💎 Hạn VIP: {exp_txt}\n"
                f"📊 Giới hạn SMS nâng lên: 1–{LIMIT_VIP} lần\n"
                f"⚡ Không bị delay 60 giây nữa!\n\n"
                f"Dùng /info để xem thông tin tài khoản."
                f"{FOOTER}")
        except Exception:
            pass

    # ── /delvip [ID] ──
    elif cmd == "delvip":
        if len(parts) < 2:
            return send(chat_id, "Dùng: /delvip [ID]" + FOOTER)
        try:
            target_id = int(parts[1])
        except ValueError:
            return send(chat_id, "❌ ID không hợp lệ!" + FOOTER)
        uid_s = str(target_id)
        if uid_s in _data.get("users", {}):
            _data["users"][uid_s]["vip"]          = False
            _data["users"][uid_s]["vip_permanent"] = False
            _data["users"][uid_s]["vip_expiry"]    = 0
            _save()
        send(chat_id, f"✅ Đã xóa VIP của user <code>{target_id}</code>." + FOOTER)
        try:
            send(target_id,
                f"ℹ️ VIP của bạn đã bị thu hồi bởi Admin.\n"
                f"Giới hạn SMS: 1–{LIMIT_NORMAL} lần.\n"
                f"Liên hệ Admin nếu có thắc mắc.{FOOTER}")
        except Exception:
            pass

    # ── /banuser [ID] ──
    elif cmd == "banuser":
        if len(parts) < 2:
            return send(chat_id, "Dùng: /banuser [ID]" + FOOTER)
        try:
            target_id = int(parts[1])
        except ValueError:
            return send(chat_id, "❌ ID không hợp lệ!" + FOOTER)
        uid_s = str(target_id)
        _data.setdefault("users", {}).setdefault(uid_s, {
            "first_name": "N/A", "username": "", "first_seen": time.time()
        })
        _data["users"][uid_s]["banned"] = True
        _save()
        send(chat_id, f"🚫 Đã cấm user <code>{target_id}</code> sử dụng bot." + FOOTER)
        try:
            send(target_id, f"🚫 Tài khoản của bạn đã bị Admin cấm sử dụng bot." + FOOTER)
        except Exception:
            pass

    # ── /unban [ID] ──
    elif cmd == "unban":
        if len(parts) < 2:
            return send(chat_id, "Dùng: /unban [ID]" + FOOTER)
        try:
            target_id = int(parts[1])
        except ValueError:
            return send(chat_id, "❌ ID không hợp lệ!" + FOOTER)
        uid_s = str(target_id)
        if uid_s in _data.get("users", {}):
            _data["users"][uid_s]["banned"] = False
            _save()
        send(chat_id, f"✅ Đã bỏ cấm user <code>{target_id}</code>." + FOOTER)
        try:
            send(target_id, f"✅ Tài khoản của bạn đã được bỏ cấm. Dùng /start để tiếp tục." + FOOTER)
        except Exception:
            pass

    # ── /listuser ──
    elif cmd == "listuser":
        users = _data.get("users",{})
        if not users:
            return send(chat_id, "Chưa có người dùng nào." + FOOTER)
        lines = ["👥 <b>DANH SÁCH NGƯỜI DÙNG (tối đa 30):</b>"]
        for uid_s, u in list(users.items())[:30]:
            act_icon = "✅" if u.get("activated") else "❌"
            vip_icon = "💎" if (u.get("vip") and is_vip(int(uid_s))) else ""
            ban_icon = "🚫" if u.get("banned") else ""
            name = u.get("first_name","?")
            lines.append(f"{act_icon}{vip_icon}{ban_icon} <code>{uid_s}</code> — {name}")
        send(chat_id, "\n".join(lines) + FOOTER)

    # ── /broadcast [text] ──
    elif cmd == "broadcast":
        if len(parts) < 2:
            return send(chat_id, "Dùng: /broadcast [tin nhắn]" + FOOTER)
        bc_text = text.split(None, 1)[1] if ' ' in text else ""
        users = _data.get("users",{})
        ok = 0
        for uid_s in users:
            try:
                send(int(uid_s), bc_text)
                ok += 1
            except Exception:
                pass
        send(chat_id, f"✅ Broadcast gửi tới {ok}/{len(users)} người dùng." + FOOTER)


# ============================================================
# DISPATCHER
# ============================================================
ADMIN_CMDS = {
    "admin", "addvip", "delvip", "banuser", "unban", "listuser", "broadcast"
}

def dispatch(update: dict):
    try:
        if "callback_query" in update:
            handle_callback(update["callback_query"])
            return

        msg = update.get("message")
        if not msg:
            return
        text = msg.get("text","")
        if not text:
            return

        user_id = msg["from"]["id"]
        if text.startswith('/'):
            raw_cmd = text.split()[0].lstrip('/').split('@')[0].lower()
            if   raw_cmd == "start":     cmd_start(msg)
            elif raw_cmd == "help":      cmd_help(msg)
            elif raw_cmd == "info":      cmd_info(msg)
            elif raw_cmd == "sms":       cmd_sms(msg)
            elif raw_cmd in ADMIN_CMDS:  cmd_admin(msg)
            else:                        handle_text(msg)
        else:
            handle_text(msg)

    except Exception as e:
        logging.error(f"[dispatch] {e}", exc_info=True)


# ============================================================
# FLASK WEB SERVER
# ============================================================
app = Flask(__name__)

_LOVE_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Văn Khánh ❤️ Minh Thư</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{
  min-height:100vh;
  background:linear-gradient(135deg,#ff6b6b 0%,#ee5a24 25%,#ff6b6b 50%,#fd79a8 75%,#e84393 100%);
  background-size:400% 400%;
  animation:bgShift 8s ease infinite;
  display:flex;align-items:center;justify-content:center;
  font-family:'Georgia',serif;overflow:hidden;
}
@keyframes bgShift{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
.hearts-bg{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:hidden}
.hp{position:absolute;animation:floatUp linear infinite;opacity:0}
@keyframes floatUp{0%{transform:translateY(100vh) scale(.5) rotate(-10deg);opacity:0}10%{opacity:.8}90%{opacity:.5}100%{transform:translateY(-10vh) scale(1.2) rotate(15deg);opacity:0}}
.card{
  position:relative;z-index:1;
  background:rgba(255,255,255,.15);
  backdrop-filter:blur(20px);
  border:2px solid rgba(255,255,255,.3);
  border-radius:30px;
  padding:60px 50px;
  text-align:center;
  max-width:520px;
  width:90%;
  box-shadow:0 25px 50px rgba(0,0,0,.2),inset 0 1px 0 rgba(255,255,255,.3);
}
.big-heart{font-size:5rem;animation:hb 1.2s ease-in-out infinite;display:block;margin-bottom:20px;filter:drop-shadow(0 0 20px rgba(255,100,100,.8))}
@keyframes hb{0%,100%{transform:scale(1)}14%{transform:scale(1.15)}28%{transform:scale(1)}42%{transform:scale(1.15)}70%{transform:scale(1)}}
h1{color:#fff;font-size:1.9rem;text-shadow:0 2px 10px rgba(0,0,0,.3);margin-bottom:15px;line-height:1.4}
.divider{width:60px;height:3px;background:rgba(255,255,255,.6);margin:20px auto;border-radius:2px}
.sub{color:rgba(255,255,255,.85);font-size:1rem;letter-spacing:1px;font-style:italic;margin-top:10px}
.sparkle{font-size:1.5rem;animation:sp 2s ease-in-out infinite;display:inline-block}
@keyframes sp{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.8)}}
</style>
</head>
<body>
<div class="hearts-bg" id="hb"></div>
<div class="card">
  <span class="big-heart">❤️</span>
  <h1>Tôi là Văn Khánh<br>yêu Minh Thư</h1>
  <div class="divider"></div>
  <p class="sub">Mãi mãi bên nhau 💕</p>
  <div style="margin-top:20px">
    <span class="sparkle">✨</span>
    <span class="sparkle" style="animation-delay:.4s">💝</span>
    <span class="sparkle" style="animation-delay:.8s">✨</span>
  </div>
</div>
<script>
const hs=['❤️','💕','💗','💓','💞','🌹','💖'];
const c=document.getElementById('hb');
function mkH(){
  const e=document.createElement('div');
  e.className='hp';
  e.textContent=hs[Math.floor(Math.random()*hs.length)];
  e.style.left=Math.random()*100+'%';
  e.style.fontSize=(1+Math.random()*1.5)+'rem';
  const dur=4+Math.random()*4;
  e.style.animationDuration=dur+'s';
  e.style.animationDelay=Math.random()*2+'s';
  c.appendChild(e);
  setTimeout(()=>e.remove(),(dur+2)*1000);
}
setInterval(mkH,500);
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(_LOVE_HTML)

@app.route('/ping')
def ping():
    return "pong", 200

@app.route('/health')
def health():
    return {"status": "ok", "timestamp": time.time()}, 200


# ============================================================
# KEEP-ALIVE WORKERS (3 workers, prevent Render sleep)
# ============================================================
def _keep_alive_worker(start_delay: int, worker_id: int):
    time.sleep(start_delay)
    cycle = 14 * 60   # 14-minute cycle per worker
    while True:
        try:
            requests.get(f"{SELF_URL}/ping", timeout=10)
            logging.info(f"[KA-{worker_id}] ping OK")
        except Exception as e:
            logging.warning(f"[KA-{worker_id}] ping fail: {e}")
        time.sleep(cycle)

def start_keep_alive():
    # Offsets: 0s, 4m40s, 9m20s → combined = ping every ~4.7min
    for idx, offset in enumerate([0, 280, 560]):
        t = threading.Thread(target=_keep_alive_worker,
                             args=(offset, idx + 1), daemon=True)
        t.start()
    logging.info("Keep-alive: 3 workers started (14min cycle each)")


# ============================================================
# TELEGRAM LONG-POLL LOOP
# ============================================================
_last_update_id = 0

def _poll_loop():
    global _last_update_id
    logging.info("Telegram polling started…")
    while True:
        try:
            r = requests.get(f"{BOT_URL}/getUpdates",
                             params={"offset": _last_update_id + 1, "timeout": 30},
                             timeout=35)
            data = r.json()
            if data.get("ok"):
                for upd in data.get("result", []):
                    _last_update_id = upd["update_id"]
                    threading.Thread(target=dispatch, args=(upd,), daemon=True).start()
        except Exception as e:
            logging.warning(f"[poll] {e}")
            time.sleep(5)

def start_polling():
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    logging.info("Polling thread started")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    start_keep_alive()
    start_polling()

    port = int(os.environ.get('PORT', 5000))
    logging.info(f"Flask starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
