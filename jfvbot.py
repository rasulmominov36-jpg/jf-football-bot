"""
JF FOOTBALL QUIZ boti (aiogram 3 + SQLite): hammasi bitta faylda.

Ishga tushirish:  python bot.py
Imkoniyatlar:
  - /start: logo + bot haqida ma'lumot + tugmalar
  - Majburiy obuna (kanallar bot ichidan boshqariladi)
  - Mini App (test sayti) tugmasi
  - Natija screenshotini qabul qilish -> adminga yuborish -> Tasdiqlash / Rad etish
  - Dublikatdan himoya (bir raundda bitta natija)
  - Admin: /admin /addchannel /delchannel /channels /stats /winners /broadcast /newtest
"""

# ============================================================================
#   SOZLAMALAR: faqat shu yerni to'ldiring (qolgan joyga tegmang)
# ============================================================================
BOT_TOKEN = "8641078083:AAFP_iqEYRAd5hu-hPohVPcEnXyXri23W0M"            # @BotFather bergan token
ADMIN_IDS = [7751663775, 6963372023, 121323675]                              # o'zingizning Telegram ID raqamingiz: [123456789] yoki bir nechta: [111, 222]
WEBAPP_URL = "https://rasulmominov36-jpg.github.io/JonimFutbolimQuiz/"       # test saytingiz manzili (faqat https://)
LOGO = "https://i.ibb.co/C57RNJ4f/jonim-JF.jpg"   # /start dagi logo (havola yoki fayl yo'li)
# ============================================================================

import asyncio
import html
import logging
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime

try:
    import aiogram  # noqa: F401
except ImportError:
    print("aiogram o'rnatilmoqda, kuting...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiogram>=3.7,<4"])

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (BotCommand, BotCommandScopeChat, CallbackQuery, FSInputFile,
                           InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("jfbot")

def _parse_ids(value):
    """123  /  "123"  /  "1,2"  /  [1, 2]  ko'rinishlarining hammasini qabul qiladi."""
    if isinstance(value, (int, str)):
        value = str(value).replace(";", ",").replace(" ", ",").split(",")
    ids = set()
    for x in value:
        x = str(x).strip()
        if x.lstrip("-").isdigit() and int(x) > 0:
            ids.add(int(x))
    return ids


# Sozlama qatori tasodifan o'chib ketsa ham bot yiqilmasligi uchun (LOGO bo'lmasa, standart logo olinadi)
ADMIN_IDS = _parse_ids(globals().get("ADMIN_IDS") or [])
BOT_TOKEN = str(globals().get("BOT_TOKEN") or "").strip()
WEBAPP_URL = str(globals().get("WEBAPP_URL") or "").strip()
LOGO = str(globals().get("LOGO") or "https://i.ibb.co/C57RNJ4f/jonim-JF.jpg").strip()
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")   # bot.py yonida saqlanadi

# ===================== MATNLAR =====================
INTRO = (
    "Assalomu alaykum, <b>{name}</b>! 👋\n\n"
    "Bu <b>JonimFutbolim</b> rasmiy futbol bilim sinov boti ⚽\n\n"
    "📌 <b>Qanday ishlaydi:</b>\n"
    "1. Kanallarga obuna bo'lasiz\n"
    "2. «Testni boshlash» tugmasini bosasiz\n"
    "3. 25 ta savolga javob berasiz (har biriga 15 soniya)\n"
    "4. Natijani screenshot qilib shu botga yuborasiz\n\n"
    "🏆 <b>Bosh sovrin: 25 000 so'm</b>. Barcha savolga to'g'ri javob bergan ishtirokchi oladi.\n\n"
    "⚠️ Test paytida ilovadan chiqsangiz, test avtomatik yakunlanadi. Faqat 1 marta urinish beriladi.\n\n"
    "{status}"
)
STATUS_NEED_SUB = "👇 Avval quyidagi kanallarga obuna bo'ling, so'ng «Tekshirish» tugmasini bosing."
STATUS_OK = "✅ Obuna tasdiqlangan. Testni boshlashingiz mumkin!"

RULES = (
    "📋 <b>Qoidalar</b>\n\n"
    "• Test 25 ta savoldan iborat, har bir savolga 15 soniya beriladi.\n"
    "• Savollar va javob variantlari aralash keladi.\n"
    "• Faqat 1 marta urinish beriladi.\n"
    "• Test boshlangach Telegramdan yoki ilovadan chiqsangiz, test avtomatik yakunlanadi, "
    "javob berilmagan savollar noto'g'ri hisoblanadi.\n"
    "• Test tugagach natija ekranini <b>screenshot</b> qiling va shu botga <b>rasm</b> sifatida yuboring. "
    "Screenshotda ismingiz, ID raqamingiz va natija ko'rinib turishi kerak.\n"
    "• Bosh sovrin faqat barcha savolga to'g'ri javob bergan ishtirokchiga beriladi."
)
ABOUT = "ℹ️ <b>JF FOOTBALL QUIZ</b> — JonimFutbolim rasmiy bilim sinov platformasi.\n\n"

# ===================== MA'LUMOTLAR BAZASI =====================
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS channels(id TEXT PRIMARY KEY, title TEXT, url TEXT);
CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, name TEXT, username TEXT, joined_at TEXT);
CREATE TABLE IF NOT EXISTS submissions(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, round INTEGER,
    file_id TEXT, status TEXT DEFAULT 'pending', created_at TEXT);
""")
db.commit()


def now_str():
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def get_round() -> int:
    r = db.execute("SELECT value FROM settings WHERE key='round'").fetchone()
    return int(r["value"]) if r else 1


def set_round(n: int):
    db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('round', ?)", (str(n),))
    db.commit()


def register_user(u):
    name = u.full_name or "Foydalanuvchi"
    db.execute(
        "INSERT INTO users(user_id, name, username, joined_at) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, username=excluded.username",
        (u.id, name, u.username or "", now_str()))
    db.commit()


def get_channels():
    return [dict(r) for r in db.execute("SELECT * FROM channels ORDER BY rowid")]


def chat_ref(value: str):
    return value if value.startswith("@") else int(value)


# ===================== OBUNA TEKSHIRUVI =====================
async def missing_channels(bot: Bot, user_id: int):
    async def one(ch):
        try:
            m = await bot.get_chat_member(chat_ref(ch["id"]), user_id)
            ok = m.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR) \
                or (m.status == ChatMemberStatus.RESTRICTED and getattr(m, "is_member", False))
            return None if ok else ch
        except Exception as e:   # odatda: bot kanalda admin emas
            log.warning("Obuna tekshiruvi xatosi (%s): %s", ch["id"], e)
            return ch

    res = await asyncio.gather(*(one(c) for c in get_channels()))
    return [c for c in res if c]


# ===================== TUGMALAR =====================
def sub_kb(missing):
    rows = [[InlineKeyboardButton(text=f"📢 {c['title']}", url=c["url"])] for c in missing]
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_kb():
    rows = [[InlineKeyboardButton(text="🚀 Testni boshlash", web_app=WebAppInfo(url=WEBAPP_URL))]]
    second = []
    chans = get_channels()
    if chans:
        second.append(InlineKeyboardButton(text="📢 Kanalimiz", url=chans[0]["url"]))
    second.append(InlineKeyboardButton(text="ℹ️ Qoidalar", callback_data="rules"))
    rows.append(second)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def review_kb(sub_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"rv:ok:{sub_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rv:no:{sub_id}"),
    ]])


async def safe_edit(message: Message, text: str, kb):
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=kb)
        else:
            await message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass   # "message is not modified" va shunga o'xshash


async def send_intro(bot: Bot, chat_id: int, user):
    missing = await missing_channels(bot, user.id)
    text = INTRO.format(name=html.escape(user.first_name or "do'st"),
                        status=STATUS_NEED_SUB if missing else STATUS_OK)
    kb = sub_kb(missing) if missing else start_kb()
    photo = FSInputFile(LOGO) if os.path.isfile(LOGO) else LOGO
    try:
        await bot.send_photo(chat_id, photo, caption=text, reply_markup=kb)
    except (TelegramBadRequest, FileNotFoundError) as e:
        log.warning("Logo yuborilmadi (%s), oddiy matn yuborilmoqda", e)
        await bot.send_message(chat_id, text, reply_markup=kb)


router = Router()


# ===================== FOYDALANUVCHI BUYRUQLARI =====================
@router.message(CommandStart())
async def cmd_start(msg: Message, bot: Bot):
    register_user(msg.from_user)
    await send_intro(bot, msg.chat.id, msg.from_user)


@router.message(Command("help", "about"))
async def cmd_help(msg: Message):
    await msg.answer(ABOUT + RULES)


@router.message(Command("status"))
async def cmd_status(msg: Message):
    row = db.execute("SELECT * FROM submissions WHERE user_id=? AND round=? ORDER BY id DESC LIMIT 1",
                     (msg.from_user.id, get_round())).fetchone()
    names = {"pending": "⏳ Tekshirilmoqda", "approved": "✅ Tasdiqlangan", "rejected": "❌ Rad etilgan"}
    if not row:
        return await msg.answer("Siz hali natija yubormagansiz. Testni topshirib, screenshotni shu yerga yuboring.")
    await msg.answer(f"Natijangiz holati: {names.get(row['status'], row['status'])}")


@router.callback_query(F.data == "check")
async def cb_check(cb: CallbackQuery, bot: Bot):
    missing = await missing_channels(bot, cb.from_user.id)
    if missing:
        await cb.answer("Hali hammasiga obuna bo'lmadingiz ❌", show_alert=True)
        try:
            await cb.message.edit_reply_markup(reply_markup=sub_kb(missing))
        except TelegramBadRequest:
            pass
        return
    text = INTRO.format(name=html.escape(cb.from_user.first_name or "do'st"), status=STATUS_OK)
    await safe_edit(cb.message, text, start_kb())
    await cb.answer("Obuna tasdiqlandi ✅")


@router.callback_query(F.data == "rules")
async def cb_rules(cb: CallbackQuery):
    await cb.message.answer(RULES)
    await cb.answer()


# ===================== NATIJA SCREENSHOTI =====================
@router.message(F.chat.type == "private", F.photo | F.document)
async def got_result(msg: Message, bot: Bot):
    if msg.document and not (msg.document.mime_type or "").startswith("image/"):
        return await msg.answer("Iltimos, natija screenshotini rasm ko'rinishida yuboring.")

    user = msg.from_user
    register_user(user)

    missing = await missing_channels(bot, user.id)
    if missing:
        return await msg.answer("Avval kanallarga obuna bo'ling 👇", reply_markup=sub_kb(missing))

    rnd = get_round()
    exists = db.execute(
        "SELECT 1 FROM submissions WHERE user_id=? AND round=? AND status IN ('pending','approved')",
        (user.id, rnd)).fetchone()
    if exists:
        return await msg.answer("Siz natijangizni allaqachon yuborgansiz. Holatini /status orqali bilib oling.")

    is_doc = bool(msg.document)
    file_id = msg.document.file_id if is_doc else msg.photo[-1].file_id
    cur = db.execute("INSERT INTO submissions(user_id, round, file_id, status, created_at) VALUES(?,?,?,?,?)",
                     (user.id, rnd, file_id, "pending", now_str()))
    db.commit()
    sub_id = cur.lastrowid

    uname = f"@{user.username}" if user.username else "username yo'q"
    caption = (f"📥 <b>Yangi natija #{sub_id}</b>\n"
               f"👤 {html.escape(user.full_name)} ({html.escape(uname)})\n"
               f"🆔 <code>{user.id}</code>\n"
               f"🔁 Raund: {rnd}\n"
               f"🕒 {now_str()}")
    sent = 0
    for aid in ADMIN_IDS:
        try:
            if is_doc:
                await bot.send_document(aid, file_id, caption=caption, reply_markup=review_kb(sub_id))
            else:
                await bot.send_photo(aid, file_id, caption=caption, reply_markup=review_kb(sub_id))
            sent += 1
        except Exception as e:
            log.warning("Adminga (%s) yuborilmadi: %s", aid, e)
    if not sent:
        log.error("Natija birorta adminga yetib bormadi! Adminlar botga /start bosganmi?")
    await msg.answer("✅ Natijangiz qabul qilindi va tekshirishga yuborildi. Natijasi haqida xabar beramiz.")


@router.callback_query(F.data.startswith("rv:"), F.from_user.id.in_(ADMIN_IDS))
async def cb_review(cb: CallbackQuery, bot: Bot):
    try:
        _, action, sid = cb.data.split(":")
        row = db.execute("SELECT * FROM submissions WHERE id=?", (int(sid),)).fetchone()
    except ValueError:
        return await cb.answer("Xato ma'lumot", show_alert=True)
    if not row:
        return await cb.answer("Topilmadi", show_alert=True)
    if row["status"] != "pending":
        return await cb.answer("Bu natija allaqachon ko'rib chiqilgan", show_alert=True)

    approved = action == "ok"
    db.execute("UPDATE submissions SET status=? WHERE id=?", ("approved" if approved else "rejected", row["id"]))
    db.commit()

    label = "✅ Tasdiqlandi" if approved else "❌ Rad etildi"
    try:
        await cb.message.edit_caption(
            caption=f"{cb.message.html_text}\n\n{label} — {html.escape(cb.from_user.full_name)}",
            reply_markup=None)
    except TelegramBadRequest:
        pass

    if approved:
        text = "🎉 Tabriklaymiz! Natijangiz tasdiqlandi. Mukofot bo'yicha admin siz bilan bog'lanadi."
    else:
        text = ("😔 Natijangiz mukofot uchun qabul qilinmadi (100% natija emas yoki screenshot aniq emas). "
                "Screenshot noaniq bo'lgan bo'lsa, uni qaytadan yuborishingiz mumkin.")
    try:
        await bot.send_message(row["user_id"], text)
    except (TelegramForbiddenError, TelegramBadRequest):
        pass
    await cb.answer("Bajarildi")


# ===================== ADMIN BUYRUQLARI =====================
@router.message(Command("admin"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_admin(msg: Message):
    await msg.answer(
        "🛠 <b>Admin buyruqlari</b>\n\n"
        "/addchannel @kanal — kanal qo'shish\n"
        "/addchannel -100123... https://t.me/+havola — yopiq kanal\n"
        "/delchannel @kanal — kanalni olib tashlash\n"
        "/channels — kanallar ro'yxati\n"
        "/stats — statistika\n"
        "/winners — tasdiqlanganlar ro'yxati\n"
        "/broadcast matn — hammaga xabar yuborish\n"
        "/send ID yoki @username matn — bitta odamga xabar\n"
        "/reply matn — natija xabariga javoban, shu odamga yozish\n"
        "/newtest — yangi raund (hamma yana natija yubora oladi)")


@router.message(Command("addchannel"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_addchannel(msg: Message, command: CommandObject, bot: Bot):
    parts = (command.args or "").split()
    if not parts:
        return await msg.answer("Ishlatilishi:\n/addchannel @username\n/addchannel -100123... https://t.me/+havola")
    raw = parts[0]
    try:
        ref = chat_ref(raw)
    except ValueError:
        return await msg.answer("❌ Kanal @username yoki raqamli ID (-100...) ko'rinishida bo'lishi kerak.")
    if not raw.startswith("@") and len(parts) < 2:
        return await msg.answer("❌ Yopiq kanal uchun taklif havolasini ham yozing:\n/addchannel -100123... https://t.me/+havola")
    try:
        chat = await bot.get_chat(ref)
        me = await bot.get_chat_member(ref, bot.id)
        if me.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            return await msg.answer("❌ Avval botni shu kanalga admin qiling, keyin qayta urinib ko'ring.")
    except Exception as e:
        return await msg.answer(f"❌ Kanal topilmadi yoki bot kanalda yo'q:\n<code>{html.escape(str(e))}</code>")
    url = parts[1] if len(parts) > 1 else f"https://t.me/{raw.lstrip('@')}"
    if db.execute("SELECT 1 FROM channels WHERE id=?", (str(ref),)).fetchone():
        return await msg.answer("Bu kanal allaqachon ro'yxatda.")
    db.execute("INSERT INTO channels(id, title, url) VALUES(?,?,?)", (str(ref), chat.title or raw, url))
    db.commit()
    await msg.answer(f"✅ Qo'shildi: <b>{html.escape(chat.title or raw)}</b>\nJami kanallar: {len(get_channels())}")


@router.message(Command("delchannel"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_delchannel(msg: Message, command: CommandObject):
    arg = (command.args or "").strip()
    if not arg:
        return await msg.answer("Ishlatilishi: /delchannel @username")
    cur = db.execute("DELETE FROM channels WHERE lower(id)=lower(?)", (arg,))
    db.commit()
    await msg.answer("🗑 O'chirildi." if cur.rowcount else "Bunday kanal topilmadi.")


@router.message(Command("channels"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_channels(msg: Message):
    chans = get_channels()
    text = "\n".join(f"{i}. {html.escape(c['title'])} (<code>{c['id']}</code>)" for i, c in enumerate(chans, 1))
    await msg.answer(text or "Kanallar yo'q. Majburiy obuna o'chirilgan.")


@router.message(Command("stats"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_stats(msg: Message):
    rnd = get_round()
    users = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    st = {r["status"]: r["c"] for r in db.execute(
        "SELECT status, COUNT(*) c FROM submissions WHERE round=? GROUP BY status", (rnd,))}
    await msg.answer(
        f"📊 <b>Statistika</b> (raund {rnd})\n\n"
        f"👥 Botdan foydalanuvchilar: {users}\n"
        f"📥 Natija yuborganlar: {sum(st.values())}\n"
        f"⏳ Kutilmoqda: {st.get('pending', 0)}\n"
        f"✅ Tasdiqlangan: {st.get('approved', 0)}\n"
        f"❌ Rad etilgan: {st.get('rejected', 0)}")


@router.message(Command("winners"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_winners(msg: Message):
    rows = db.execute(
        "SELECT u.user_id, u.name, u.username FROM submissions s JOIN users u ON u.user_id=s.user_id "
        "WHERE s.round=? AND s.status='approved' ORDER BY s.id", (get_round(),)).fetchall()
    if not rows:
        return await msg.answer("Hozircha tasdiqlangan g'oliblar yo'q.")
    lines = [f"{i}. {html.escape(r['name'])} {('@' + r['username']) if r['username'] else ''} — <code>{r['user_id']}</code>"
             for i, r in enumerate(rows, 1)]
    await msg.answer("🏆 <b>G'oliblar</b>\n\n" + "\n".join(lines))


@router.message(Command("broadcast"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_broadcast(msg: Message, command: CommandObject, bot: Bot):
    text = (command.args or "").strip()
    if not text:
        return await msg.answer("Ishlatilishi: /broadcast Xabar matni")
    ids = [r["user_id"] for r in db.execute("SELECT user_id FROM users")]
    await msg.answer(f"📤 {len(ids)} ta foydalanuvchiga yuborilmoqda...")
    ok = fail = 0
    for uid in ids:
        try:
            await bot.send_message(uid, text)
            ok += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(uid, text)
                ok += 1
            except Exception:
                fail += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await msg.answer(f"✅ Yuborildi: {ok}\n❌ Yetmadi: {fail}")


def find_user_id(token: str):
    """ID (raqam) yoki @username bo'yicha foydalanuvchini topadi."""
    token = token.strip()
    if token.lstrip("-").isdigit():
        return int(token)
    r = db.execute("SELECT user_id FROM users WHERE lower(username)=lower(?)",
                   (token.lstrip("@"),)).fetchone()
    return r["user_id"] if r else None


async def deliver(bot: Bot, uid: int, text: str):
    """Xabarni yuboradi. Muvaffaqiyatli bo'lsa None, aks holda xato matnini qaytaradi."""
    try:
        await bot.send_message(uid, text)
        return None
    except TelegramForbiddenError:
        return "Foydalanuvchi botni bloklagan."
    except TelegramBadRequest as e:
        return f"Yuborilmadi (foydalanuvchi botga hech qachon /start bosmagan bo'lishi mumkin): {html.escape(str(e))}"


@router.message(Command("send"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_send(msg: Message, command: CommandObject, bot: Bot):
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) < 2:
        return await msg.answer("Ishlatilishi:\n/send 123456789 Xabar matni\n/send @username Xabar matni")
    uid = find_user_id(parts[0])
    if uid is None:
        return await msg.answer("❌ Bunday foydalanuvchi botda topilmadi. ID raqamini yozing yoki u botga /start bosgan bo'lishi kerak.")
    err = await deliver(bot, uid, parts[1])
    await msg.answer(f"❌ {err}" if err else f"✅ Yuborildi: <code>{uid}</code>")


@router.message(Command("reply"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_reply(msg: Message, command: CommandObject, bot: Bot):
    text = (command.args or "").strip()
    src = msg.reply_to_message
    if not text or not src:
        return await msg.answer("Ishlatilishi: natija xabariga <b>javob (Reply)</b> qilib yozing:\n/reply Xabar matni")
    m = re.search(r"🆔\s*(\d+)", (src.caption or src.text or ""))
    if not m:
        return await msg.answer("❌ Bu xabardan foydalanuvchi ID si topilmadi. Natija (📥) xabariga javob qiling yoki /send ishlating.")
    uid = int(m.group(1))
    err = await deliver(bot, uid, text)
    await msg.answer(f"❌ {err}" if err else f"✅ Yuborildi: <code>{uid}</code>")


@router.message(Command("newtest"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_newtest(msg: Message):
    n = get_round() + 1
    set_round(n)
    await msg.answer(f"🔁 Yangi raund: <b>{n}</b>. Endi hamma yana natija yubora oladi.\n"
                     "Xabar berish uchun /broadcast dan foydalaning.")


# ===================== QOLGAN XABARLAR =====================
@router.message(F.chat.type == "private", ~F.from_user.id.in_(ADMIN_IDS))
async def fallback(msg: Message):
    await msg.answer("Natija screenshotini <b>rasm</b> sifatida yuboring yoki /start bosing.")


# ===================== ISHGA TUSHIRISH =====================
async def setup_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni boshlash"),
        BotCommand(command="status", description="Natijam holati"),
        BotCommand(command="help", description="Qoidalar"),
    ])
    for aid in ADMIN_IDS:
        try:
            await bot.set_my_commands(
                [BotCommand(command="admin", description="Admin buyruqlari"),
                 BotCommand(command="stats", description="Statistika"),
                 BotCommand(command="winners", description="G'oliblar"),
                 BotCommand(command="channels", description="Kanallar"),
                 BotCommand(command="start", description="Botni boshlash")],
                scope=BotCommandScopeChat(chat_id=aid))
        except Exception:
            pass


async def main():
    problems = []
    if ":" not in BOT_TOKEN or "BU_YERGA" in BOT_TOKEN:
        problems.append("BOT_TOKEN to'ldirilmagan")
    if not ADMIN_IDS:
        problems.append("ADMIN_IDS to'ldirilmagan")
    if not WEBAPP_URL.startswith("https://") or "sizning-sayt" in WEBAPP_URL:
        problems.append("WEBAPP_URL to'g'ri https:// manzil bo'lishi kerak")
    if problems:
        sys.exit("❌ bot.py ning eng tepasidagi SOZLAMALAR qismini to'ldiring: " + "; ".join(problems))

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=False)
    await setup_commands(bot)
    me = await bot.get_me()
    log.info("Bot ishga tushdi: @%s", me.username)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
