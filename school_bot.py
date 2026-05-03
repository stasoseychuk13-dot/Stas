"""
╔══════════════════════════════════════════╗
║       🏫  ШКІЛЬНИЙ TELEGRAM БОТ         ║
╠══════════════════════════════════════════╣
║  pip install aiogram apscheduler        ║
║  python school_bot.py                   ║
╠══════════════════════════════════════════╣
║  Команди адміна:                        ║
║    /admin ПАРОЛЬ  — увійти як адмін     ║
╚══════════════════════════════════════════╝
"""

import asyncio
import json
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ══════════════════════════════════════════
#  ⚙️  НАЛАШТУВАННЯ
# ══════════════════════════════════════════
BOT_TOKEN      = "8682554539:AAHWE1F_epaNf0n1DbgP2RbfH4ayX4qPC1Y"   # ← токен від @BotFather
ADMIN_PASSWORD = "school2025"        # ← пароль для адміна
DATA_FILE      = "school_data.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════
#  📋  РОЗКЛАД ДЗВІНКІВ
# ══════════════════════════════════════════
BELLS = [
    {"n": 1, "s": "08:30", "e": "09:15", "b": 10},
    {"n": 2, "s": "09:25", "e": "10:10", "b": 10},
    {"n": 3, "s": "10:20", "e": "11:05", "b": 20},
    {"n": 4, "s": "11:25", "e": "12:10", "b": 30},
    {"n": 5, "s": "12:40", "e": "13:25", "b": 10},
    {"n": 6, "s": "13:35", "e": "14:20", "b": 10},
    {"n": 7, "s": "14:30", "e": "15:15", "b": 0},
]

DAYS = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця"]

DAY_EMOJI = {
    "Понеділок": "1️⃣",
    "Вівторок":  "2️⃣",
    "Середа":    "3️⃣",
    "Четвер":    "4️⃣",
    "П'ятниця":  "5️⃣",
}

DEFAULT_SCHEDULE = {
    "Понеділок": ["Математика", "Українська мова", "Фізика", "Хімія", "Біологія", "Англійська", "Фізкультура"],
    "Вівторок":  ["Англійська", "Математика", "Географія", "Укр. Літ-ра", "Фізика", "Хімія", "Трудове навч."],
    "Середа":    ["Фізика", "Біологія", "Математика", "Англійська", "Географія", "Укр. мова", "Інформатика"],
    "Четвер":    ["Хімія", "Математика", "Фізика", "Укр. мова", "Англійська", "Біологія", "Фізкультура"],
    "П'ятниця":  ["Укр. Літ-ра", "Географія", "Англійська", "Математика", "Фізика", "Хімія", "Класна год."],
}

# ══════════════════════════════════════════
#  🗄️  БАЗА ДАНИХ
# ══════════════════════════════════════════
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "schedule":   DEFAULT_SCHEDULE,
        "homework":   {},
        "users":      [],
        "admins":     [],
        "hw_stats":   {},
        "notif_time": "20:00",
    }

def save_data(d: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

db = load_data()

def reg(uid: int):
    s = str(uid)
    if s not in db["users"]:
        db["users"].append(s)
        save_data(db)

def is_admin(uid: int) -> bool:
    return str(uid) in db["admins"]

# ══════════════════════════════════════════
#  🔧  FSM СТАНИ
# ══════════════════════════════════════════
class A(StatesGroup):
    pass_wait     = State()
    menu          = State()
    sched_day     = State()
    sched_lessons = State()
    hw_day        = State()
    hw_lesson     = State()
    hw_text       = State()
    notif_time    = State()

class U(StatesGroup):
    main   = State()
    hw_day = State()

# ══════════════════════════════════════════
#  ⌨️  КЛАВІАТУРИ
# ══════════════════════════════════════════
def kb_main():
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="📚 Розклад"),
            KeyboardButton(text="🔔 Дзвінки"),
            KeyboardButton(text="✏️ ДЗ"),
        ]],
        resize_keyboard=True,
        persistent=True,
    )

def kb_days(prefix: str) -> InlineKeyboardMarkup:
    """Кожен день — окремий рядок з повною назвою."""
    wd = datetime.now().weekday()
    rows = []
    for i, day in enumerate(DAYS):
        emoji  = DAY_EMOJI[day]
        today  = "  ← сьогодні" if i == wd else ""
        rows.append([InlineKeyboardButton(
            text=f"{emoji}  {day}{today}",
            callback_data=f"{prefix}:{day}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚  Редагувати розклад",   callback_data="adm:sched")],
        [InlineKeyboardButton(text="✏️  Додати / змінити ДЗ",  callback_data="adm:hw")],
        [InlineKeyboardButton(text="⏰  Час нагадування",       callback_data="adm:notif")],
        [InlineKeyboardButton(text="📊  Статистика ДЗ",         callback_data="adm:stats")],
        [InlineKeyboardButton(text="❌  Вийти з панелі",        callback_data="adm:exit")],
    ])

def kb_back(cb_data: str, label: str = "◀️  Назад") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=cb_data)]
    ])

# ══════════════════════════════════════════
#  📝  ФОРМАТУВАННЯ
# ══════════════════════════════════════════
def fmt_schedule(day: str) -> str:
    lessons = db["schedule"].get(day, [])
    hw      = db["homework"].get(day, {})
    wd      = datetime.now().weekday()
    today   = DAYS[wd] if wd < 5 else None
    marker  = "  ← сьогодні" if day == today else ""
    lines   = [f"📅  <b>{DAY_EMOJI[day]}  {day}</b>{marker}\n"]
    for i, name in enumerate(lessons, 1):
        bell    = BELLS[i - 1]
        hw_mark = "  📝" if str(i) in hw else ""
        lines.append(
            f"<b>{i}.</b>  {name}{hw_mark}\n"
            f"      🕐  {bell['s']} – {bell['e']}"
        )
    if any(str(i) in hw for i in range(1, 8)):
        lines.append("\n<i>📝 — є домашнє завдання</i>")
    return "\n".join(lines)

def fmt_bells() -> str:
    lines = ["🔔  <b>Розклад дзвінків</b>\n"]
    for b in BELLS:
        br = f"перерва  {b['b']} хв" if b["b"] else "останній урок"
        lines.append(
            f"<b>Урок {b['n']}</b>  │  {b['s']} – {b['e']}\n"
            f"              ╰─  {br}"
        )
    return "\n".join(lines)

def fmt_hw(day: str) -> str:
    hw       = db["homework"].get(day, {})
    schedule = db["schedule"].get(day, [])
    if not hw:
        return (
            f"✏️  <b>{DAY_EMOJI[day]}  ДЗ на {day}</b>\n\n"
            "🎉  Домашнього завдання немає!"
        )
    lines = [f"✏️  <b>{DAY_EMOJI[day]}  ДЗ на {day}</b>\n"]
    for ns, text in sorted(hw.items(), key=lambda x: int(x[0])):
        idx    = int(ns) - 1
        lesson = schedule[idx] if idx < len(schedule) else f"Урок {ns}"
        lines.append(f"📖  <b>{lesson}</b>\n    {text}\n")
    return "\n".join(lines)

def fmt_stats() -> str:
    stats = db.get("hw_stats", {})
    if not stats:
        return "📊  <b>Статистика порожня</b>\n\nЩе ніхто не відповів на нагадування."
    lines = ["📊  <b>Статистика ДЗ</b>\n"]
    for uid, dates in stats.items():
        yes   = sum(1 for v in dates.values() if v)
        no    = sum(1 for v in dates.values() if not v)
        total = yes + no
        pct   = round(yes / total * 100) if total else 0
        lines.append(f"👤  {uid}\n    ✅ {yes}  ❌ {no}  │  {pct}% виконання\n")
    return "\n".join(lines)

# ══════════════════════════════════════════
#  🤖  BOT / ROUTER
# ══════════════════════════════════════════
bot    = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
router = Router()
dp     = Dispatcher(storage=MemoryStorage())
dp.include_router(router)

# ══════════════════════════════════════════
#  /start
# ══════════════════════════════════════════
@router.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext):
    reg(msg.from_user.id)
    await state.set_state(U.main)
    name = msg.from_user.first_name or "учню"
    await msg.answer(
        f"👋  Привіт, <b>{name}</b>!\n\n"
        "🏫  <b>Шкільний бот</b> — твій помічник:\n\n"
        "📚  <b>Розклад</b> — уроки на кожен день з часом\n"
        "🔔  <b>Дзвінки</b> — точний розклад дзвінків\n"
        "✏️  <b>ДЗ</b> — домашнє завдання\n\n"
        "Обирай розділ 👇",
        reply_markup=kb_main(),
    )

# ══════════════════════════════════════════
#  /admin
# ══════════════════════════════════════════
def _make_admin(uid: int):
    s = str(uid)
    if s not in db["admins"]:
        db["admins"].append(s)
        save_data(db)

@router.message(Command("admin"))
async def cmd_admin(msg: Message, state: FSMContext):
    parts = msg.text.strip().split(maxsplit=1)
    pwd   = parts[1].strip() if len(parts) > 1 else None
    if pwd == ADMIN_PASSWORD:
        _make_admin(msg.from_user.id)
        await state.set_state(A.menu)
        await msg.answer("✅  Ви увійшли як <b>адмін</b>!", reply_markup=kb_main())
        await msg.answer("🛠  <b>Панель адміна</b>", reply_markup=kb_admin_menu())
    elif pwd is None:
        await state.set_state(A.pass_wait)
        await msg.answer("🔐  Введіть пароль адміна:")
    else:
        await msg.answer("❌  Невірний пароль.")

@router.message(A.pass_wait)
async def admin_pass(msg: Message, state: FSMContext):
    if msg.text.strip() == ADMIN_PASSWORD:
        _make_admin(msg.from_user.id)
        await state.set_state(A.menu)
        await msg.answer("✅  Ви увійшли як <b>адмін</b>!", reply_markup=kb_main())
        await msg.answer("🛠  <b>Панель адміна</b>", reply_markup=kb_admin_menu())
    else:
        await msg.answer("❌  Невірний пароль. Спробуйте ще раз:")

# ══════════════════════════════════════════
#  АДМІН — КОЛЛБЕКИ
# ══════════════════════════════════════════
@router.callback_query(F.data == "adm:back")
async def adm_back(cb: CallbackQuery, state: FSMContext):
    await state.set_state(A.menu)
    await cb.message.edit_text("🛠  <b>Панель адміна</b>", reply_markup=kb_admin_menu())
    await cb.answer()

@router.callback_query(F.data == "adm:exit")
async def adm_exit(cb: CallbackQuery, state: FSMContext):
    await state.set_state(U.main)
    await cb.message.edit_text("👋  Вийшли з панелі адміна.")
    await cb.answer()

# ─ Розклад ─
@router.callback_query(F.data == "adm:sched")
async def adm_sched(cb: CallbackQuery, state: FSMContext):
    await state.set_state(A.sched_day)
    await cb.message.edit_text(
        "📅  <b>Редагування розкладу</b>\n\nВиберіть день:",
        reply_markup=kb_days("aeday"),
    )
    await cb.answer()

@router.callback_query(A.sched_day, F.data.startswith("aeday:"))
async def adm_sched_day(cb: CallbackQuery, state: FSMContext):
    day = cb.data.split(":", 1)[1]
    await state.update_data(edit_day=day)
    cur     = db["schedule"].get(day, [])
    cur_txt = "\n".join(f"{i+1}. {l}" for i, l in enumerate(cur))
    await cb.message.edit_text(
        f"📅  <b>{day}</b> — поточний розклад:\n\n"
        f"<code>{cur_txt}</code>\n\n"
        "✏️  Надішліть новий розклад:\n"
        "<i>Кожен предмет з нового рядка, рівно 7 рядків</i>",
        reply_markup=kb_back("adm:sched"),
    )
    await state.set_state(A.sched_lessons)
    await cb.answer()

@router.message(A.sched_lessons)
async def adm_sched_save(msg: Message, state: FSMContext):
    lessons = [l.strip() for l in msg.text.strip().splitlines() if l.strip()]
    if len(lessons) != 7:
        await msg.answer(
            f"⚠️  Потрібно 7 предметів, ви надіслали <b>{len(lessons)}</b>.\n"
            "Спробуйте ще раз:"
        )
        return
    d = await state.get_data()
    db["schedule"][d["edit_day"]] = lessons
    save_data(db)
    await state.set_state(A.menu)
    await msg.answer(
        f"✅  Розклад на <b>{d['edit_day']}</b> збережено!",
        reply_markup=kb_admin_menu(),
    )

# ─ ДЗ ─
@router.callback_query(F.data == "adm:hw")
async def adm_hw(cb: CallbackQuery, state: FSMContext):
    await state.set_state(A.hw_day)
    await cb.message.edit_text(
        "✏️  <b>Домашнє завдання</b>\n\nВиберіть день:",
        reply_markup=kb_days("ahday"),
    )
    await cb.answer()

@router.callback_query(A.hw_day, F.data.startswith("ahday:"))
async def adm_hw_day(cb: CallbackQuery, state: FSMContext):
    day     = cb.data.split(":", 1)[1]
    await state.update_data(hw_day=day)
    lessons = db["schedule"].get(day, [])
    hw      = db["homework"].get(day, {})
    rows    = []
    for i, name in enumerate(lessons, 1):
        mark = "  ✅" if str(i) in hw else ""
        rows.append([InlineKeyboardButton(
            text=f"{i}.  {name}{mark}",
            callback_data=f"ahlesson:{i}",
        )])
    rows.append([InlineKeyboardButton(text="◀️  Назад", callback_data="adm:hw")])
    await cb.message.edit_text(
        f"✏️  <b>{day}</b> — оберіть урок:\n<i>✅ — вже є ДЗ</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await state.set_state(A.hw_lesson)
    await cb.answer()

@router.callback_query(A.hw_lesson, F.data.startswith("ahlesson:"))
async def adm_hw_lesson(cb: CallbackQuery, state: FSMContext):
    num = cb.data.split(":", 1)[1]
    await state.update_data(hw_num=num)
    d       = await state.get_data()
    day     = d["hw_day"]
    cur     = db["homework"].get(day, {}).get(num, "")
    cur_txt = f"\n\n<b>Поточне ДЗ:</b>\n<i>{cur}</i>" if cur else "\n\n<i>ДЗ поки немає</i>"
    await cb.message.edit_text(
        f"✏️  Урок <b>{num}</b>  /  {day}{cur_txt}\n\n"
        "Напишіть текст ДЗ:\n"
        "<i>Щоб видалити — надішліть   -</i>",
    )
    await state.set_state(A.hw_text)
    await cb.answer()

@router.message(A.hw_text)
async def adm_hw_save(msg: Message, state: FSMContext):
    d   = await state.get_data()
    day = d["hw_day"]
    num = d["hw_num"]
    db["homework"].setdefault(day, {})
    if msg.text.strip() == "-":
        db["homework"][day].pop(num, None)
        text = f"🗑  ДЗ для уроку <b>{num}</b> / {day} видалено."
    else:
        db["homework"][day][num] = msg.text.strip()
        text = f"✅  ДЗ для уроку <b>{num}</b> / {day} збережено!"
    save_data(db)
    await state.set_state(A.menu)
    await msg.answer(text, reply_markup=kb_admin_menu())

# ─ Час нагадування ─
@router.callback_query(F.data == "adm:notif")
async def adm_notif(cb: CallbackQuery, state: FSMContext):
    await state.set_state(A.notif_time)
    await cb.message.edit_text(
        f"⏰  Поточний час нагадування: <b>{db['notif_time']}</b>\n\n"
        "Введіть новий час у форматі  <code>ГГ:ХХ</code>\n"
        "Наприклад:  <code>20:00</code>",
        reply_markup=kb_back("adm:back"),
    )
    await cb.answer()

@router.message(A.notif_time)
async def adm_notif_save(msg: Message, state: FSMContext):
    t = msg.text.strip()
    try:
        h, m = map(int, t.split(":"))
        assert 0 <= h <= 23 and 0 <= m <= 59
        db["notif_time"] = f"{h:02d}:{m:02d}"
        save_data(db)
        reschedule_job()
        await state.set_state(A.menu)
        await msg.answer(
            f"✅  Час нагадування: <b>{db['notif_time']}</b>",
            reply_markup=kb_admin_menu(),
        )
    except Exception:
        await msg.answer(
            "⚠️  Невірний формат. Введіть  <code>ГГ:ХХ</code>  (наприклад  <code>19:30</code>):"
        )

# ─ Статистика ─
@router.callback_query(F.data == "adm:stats")
async def adm_stats(cb: CallbackQuery):
    await cb.message.edit_text(fmt_stats(), reply_markup=kb_admin_menu())
    await cb.answer()

# ══════════════════════════════════════════
#  👤  КОРИСТУВАЧ
# ══════════════════════════════════════════
@router.message(F.text == "📚 Розклад")
async def user_schedule(msg: Message):
    wd = datetime.now().weekday()
    note = f"  (сьогодні — <b>{DAYS[wd]}</b>)" if wd < 5 else "  (сьогодні вихідний 🎉)"
    await msg.answer(
        f"📅  <b>Розклад уроків</b>{note}\n\nВиберіть день:",
        reply_markup=kb_days("sday"),
    )

@router.callback_query(F.data.startswith("sday:"))
async def user_schedule_day(cb: CallbackQuery):
    day = cb.data.split(":", 1)[1]
    if day == "back":
        wd   = datetime.now().weekday()
        note = f"  (сьогодні — <b>{DAYS[wd]}</b>)" if wd < 5 else "  (сьогодні вихідний 🎉)"
        await cb.message.edit_text(
            f"📅  <b>Розклад уроків</b>{note}\n\nВиберіть день:",
            reply_markup=kb_days("sday"),
        )
        await cb.answer()
        return
    back = kb_back("sday:back", "◀️  Інший день")
    await cb.message.edit_text(fmt_schedule(day), reply_markup=back)
    await cb.answer()

@router.message(F.text == "🔔 Дзвінки")
async def user_bells(msg: Message):
    await msg.answer(fmt_bells())

@router.message(F.text == "✏️ ДЗ")
async def user_hw(msg: Message, state: FSMContext):
    await state.set_state(U.hw_day)
    await msg.answer(
        "✏️  <b>Домашнє завдання</b>\n\nВиберіть день:",
        reply_markup=kb_days("hday"),
    )

@router.callback_query(F.data.startswith("hday:"))
async def user_hw_day(cb: CallbackQuery, state: FSMContext):
    day = cb.data.split(":", 1)[1]
    if day == "back":
        await state.set_state(U.hw_day)
        await cb.message.edit_text(
            "✏️  <b>Домашнє завдання</b>\n\nВиберіть день:",
            reply_markup=kb_days("hday"),
        )
        await cb.answer()
        return
    await state.set_state(U.main)
    back = kb_back("hday:back", "◀️  Інший день")
    await cb.message.edit_text(fmt_hw(day), reply_markup=back)
    await cb.answer()

# ══════════════════════════════════════════
#  🌙  ВЕЧІРНЄ НАГАДУВАННЯ
# ══════════════════════════════════════════
async def evening_notify():
    wd = datetime.now().weekday()
    if wd >= 4:
        return
    tomorrow = DAYS[wd + 1]
    hw       = db["homework"].get(tomorrow, {})
    schedule = db["schedule"].get(tomorrow, [])
    if not hw:
        return

    hw_lines = []
    for ns, text in sorted(hw.items(), key=lambda x: int(x[0])):
        idx    = int(ns) - 1
        lesson = schedule[idx] if idx < len(schedule) else f"Урок {ns}"
        hw_lines.append(f"📖  <b>{lesson}</b>\n    {text}")

    body = "\n\n".join(hw_lines)
    text = (
        f"🌙  <b>Вечірня перевірка!</b>\n\n"
        f"Завтра  <b>{DAY_EMOJI[tomorrow]}  {tomorrow}</b>\n\n"
        f"{body}\n\n"
        "Ти зробив домашнє завдання? 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅  Так, зробив!",  callback_data=f"done:yes:{tomorrow}"),
        InlineKeyboardButton(text="❌  Ще ні",         callback_data=f"done:no:{tomorrow}"),
    ]])
    for uid in db["users"]:
        try:
            await bot.send_message(int(uid), text, reply_markup=kb)
        except Exception as e:
            log.warning(f"Не надіслано {uid}: {e}")

@router.callback_query(F.data.startswith("done:"))
async def done_answer(cb: CallbackQuery):
    parts = cb.data.split(":", 2)
    ans   = parts[1]
    day   = parts[2]
    uid   = str(cb.from_user.id)
    key   = datetime.now().strftime("%Y-%m-%d")
    db["hw_stats"].setdefault(uid, {})[key] = (ans == "yes")
    save_data(db)
    if ans == "yes":
        reply = "🎉  <b>Молодець!</b> Так тримати! Завтра все вийде! 💪"
    else:
        reply = "💪  Нічого страшного! Ще є час — зроби до завтра!"
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(reply)
    await cb.answer()

# ══════════════════════════════════════════
#  ⏰  ПЛАНУВАЛЬНИК
# ══════════════════════════════════════════
scheduler = AsyncIOScheduler(timezone="Europe/Kiev")

def reschedule_job():
    if scheduler.get_job("ev"):
        scheduler.remove_job("ev")
    h, m = map(int, db["notif_time"].split(":"))
    scheduler.add_job(evening_notify, "cron", hour=h, minute=m, id="ev")
    log.info(f"Нагадування заплановано на {db['notif_time']}")

# ══════════════════════════════════════════
#  🚀  ЗАПУСК
# ══════════════════════════════════════════
async def main():
    reschedule_job()
    scheduler.start()
    log.info("✅  Бот запущено!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
