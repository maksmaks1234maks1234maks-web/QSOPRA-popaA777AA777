"""
🔍 Sherlock Telegram Bot + поиск по номеру телефона
Всё в одном файле.

Зависимости:
    python -m pip install pyTelegramBotAPI requests phonenumbers

Запуск:
    python bot.py
"""

import concurrent.futures
import re
import requests
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# phonenumbers — опционально: без него бот тоже работает
try:
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone as pn_tz
    HAS_PN = True
except ImportError:
    HAS_PN = False

# ==================== КОНФИГ ====================

BOT_TOKEN = "9098946125:AAG9IWrh1pV_Hh-KfaULFqm4yWnD1ggwDLA"
TIMEOUT = 5                      # таймаут HTTP-запросов к сайтам, сек
EYE_OF_GOD_API = ""              # токен eyeofgodapi.com (опционально) — поиск по утечкам

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ==================== БАЗА САЙТОВ ====================

SITES = {
    "GitHub":        "https://github.com/{username}",
    "Telegram":      "https://t.me/{username}",
    "Reddit":        "https://www.reddit.com/user/{username}",
    "Instagram":     "https://www.instagram.com/{username}/",
    "X (Twitter)":   "https://x.com/{username}",
    "TikTok":        "https://www.tiktok.com/@{username}",
    "VK":            "https://vk.com/{username}",
    "Steam":         "https://steamcommunity.com/id/{username}",
    "SoundCloud":    "https://soundcloud.com/{username}",
    "Pinterest":     "https://www.pinterest.com/{username}",
    "Flickr":        "https://www.flickr.com/people/{username}",
    "Behance":       "https://www.behance.net/{username}",
    "Medium":        "https://medium.com/@{username}",
    "DeviantArt":    "https://{username}.deviantart.com",
    "Tumblr":        "https://{username}.tumblr.com",
    "Chess":         "https://www.chess.com/member/{username}",
    "Codeforces":    "https://codeforces.com/profile/{username}",
    "Habr":          "https://habr.com/ru/users/{username}/",
    "Bitbucket":     "https://bitbucket.org/{username}/",
    "Docker Hub":    "https://hub.docker.com/u/{username}",
    "Spotify":       "https://open.spotify.com/user/{username}",
    "Twitch":        "https://www.twitch.tv/{username}",
    "Wattpad":       "https://www.wattpad.com/user/{username}",
    "WordPress":     "https://{username}.wordpress.com",
    "Blogger":       "https://{username}.blogspot.com",
    "AskFM":         "https://ask.fm/{username}",
    "Cash App":      "https://cash.app/${username}",
    "Codewars":      "https://www.codewars.com/users/{username}",
    "Dribbble":      "https://dribbble.com/{username}",
    "Fiverr":        "https://www.fiverr.com/{username}",
    "Gravatar":      "https://en.gravatar.com/{username}",
    "Hacker News":   "https://news.ycombinator.com/user?id={username}",
    "HackerOne":     "https://hackerone.com/{username}",
    "Hive":          "https://hive.blog/@{username}",
    "Instructables": "https://www.instructables.com/member/{username}/",
    "Last.fm":       "https://www.last.fm/user/{username}",
    "LeetCode":      "https://leetcode.com/{username}/",
    "Linktree":      "https://linktr.ee/{username}",
    "Mastodon":      "https://mastodon.social/@{username}",
    "Mixcloud":      "https://www.mixcloud.com/{username}/",
    "MyAnimeList":   "https://myanimelist.net/profile/{username}",
    "Newgrounds":    "https://{username}.newgrounds.com",
    "NPM":           "https://www.npmjs.com/~{username}",
    "PasteBin":      "https://pastebin.com/u/{username}",
    "Slideshare":    "https://slideshare.net/{username}",
    "Trakt":         "https://trakt.tv/users/{username}",
    "Vimeo":         "https://vimeo.com/{username}",
    "WordPressOrg":  "https://profiles.wordpress.org/{username}/",
}

# Сайты, где 404 = «найдено» (инвертированная логика)
INVERTED = set()

# ==================== ЛОГИКА ПОИСКА ПО НИКУ ====================

def check_site(name: str, url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=False)
        ok = (r.status_code == 404) if name in INVERTED else (r.status_code == 200)
        return (name, url if ok else None)
    except requests.RequestException:
        return (name, None)


def search(username: str, progress_cb=None):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        futures = [
            pool.submit(check_site, name, url.format(username=username))
            for name, url in SITES.items()
        ]
        for fut in concurrent.futures.as_completed(futures):
            name, url = fut.result()
            if url:
                results.append((name, url))
                if progress_cb:
                    progress_cb(len(results))
    return sorted(results)

# ==================== ЛОГИКА ПОИСКА ПО НОМЕРУ ====================

# Мини-справочник кодов стран (используется, если нет phonenumbers)
COUNTRY_CODES = {
    "7": "🇷🇺 Россия / 🇰🇿 Казахстан",
    "375": "🇧🇾 Беларусь", "380": "🇺🇦 Украина", "373": "🇲🇩 Молдова",
    "995": "🇬🇪 Грузия", "374": "🇦🇲 Армения", "994": "🇦🇿 Азербайджан",
    "996": "🇰🇬 Кыргызстан", "992": "🇹🇯 Таджикистан", "998": "🇺🇿 Узбекистан",
    "371": "🇱🇻 Латвия", "370": "🇱🇹 Литва", "372": "🇪🇪 Эстония",
    "1": "🇺🇸 США / Канада", "44": "🇬🇧 Великобритания", "49": "🇩🇪 Германия",
    "33": "🇫🇷 Франция", "39": "🇮🇹 Италия", "34": "🇪🇸 Испания",
    "48": "🇵🇱 Польша", "420": "🇨🇿 Чехия", "90": "🇹🇷 Турция",
    "86": "🇨🇳 Китай", "81": "🇯🇵 Япония", "82": "🇰🇷 Корея",
    "91": "🇮🇳 Индия", "55": "🇧🇷 Бразилия", "971": "🇦🇪 ОАЭ",
}


def normalize_phone(raw: str):
    """Возвращает (digits, is_full). Для РФ/СНГ подставляет +7, если номер начинается с 8."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits, digits.startswith("+") or raw.strip().startswith("+")


def phone_info(raw: str) -> dict | None:
    """Валидация + страна, регион, оператор, часовой пояс."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) < 7 or len(digits) > 15:
        return None

    international = raw.strip()
    if not international.startswith("+"):
        international = "+" + digits

    # 1) Точный разбор через phonenumbers
    if HAS_PN:
        try:
            for region in (None, "RU", "KZ", "BY", "UA"):
                try:
                    num = phonenumbers.parse(raw, region)
                except phonenumbers.NumberParseException:
                    continue
                if phonenumbers.is_valid_number(num):
                    return {
                        "international": phonenumbers.format_number(
                            num, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                        "country": geocoder.country_name_for_number(num, "ru") or "неизвестно",
                        "region": geocoder.description_for_number(num, "ru") or "—",
                        "carrier": carrier.name_for_number(num, "ru") or "неизвестен",
                        "timezones": ", ".join(pn_tz.time_zones_for_number(num)) or "—",
                        "national": str(num.national_number),
                        "country_code": f"+{num.country_code}",
                    }
        except Exception:
            pass

    # 2) Фолбэк без phonenumbers — по коду страны
    for code_len in (3, 2, 1):
        code = digits[:code_len]
        if code in COUNTRY_CODES:
            return {
                "international": international,
                "country": COUNTRY_CODES[code],
                "region": "—",
                "carrier": "неизвестен (установи phonenumbers)",
                "timezones": "—",
                "national": digits[code_len:],
                "country_code": "+" + code,
            }
    return None


def phone_leaks(national: str) -> tuple[list, list]:
    """Поиск по открытым утечкам через eyeofgodapi.com (нужен токен)."""
    if not EYE_OF_GOD_API:
        return [], []
    url = f"https://eyeofgodapi.com/api/search?apikey={EYE_OF_GOD_API}&term={national}"
    try:
        data = requests.get(url, headers=HEADERS, timeout=20).json()
        names, socials = set(), set()
        for row in data.get("data", []) or []:
            if not isinstance(row, dict):
                continue
            for key in ("fio", "ФИО", "name", "fullname"):
                v = row.get(key)
                if v and str(v).strip() not in ("-", ""):
                    names.add(str(v).strip())
            for key in ("tg", "telegram", "vk", "inst", "instagram", "email"):
                v = row.get(key)
                if v and str(v).strip() not in ("-", ""):
                    socials.add(f"{key}: {v}")
        return sorted(names), sorted(socials)
    except Exception:
        return [], []


def phone_report(raw: str) -> str | None:
    info = phone_info(raw)
    if not info:
        return None

    text = (
        "📱 <b>Отчёт по номеру</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"☎️ Номер: <code>{info['international']}</code>\n"
        f"🌍 Страна: {info['country']}\n"
        f"📍 Регион: {info['region']}\n"
        f"📶 Оператор: {info['carrier']}\n"
        f"🕐 Часовой пояс: {info['timezones']}\n"
        f"🔢 Код страны: {info['country_code']}\n"
    )

    names, socials = phone_leaks(info["national"])
    if names:
        text += "\n🧑 <b>Имена из утечек:</b>\n" + "\n".join(f"• {n}" for n in names[:10])
    if socials:
        text += "\n\n🔗 <b>Привязанные аккаунты:</b>\n" + "\n".join(f"• {s}" for s in socials[:10])

    if not EYE_OF_GOD_API:
        text += "\n\n<i>💡 Базы утечек не проверялись — не задан EYE_OF_GOD_API.</i>"
    return text

# ==================== БОТ ====================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

WELCOME = (
    "🔍 <b>Sherlock Bot</b>\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "Ищу аккаунты по нику и информацию по номеру телефона.\n\n"
    "<b>Команды:</b>\n"
    "/search — поиск по нику\n"
    "/phone — поиск по номеру телефона\n"
    "/sites — поддерживаемые сайты\n"
    "/help — помощь\n\n"
    "Или жми кнопку ниже 👇"
)

HELP = (
    "ℹ️ <b>Как пользоваться</b>\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "<b>🔍 По нику:</b>\n"
    "Нажми «🔍 Ник» → введи username → получи список найденных профилей.\n\n"
    "<b>📱 По телефону:</b>\n"
    "Нажми «📱 Телефон» → введи номер в любом формате "
    "(<code>+79123456789</code> или <code>89123456789</code>) → "
    "получи страну, регион, оператора и часовой пояс.\n\n"
    f"🌐 По нику проверяется {len(SITES)} сайтов за один запрос "
    "(до 10–20 секунд)."
)

SITES_LIST = "🌐 <b>Поддерживаемые сайты</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(
    f"• {name}" for name in sorted(SITES.keys())
)

# ---------- Клавиатуры ----------

def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔍 Ник", callback_data="start_search"),
        InlineKeyboardButton("📱 Телефон", callback_data="start_phone"),
    )
    kb.add(
        InlineKeyboardButton("🌐 Сайты", callback_data="show_sites"),
        InlineKeyboardButton("ℹ️ Помощь", callback_data="show_help"),
    )
    kb.add(InlineKeyboardButton("🔄 Обновить меню", callback_data="main_menu"))
    return kb


def back_button() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    return kb


def results_menu(username: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔄 Ещё раз", callback_data="start_search"),
        InlineKeyboardButton("🏠 Меню", callback_data="main_menu"),
    )
    kb.add(InlineKeyboardButton(
        "🔗 Поиск в Google",
        url=f"https://www.google.com/search?q=%22{username}%22",
    ))
    return kb


def phone_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📱 Другой номер", callback_data="start_phone"),
        InlineKeyboardButton("🏠 Меню", callback_data="main_menu"),
    )
    return kb

# ---------- Хендлеры ----------

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    bot.send_message(m.chat.id, WELCOME, reply_markup=main_menu())


@bot.message_handler(commands=["help"])
def cmd_help(m):
    bot.send_message(m.chat.id, HELP, reply_markup=back_button())


@bot.message_handler(commands=["sites"])
def cmd_sites(m):
    bot.send_message(m.chat.id, SITES_LIST, reply_markup=back_button())


@bot.message_handler(commands=["search"])
def cmd_search(m):
    ask_username(m.chat.id)


@bot.message_handler(commands=["phone"])
def cmd_phone(m):
    ask_phone(m.chat.id)


@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    data = call.data
    try:
        if data == "main_menu":
            bot.edit_message_text(WELCOME, call.message.chat.id,
                                  call.message.message_id, reply_markup=main_menu())
        elif data == "start_search":
            bot.answer_callback_query(call.id)
            ask_username(call.message.chat.id)
        elif data == "start_phone":
            bot.answer_callback_query(call.id)
            ask_phone(call.message.chat.id)
        elif data == "show_sites":
            bot.edit_message_text(SITES_LIST, call.message.chat.id,
                                  call.message.message_id, reply_markup=back_button())
        elif data == "show_help":
            bot.edit_message_text(HELP, call.message.chat.id,
                                  call.message.message_id, reply_markup=back_button())
    except Exception:
        pass
    bot.answer_callback_query(call.id)


# ---------- Диалог: поиск по нику ----------

def ask_username(chat_id):
    msg = bot.send_message(
        chat_id,
        "🔎 <b>Введи ник для поиска</b>\n"
        "<i>Например: username</i>",
    )
    bot.register_next_step_handler(msg, do_search)


def do_search(m):
    username = (m.text or "").strip().lstrip("@")
    if not username or len(username) > 50 or any(c.isspace() for c in username):
        bot.send_message(m.chat.id, "⚠️ Некорректный ник. Попробуй ещё раз: /search")
        return

    status = bot.send_message(
        m.chat.id,
        f"⏳ Ищу <code>{username}</code>...\n"
        f"🌐 Проверяю {len(SITES)} сайтов.",
    )

    def progress(n):
        if n and n % 10 == 0:
            try:
                bot.edit_message_text(
                    f"⏳ Ищу <code>{username}</code>...\n✅ Найдено: <b>{n}</b>",
                    m.chat.id, status.message_id,
                )
            except Exception:
                pass

    results = search(username, progress_cb=progress)

    if not results:
        bot.edit_message_text(
            f"❌ <b>Ничего не найдено</b>\n\nНик <code>{username}</code> не обнаружен.",
            m.chat.id, status.message_id, reply_markup=results_menu(username),
        )
        return

    text = (
        f"🎯 <b>Результаты для</b> <code>{username}</code>\n"
        f"✅ Найдено аккаунтов: <b>{len(results)}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )
    for i, (name, url) in enumerate(results, 1):
        text += f'{i}. <a href="{url}">{name}</a>\n'

    chunks, current = [], text
    while len(current) > 4000:
        cut = current.rfind("\n", 0, 4000)
        chunks.append(current[:cut])
        current = current[cut:]
    chunks.append(current)

    bot.delete_message(m.chat.id, status.message_id)
    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            bot.send_message(m.chat.id, chunk, reply_markup=results_menu(username))
        else:
            bot.send_message(m.chat.id, chunk, disable_web_page_preview=True)


# ---------- Диалог: поиск по телефону ----------

def ask_phone(chat_id):
    msg = bot.send_message(
        chat_id,
        "📱 <b>Введи номер телефона</b>\n"
        "<i>В любом формате: +79123456789 или 89123456789</i>",
    )
    bot.register_next_step_handler(msg, do_phone_search)


def do_phone_search(m):
    raw = (m.text or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 7 or len(digits) > 15:
        bot.send_message(m.chat.id, "⚠️ Это не похоже на номер. Попробуй ещё раз: /phone")
        return

    status = bot.send_message(m.chat.id, "⏳ Анализирую номер...")
    report = phone_report(raw)

    if not report:
        bot.edit_message_text("❌ Некорректный или неизвестный номер.",
                              m.chat.id, status.message_id, reply_markup=phone_menu())
        return

    try:
        bot.edit_message_text(report, m.chat.id, status.message_id, reply_markup=phone_menu())
    except Exception:
        bot.delete_message(m.chat.id, status.message_id)
        bot.send_message(m.chat.id, report, reply_markup=phone_menu(),
                         disable_web_page_preview=True)


# ---------- Фолбэк на обычный текст ----------

@bot.message_handler(func=lambda m: True)
def fallback(m):
    text = (m.text or "").strip()
    if re.fullmatch(r"[+\d\s\-()]{7,20}", text):
        do_phone_search(m)
    else:
        bot.send_message(
            m.chat.id,
            "🤔 Не понял. Выбери действие в меню или отправь /help",
            reply_markup=main_menu(),
        )


# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    print("🤖 Бот запущен. phonenumbers:", "OK" if HAS_PN else "не установлен")
    bot.infinity_polling(skip_pending=True)
