import os
import json
import requests
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

# ============================================================
# إعدادات البوت
# ============================================================
BOT_TOKEN = "8808969190:AAHo_14OPNbRQL0DpG4xhncHmtR2mw_YYTs"
ADMIN_ID = "1743301387"
TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ============================================================
# قاعدة بيانات JSONBin
# ============================================================
JBIN_KEY = "$2a$10$GTPka01SaLPehwlSP01DH.k1WwIyh9Ko2GrTYMN91JAjBL2Dk.EIG"
JBIN_API = "https://api.jsonbin.io/v3/b"
BIN_ID = "6a40d3f1da38895dfe0a9368"
MAX_TRIES = 2


# ============================================================
# دوال قاعدة البيانات
# ============================================================
def load_db():
    try:
        r = requests.get(f"{JBIN_API}/{BIN_ID}/latest",
            headers={"X-Master-Key": JBIN_KEY})
        rec = r.json().get("record", {})
        return rec.get("codes", {}), rec.get("fingerprints", {}), rec.get("stats", {})
    except Exception as e:
        print(f"Error loading DB: {e}")
        return {}, {}, {}


def save_stats(stats):
    try:
        codes, fps, _ = load_db()
        requests.put(f"{JBIN_API}/{BIN_ID}", headers={
            "Content-Type": "application/json",
            "X-Master-Key": JBIN_KEY
        }, json={
            "codes": codes,
            "fingerprints": fps,
            "stats": stats
        })
    except Exception as e:
        print(f"Error saving stats: {e}")


def add_event(stats, event_type, info=None):
    if "lastEvents" not in stats:
        stats["lastEvents"] = []
    stats["lastEvents"].append({
        "type": event_type,
        "info": info or {},
        "time": datetime.now().isoformat()
    })
    if len(stats["lastEvents"]) > 50:
        stats["lastEvents"] = stats["lastEvents"][-50:]
    save_stats(stats)


# ============================================================
# دوال التليجرام
# ============================================================
def send(chat_id, text):
    try:
        requests.post(f"{TG}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        })
    except Exception as e:
        print(f"Error sending message: {e}")


def is_admin(chat_id):
    return str(chat_id) == str(ADMIN_ID)


def fmt_event(e):
    t = e.get("type", "?")
    info = e.get("info", {}) or {}
    time = e.get("time", "")[:16].replace("T", " ")
    
    labels = {
        "visit": f"👁 زيارة للأداة",
        "wrong_code": f"⚠️ كود خاطئ: {info.get('attempted', '?')}",
        "activate": f"✅ تفعيل كود {info.get('code', '?')} — {info.get('owner_name') or info.get('owner', 'مجهول')}",
        "fps_use": f"🎬 استخدام FPS — كود {info.get('code', '?')}",
        "ipad_use": f"📐 استخدام آيباد — كود {info.get('code', '?')}",
    }
    return f"{time} | {labels.get(t, t)}"


# ============================================================
# مسار Webhook
# ============================================================
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.json or {}
    msg = data.get("message", {})
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return "ok"

    # التحقق من الصلاحية
    if not is_admin(chat_id):
        send(chat_id, "⛔ هذا بوت إحصائيات خاص، غير مخوّل لك استخدامه.")
        return "ok"

    # ========== الأوامر ==========
    
    if text == "/start":
        send(chat_id, (
            "📊 <b>بوت إحصائيات TIKRITI</b>\n\n"
            "📌 <b>الأوامر المتاحة:</b>\n"
            "/stats — ملخص عام عن الاستخدام\n"
            "/users — قائمة كل من حصل على كود واستخدمه\n"
            "/recent — آخر 15 حدثاً على الأداة\n"
            "/code [الكود] — البحث عن كود معين"
        ))

    elif text == "/stats":
        codes, fps, stats = load_db()
        total_codes = len(codes)
        activated = sum(
            1 for d in codes.values()
            if d.get("used1", 0) > 0 or d.get("used2", 0) > 0
        )
        fps_uses = sum(d.get("cnt1", 0) for d in codes.values())
        ipad_uses = sum(d.get("cnt2", 0) for d in codes.values())
        
        # عدد الأجهزة التي استنفذت كل المحاولات
        exhausted = 0
        for d in codes.values():
            if d.get("used1", 0) >= MAX_TRIES and d.get("used2", 0) >= MAX_TRIES:
                exhausted += 1
        
        visits = stats.get("visits", 0)
        wrong = stats.get("wrongAttempts", 0)

        send(chat_id, (
            "📊 <b>إحصائيات TIKRITI</b>\n\n"
            f"👁 عدد الزيارات للأداة: {visits}\n"
            f"🔑 عدد الأكواد الصادرة: {total_codes}\n"
            f"✅ أكواد تم تفعيلها/استخدامها: {activated}\n"
            f"🎬 مرات استخدام أداة FPS: {fps_uses}\n"
            f"📐 مرات استخدام أداة آيباد: {ipad_uses}\n"
            f"📵 أجهزة استنفذت كل محاولاتها: {exhausted}\n"
            f"⚠️ محاولات كود خاطئ: {wrong}"
        ))

    elif text == "/users":
        codes, fps, stats = load_db()
        if not codes:
            send(chat_id, "📭 لا يوجد أي مستخدمين بعد.")
            return "ok"

        lines = ["👥 <b>قائمة المستخدمين</b>\n"]
        for code, d in codes.items():
            owner = d.get("owner", "—")
            name = d.get("owner_name") or d.get("name") or "بدون اسم"
            r1 = max(0, MAX_TRIES - d.get("used1", 0))
            r2 = max(0, MAX_TRIES - d.get("used2", 0))
            lines.append(
                f"👤 {name} (<code>{owner}</code>)\n"
                f"   🔑 <code>{code}</code> — FPS: {r1} | آيباد: {r2}"
            )

        full_text = "\n".join(lines)
        for i in range(0, len(full_text), 3500):
            send(chat_id, full_text[i:i + 3500])

    elif text == "/recent":
        _, _, stats = load_db()
        events = (stats.get("lastEvents") or [])[-15:]
        if not events:
            send(chat_id, "📭 لا توجد أحداث مسجلة بعد.")
            return "ok"
        lines = ["🕒 <b>آخر الأحداث</b>\n"]
        for e in reversed(events):
            lines.append(f"• {fmt_event(e)}")
        send(chat_id, "\n".join(lines))

    elif text.startswith("/code"):
        parts = text.split()
        if len(parts) < 2:
            send(chat_id, "⚠️ استخدم: /code [الكود]")
            return "ok"
        
        search_code = parts[1].strip().upper()
        codes, _, _ = load_db()
        
        if search_code not in codes:
            send(chat_id, f"❌ الكود <code>{search_code}</code> غير موجود.")
            return "ok"
        
        d = codes[search_code]
        owner = d.get("owner", "—")
        name = d.get("owner_name") or d.get("name") or "بدون اسم"
        used1 = d.get("used1", 0)
        used2 = d.get("used2", 0)
        cnt1 = d.get("cnt1", 0)
        cnt2 = d.get("cnt2", 0)
        
        send(chat_id, (
            f"🔑 <b>معلومات الكود</b>\n\n"
            f"📌 الكود: <code>{search_code}</code>\n"
            f"👤 المالك: {name} (<code>{owner}</code>)\n"
            f"🎬 FPS المستخدمة: {used1}/{MAX_TRIES} (إجمالي {cnt1} فيديو)\n"
            f"📐 آيباد المستخدمة: {used2}/{MAX_TRIES} (إجمالي {cnt2} فيديو)"
        ))

    return "ok"


# ============================================================
# الصفحة الرئيسية
# ============================================================
@app.route("/")
def home():
    return "✅ TIKRITI Stats Bot is running"


# ============================================================
# تشغيل التطبيق
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
