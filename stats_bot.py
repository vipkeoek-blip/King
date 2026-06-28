import os
import requests
from flask import Flask, request

app = Flask(__name__)

# توكن بوت الإحصاءات (منفصل تماماً عن بوت الأكواد القديم)
BOT_TOKEN = "8808969190:AAHo_14OPNbRQL0DpG4xhncHmtR2mw_YYTs"
ADMIN_ID = "1743301387"
TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

# نفس قاعدة بيانات jsonbin التي تستخدمها أداة TIKRITI وبوت الأكواد
JBIN_KEY = "$2a$10$GTPka01SaLPehwlSP01DH.k1WwIyh9Ko2GrTYMN91JAjBL2Dk.EIG"
JBIN_API = "https://api.jsonbin.io/v3/b"
BIN_ID = "6a40d3f1da38895dfe0a9368"

MAX_TRIES = 2


def load_db():
    try:
        r = requests.get(f"{JBIN_API}/{BIN_ID}/latest",
            headers={"X-Master-Key": JBIN_KEY})
        rec = r.json().get("record", {})
        return rec.get("codes", {}), rec.get("fingerprints", {}), rec.get("stats", {})
    except Exception:
        return {}, {}, {}


def send(chat_id, text):
    requests.post(f"{TG}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })


def is_admin(chat_id):
    return chat_id == ADMIN_ID


def fmt_event(e):
    t = e.get("type", "?")
    info = e.get("info", {}) or {}
    labels = {
        "visit": "👁 زيارة للأداة",
        "wrong_code": f"⚠️ كود خاطئ: {info.get('attempted','?')}",
        "activate": f"✅ تفعيل كود {info.get('code','?')} — {info.get('owner_name') or info.get('owner') or 'مجهول'}",
        "fps_use": f"🎬 استخدام FPS — كود {info.get('code','?')}",
        "ipad_use": f"📐 استخدام آيباد — كود {info.get('code','?')}",
    }
    return labels.get(t, t)


@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.json or {}
    msg = data.get("message", {})
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return "ok"

    if not is_admin(chat_id):
        send(chat_id, "⛔ هذا بوت إحصائيات خاص، غير مخوّل لك استخدامه.")
        return "ok"

    if text == "/start":
        send(chat_id, (
            "📊 <b>بوت إحصائيات TIKRITI</b>\n\n"
            "الأوامر المتاحة:\n"
            "/stats — ملخص عام عن الاستخدام\n"
            "/users — قائمة كل من حصل على كود واستخدمه\n"
            "/recent — آخر 15 حدثاً على الأداة"
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
        exhausted_devices = sum(
            1 for d in fps.values()
            if d.get("used1", 0) >= MAX_TRIES and d.get("used2", 0) >= MAX_TRIES
        )
        visits = stats.get("visits", 0)
        wrong = stats.get("wrongAttempts", 0)

        send(chat_id, (
            "📊 <b>إحصائيات TIKRITI</b>\n\n"
            f"👁 عدد الزيارات للأداة: {visits}\n"
            f"🔑 عدد الأكواد الصادرة: {total_codes}\n"
            f"✅ أكواد تم تفعيلها/استخدامها: {activated}\n"
            f"🎬 مرات استخدام أداة FPS: {fps_uses}\n"
            f"📐 مرات استخدام أداة آيباد: {ipad_uses}\n"
            f"📵 أجهزة استنفذت كل محاولاتها: {exhausted_devices}\n"
            f"⚠️ محاولات كود خاطئ: {wrong}"
        ))

    elif text == "/users":
        codes, fps, stats = load_db()
        if not codes:
            send(chat_id, "لا يوجد أي مستخدمين بعد.")
            return "ok"

        lines = ["👥 <b>من حصل على كود واستخدم الأداة</b>\n"]
        for code, d in codes.items():
            owner = d.get("owner", "—")
            name = d.get("owner_name") or "بدون اسم"
            r1 = max(0, MAX_TRIES - d.get("used1", 0))
            r2 = max(0, MAX_TRIES - d.get("used2", 0))
            lines.append(
                f"👤 {name} (<code>{owner}</code>)\n"
                f"   🔑 <code>{code}</code> — FPS متبقية: {r1} | آيباد متبقية: {r2}"
            )

        full_text = "\n".join(lines)
        # تيليجرام يحدد حد 4096 حرف للرسالة، نقسمها إن طالت
        for i in range(0, len(full_text), 3500):
            send(chat_id, full_text[i:i + 3500])

    elif text == "/recent":
        _, _, stats = load_db()
        events = (stats.get("lastEvents") or [])[-15:]
        if not events:
            send(chat_id, "لا توجد أحداث مسجلة بعد.")
            return "ok"
        lines = ["🕒 <b>آخر الأحداث</b>\n"]
        for e in reversed(events):
            lines.append(f"• {fmt_event(e)}")
        send(chat_id, "\n".join(lines))

    return "ok"


@app.route("/")
def home():
    return "TIKRITI Stats Bot is running ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
