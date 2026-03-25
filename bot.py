from __future__ import annotations

import asyncio
import html
import logging
import os
from typing import Any

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

import database
import wikipedia_api

load_dotenv()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi. .env faylini tekshiring.")

PREFERRED_LANGUAGE_KEY = "preferred_language"
NAVIGATION_STACK_KEY = "navigation_stack"
WIKIPEDIA_OPERATION_TIMEOUT_SECONDS = 40
HISTORY_LIMIT = 10

VIEW_LANGUAGE_GATE = "language_gate"
VIEW_MAIN_MENU = "main_menu"
VIEW_SEARCH = "search"
VIEW_HISTORY = "history"
VIEW_STATS = "stats"
VIEW_HELP = "help"
VIEW_PROFILE = "profile"
VIEW_RESULTS = "results"

LANGUAGE_CHOICES = {"uz": "O'zbek", "ru": "Русский", "en": "English"}

TEXTS = {
    "uz": {
        "search": "Qidirish", "history": "Saqlanganlar", "stats": "Statistika", "help": "Yordam", "profile": "Profil", "back": "Orqaga",
        "searching": "Qidirilmoqda",
        "tri": "Assalomu alaykum! Wikipedia botga xush kelibsiz.\nЗдравствуйте! Добро пожаловать в Wikipedia бот.\nHello! Welcome to the Wikipedia bot.",
        "pick_lang": "Tilni tanlang:",
        "welcome": "Assalomu alaykum, <b>{name}</b>!\n\nMen sizga Wikipedia maqolalarini tanlagan tilingizda topib beraman, qidiruvlaringizni saqlab boraman va bo'limlar orqali qulay ishlashga yordam beraman.",
        "menu": "Bo'limlardan birini tanlang.",
        "menu_opened": "Bo'limlar ochildi. Endi kerakli bo'limni tanlang.",
        "search_prompt": "Mavzu nomini yozing. Men uni tanlangan tilingizdagi Wikipedia'dan qidiraman.",
        "help_text": "<b>Yordam</b>\n\nQidirish bo'limida mavzu yozing va bot tanlangan tildagi maqolalarni havolalari bilan chiqaradi.\n\nOrqaga tugmasi bir qadam oldingi oynaga qaytaradi.",
        "stats_title": "<b>Sizning statistikangiz</b>",
        "total": "Jami qidiruvlar",
        "profile_title": "<b>Profil ma'lumotlari</b>",
        "fname": "Ism", "lname": "Familiya", "uname": "Username", "tgid": "Telegram ID", "main_lang": "Asosiy til",
        "history_title": "<b>Saqlangan qidiruvlar</b>", "history_empty": "Hali saqlangan qidiruvlar yo'q.",
        "query": "Qidiruv", "date": "Sana", "language": "Til", "topic": "Mavzu", "found": "Topilgan maqolalar",
        "search_again": "Yangi mavzu yozsangiz, shu yerning o'zida yana qidiramiz.",
        "choose_lang_first": "Avval tilni tanlang:",
        "enter_topic": "Iltimos, mavzu nomini yuboring.",
        "timeout": "Uzr, qidiruv kutilganidan sekinroq ishladi. Iltimos, birozdan keyin qayta urinib ko'ring.",
        "not_found": "Uzr, ushbu mavzu bo'yicha maqola topa olmadim.\nIltimos, mavzuni boshqacharoq yozib yoki qisqartirib qayta urinib ko'ring.",
        "network": "Uzr, hozir Wikipedia bilan ulanishda muammo bo'ldi. Keyinroq urinib ko'ring.",
        "unknown": "Kutilmagan xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
        "processing": "Uzr, xabarni qayta ishlashda muammo bo'ldi.",
        "callback": "Uzr, tanlovni qayta ishlashda muammo bo'ldi.",
        "lang_saved": "Til saqlandi.", "bad_lang": "Noto'g'ri til.", "first_screen": "Siz boshlang'ich oynadasiz.",
    },
    "ru": {
        "search": "Поиск", "history": "Сохранённые", "stats": "Статистика", "help": "Помощь", "profile": "Профиль", "back": "Назад",
        "searching": "Идёт поиск",
        "tri": "Assalomu alaykum! Wikipedia botga xush kelibsiz.\nЗдравствуйте! Добро пожаловать в Wikipedia бот.\nHello! Welcome to the Wikipedia bot.",
        "pick_lang": "Выберите язык:",
        "welcome": "Здравствуйте, <b>{name}</b>!\n\nЯ помогу найти статьи Wikipedia на выбранном вами языке, сохранить ваши запросы и удобно работать через разделы ниже.",
        "menu": "Выберите один из разделов.",
        "menu_opened": "Разделы открыты. Теперь выберите нужный пункт.",
        "search_prompt": "Напишите тему. Я найду её в Wikipedia на выбранном вами языке.",
        "help_text": "<b>Помощь</b>\n\nВ разделе поиска напишите тему, и бот покажет статьи Wikipedia со ссылками на выбранном языке.\n\nКнопка Назад возвращает на один шаг назад.",
        "stats_title": "<b>Ваша статистика</b>",
        "total": "Всего запросов",
        "profile_title": "<b>Информация профиля</b>",
        "fname": "Имя", "lname": "Фамилия", "uname": "Username", "tgid": "Telegram ID", "main_lang": "Основной язык",
        "history_title": "<b>Сохранённые запросы</b>", "history_empty": "Сохранённых запросов пока нет.",
        "query": "Запрос", "date": "Дата", "language": "Язык", "topic": "Тема", "found": "Найденные статьи",
        "search_again": "Отправьте новую тему, и я выполню новый поиск.",
        "choose_lang_first": "Сначала выберите язык:",
        "enter_topic": "Пожалуйста, отправьте тему.",
        "timeout": "Извините, поиск занял слишком много времени. Попробуйте позже.",
        "not_found": "Извините, я не смог найти статью по этой теме.\nПопробуйте написать тему по-другому или короче.",
        "network": "Извините, сейчас возникла проблема с подключением к Wikipedia. Попробуйте позже.",
        "unknown": "Произошла непредвиденная ошибка. Пожалуйста, попробуйте снова.",
        "processing": "Извините, произошла ошибка при обработке сообщения.",
        "callback": "Извините, произошла ошибка при обработке выбора.",
        "lang_saved": "Язык сохранён.", "bad_lang": "Неверный язык.", "first_screen": "Вы уже на начальном экране.",
    },
    "en": {
        "search": "Search", "history": "Saved", "stats": "Statistics", "help": "Help", "profile": "Profile", "back": "Back",
        "searching": "Searching",
        "tri": "Assalomu alaykum! Wikipedia botga xush kelibsiz.\nЗдравствуйте! Добро пожаловать в Wikipedia бот.\nHello! Welcome to the Wikipedia bot.",
        "pick_lang": "Choose a language:",
        "welcome": "Hello, <b>{name}</b>!\n\nI can find Wikipedia articles in your chosen language, save your searches, and help you use everything through the sections below.",
        "menu": "Choose one of the sections.",
        "menu_opened": "Sections are now open. Choose the one you need.",
        "search_prompt": "Send a topic. I will search Wikipedia in your selected language.",
        "help_text": "<b>Help</b>\n\nOpen Search, send a topic, and the bot will show Wikipedia articles with links in your selected language.\n\nThe Back button takes you one step back.",
        "stats_title": "<b>Your statistics</b>",
        "total": "Total searches",
        "profile_title": "<b>Profile information</b>",
        "fname": "First name", "lname": "Last name", "uname": "Username", "tgid": "Telegram ID", "main_lang": "Main language",
        "history_title": "<b>Saved searches</b>", "history_empty": "No saved searches yet.",
        "query": "Query", "date": "Date", "language": "Language", "topic": "Topic", "found": "Found articles",
        "search_again": "Send a new topic any time and I will search again.",
        "choose_lang_first": "Please choose a language first:",
        "enter_topic": "Please send a topic.",
        "timeout": "Sorry, the search took too long. Please try again later.",
        "not_found": "Sorry, I could not find an article for this topic.\nPlease try rewriting the topic or making it shorter.",
        "network": "Sorry, there is a connection problem with Wikipedia right now. Please try again later.",
        "unknown": "An unexpected error occurred. Please try again.",
        "processing": "Sorry, there was a problem while processing your message.",
        "callback": "Sorry, there was a problem while processing your selection.",
        "lang_saved": "Language saved.", "bad_lang": "Invalid language.", "first_screen": "You are already on the first screen.",
    },
}


def t(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["uz"])[key]


def esc(value: Any) -> str:
    return html.escape(str(value), quote=False)


def esc_attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


def buttons(lang: str) -> dict[str, str]:
    return {k: t(lang, k) for k in ("search", "history", "stats", "help", "profile", "back")}


def main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    b = buttons(lang)
    return ReplyKeyboardMarkup([[b["search"], b["history"]], [b["stats"], b["help"]], [b["profile"]]], resize_keyboard=True)


def back_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[buttons(lang)["back"]]], resize_keyboard=True)


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=f"lang_set:{code}")] for code, label in LANGUAGE_CHOICES.items()])


def nav_stack(context: ContextTypes.DEFAULT_TYPE) -> list[dict[str, Any]]:
    return context.user_data.setdefault(NAVIGATION_STACK_KEY, [{"view": VIEW_LANGUAGE_GATE}])


def set_root(context: ContextTypes.DEFAULT_TYPE, view: str, **payload: Any) -> None:
    context.user_data[NAVIGATION_STACK_KEY] = [{"view": view, **payload}]


def push_view(context: ContextTypes.DEFAULT_TYPE, view: str, **payload: Any) -> None:
    stack = nav_stack(context)
    new_view = {"view": view, **payload}
    if stack[-1] != new_view:
        stack.append(new_view)


def pop_view(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    stack = nav_stack(context)
    if len(stack) > 1:
        stack.pop()
    return stack[-1]


async def safe_answer(query, text: str | None = None, show_alert: bool = False) -> None:
    try:
        await query.answer(text, show_alert=show_alert)
    except Exception as exc:
        logger.warning("Callback javobi yuborilmadi: %s", exc)


async def safe_edit_or_reply(query, text: str, **kwargs: Any) -> None:
    try:
        await query.edit_message_text(text, **kwargs)
    except Exception as exc:
        logger.warning("Xabarni tahrirlab bo'lmadi, yangi xabar yuboriladi: %s", exc)
        if query.message:
            await query.message.reply_text(text, **kwargs)


async def safe_edit_message(message, text: str, **kwargs: Any) -> None:
    try:
        await message.edit_text(text, **kwargs)
    except Exception as exc:
        logger.warning("Xabarni yangilab bo'lmadi, yangi xabar yuboriladi: %s", exc)
        if hasattr(message, "reply_text"):
            await message.reply_text(text, **kwargs)


async def save_user(user, language: str | None = None) -> None:
    await asyncio.to_thread(database.save_user, user, language)


async def update_user_language(user_id: int, language: str) -> None:
    await asyncio.to_thread(database.update_user_language, user_id, language)


async def get_user_language(user_id: int) -> str | None:
    return await asyncio.to_thread(database.get_user_language, user_id)


async def get_user_stats(user_id: int) -> int:
    return await asyncio.to_thread(database.get_user_stats, user_id)


async def get_user_history(user_id: int) -> list[dict[str, Any]]:
    return await asyncio.to_thread(database.get_user_history, user_id, HISTORY_LIMIT)


async def save_search(user_id: int, query: str, title: str, url: str, language: str) -> None:
    await asyncio.to_thread(database.save_search, user_id, query, title, url, "", language)


async def current_language(context: ContextTypes.DEFAULT_TYPE, user_id: int | None = None) -> str:
    language = context.user_data.get(PREFERRED_LANGUAGE_KEY)
    if language:
        return language
    if user_id is not None:
        language = await get_user_language(user_id)
        if language:
            context.user_data[PREFERRED_LANGUAGE_KEY] = language
            return language
    return wikipedia_api.DEFAULT_LANGUAGE


def results_text(query: str, lang: str, options: list[dict[str, Any]]) -> str:
    lines = [
        f"<b>{t(lang, 'topic')}:</b> {esc(query)}",
        f"<b>{t(lang, 'language')}:</b> {esc(LANGUAGE_CHOICES.get(lang, lang))}",
        "",
        f"<b>{t(lang, 'found')}:</b>",
        "",
    ]
    for i, option in enumerate(options, start=1):
        lines.append(f"{i}. <a href=\"{esc_attr(option['url'])}\">{esc(option['title'])}</a>")
        if option.get("snippet"):
            lines.append(esc(option["snippet"]))
        lines.append("")
    lines.append(t(lang, "search_again"))
    return "\n".join(lines)


def history_text(items: list[dict[str, Any]], lang: str) -> str:
    if not items:
        return f"{t(lang, 'history_title')}\n\n{t(lang, 'history_empty')}"
    lines = [t(lang, "history_title"), ""]
    for i, item in enumerate(items, start=1):
        item_lang = item.get("language") or lang
        lines.append(f"{i}. <a href=\"{esc_attr(item['url'])}\">{esc(item['title'])}</a>")
        lines.append(f"{t(lang, 'query')}: {esc(item['query'])}")
        lines.append(f"{t(lang, 'language')}: {esc(LANGUAGE_CHOICES.get(item_lang, item_lang))}")
        if item.get("search_date"):
            dt = str(item["search_date"])[:16].replace("T", " ")
            lines.append(f"{t(lang, 'date')}: {esc(dt)}")
        lines.append("")
    return "\n".join(lines)


async def render_main_menu(message, lang: str, note: str | None = None) -> None:
    await message.reply_text(note or t(lang, "menu"), reply_markup=main_keyboard(lang))


async def render_search_prompt(message, lang: str) -> None:
    await message.reply_text(t(lang, "search_prompt"), reply_markup=back_keyboard(lang))


async def render_help(message, lang: str) -> None:
    await message.reply_text(t(lang, "help_text"), parse_mode=ParseMode.HTML, reply_markup=back_keyboard(lang))


async def render_stats(message, user_id: int, lang: str) -> None:
    try:
        count = await get_user_stats(user_id)
    except Exception as exc:
        logger.error("Statistika olishda xatolik: %s", exc)
        count = 0
    await message.reply_text(f"{t(lang, 'stats_title')}\n\n{t(lang, 'total')}: {esc(count)}", parse_mode=ParseMode.HTML, reply_markup=back_keyboard(lang))


async def render_profile(message, user, lang: str) -> None:
    try:
        count = await get_user_stats(user.id)
    except Exception as exc:
        logger.error("Profil statistikasi olinmadi: %s", exc)
        count = 0
    username = f"@{user.username}" if user.username else "Yo'q"
    text = (
        f"{t(lang, 'profile_title')}\n\n"
        f"{t(lang, 'fname')}: {esc(user.first_name or 'Belgilanmagan')}\n"
        f"{t(lang, 'lname')}: {esc(user.last_name or 'Belgilanmagan')}\n"
        f"{t(lang, 'uname')}: {esc(username)}\n"
        f"{t(lang, 'tgid')}: <code>{user.id}</code>\n"
        f"{t(lang, 'main_lang')}: {esc(LANGUAGE_CHOICES.get(lang, lang))}\n"
        f"{t(lang, 'total')}: {esc(count)}"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard(lang))


async def render_history(message, user_id: int, lang: str) -> None:
    try:
        items = await get_user_history(user_id)
    except Exception as exc:
        logger.error("Tarixni olishda xatolik: %s", exc)
        items = []
    await message.reply_text(history_text(items, lang), parse_mode=ParseMode.HTML, reply_markup=back_keyboard(lang), disable_web_page_preview=True)


async def render_view(message, context: ContextTypes.DEFAULT_TYPE, user, view: dict[str, Any]) -> None:
    lang = await current_language(context, user.id if user else None)
    name = view["view"]
    if name == VIEW_MAIN_MENU:
        await render_main_menu(message, lang, view.get("note"))
    elif name == VIEW_SEARCH:
        await render_search_prompt(message, lang)
    elif name == VIEW_HISTORY:
        await render_history(message, user.id, lang)
    elif name == VIEW_STATS:
        await render_stats(message, user.id, lang)
    elif name == VIEW_HELP:
        await render_help(message, lang)
    elif name == VIEW_PROFILE:
        await render_profile(message, user, lang)
    else:
        await message.reply_text(t("uz", "tri"), reply_markup=ReplyKeyboardRemove())
        await message.reply_text(t("uz", "pick_lang"), reply_markup=language_keyboard())


async def go_back(message, context: ContextTypes.DEFAULT_TYPE, user) -> None:
    current = nav_stack(context)[-1]
    lang = await current_language(context, user.id if user else None)
    if current["view"] == VIEW_LANGUAGE_GATE:
        await message.reply_text(t(lang, "first_screen"))
        return
    await render_view(message, context, user, pop_view(context))


async def run_search(message, context: ContextTypes.DEFAULT_TYPE, user, query: str) -> None:
    lang = await current_language(context, user.id)
    loading = await message.reply_text(
        f"{t(lang, 'searching')}: <b>{esc(query)}</b>\n{t(lang, 'language')}: <b>{esc(LANGUAGE_CHOICES.get(lang, lang))}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard(lang),
    )
    try:
        result = await asyncio.wait_for(asyncio.to_thread(wikipedia_api.search_wikipedia, query, lang), timeout=WIKIPEDIA_OPERATION_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await safe_edit_message(loading, t(lang, "timeout"))
        return
    except Exception as exc:
        logger.exception("Qidiruvda kutilmagan xatolik")
        await safe_edit_message(loading, f"{t(lang, 'processing')}\n{esc(str(exc)[:120])}", parse_mode=ParseMode.HTML)
        return

    if not result or result.get("error"):
        err = result.get("error") if result else "unknown"
        msg = {"empty_query": t(lang, "enter_topic"), "not_found": t(lang, "not_found"), "network_error": t(lang, "network")}.get(err, t(lang, "unknown"))
        await safe_edit_message(loading, msg)
        return

    options = (result.get("options") or [])[: wikipedia_api.MAX_SEARCH_RESULTS]
    if not options:
        await safe_edit_message(loading, t(lang, "not_found"))
        return

    try:
        await save_search(user.id, query, options[0]["title"], options[0]["url"], lang)
    except Exception as exc:
        logger.error("Qidiruvni saqlashda xatolik: %s", exc)

    push_view(context, VIEW_RESULTS, query=query, language=lang)
    await safe_edit_message(loading, results_text(query, lang, options), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message
    try:
        await save_user(user)
    except Exception as exc:
        logger.error("Foydalanuvchini saqlashda xatolik: %s", exc)
    context.user_data[PREFERRED_LANGUAGE_KEY] = None
    set_root(context, VIEW_LANGUAGE_GATE)
    await message.reply_text(t("uz", "tri"), reply_markup=ReplyKeyboardRemove())
    await message.reply_text(t("uz", "pick_lang"), reply_markup=language_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    push_view(context, VIEW_HELP)
    await render_help(update.effective_message, await current_language(context, update.effective_user.id))


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    push_view(context, VIEW_PROFILE)
    await render_profile(update.effective_message, update.effective_user, await current_language(context, update.effective_user.id))


async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    push_view(context, VIEW_STATS)
    await render_stats(update.effective_message, update.effective_user.id, await current_language(context, update.effective_user.id))


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    push_view(context, VIEW_HISTORY)
    await render_history(update.effective_message, update.effective_user.id, await current_language(context, update.effective_user.id))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message
    try:
        lang = await current_language(context, user.id)
        b = buttons(lang)
        text = (message.text or "").strip()
        try:
            await save_user(user, context.user_data.get(PREFERRED_LANGUAGE_KEY))
        except Exception as exc:
            logger.error("Foydalanuvchini saqlashda xatolik: %s", exc)

        if text == b["back"]:
            await go_back(message, context, user)
            return

        if not context.user_data.get(PREFERRED_LANGUAGE_KEY):
            await message.reply_text(t("uz", "pick_lang"), reply_markup=language_keyboard())
            return

        if text == b["search"]:
            push_view(context, VIEW_SEARCH)
            await render_search_prompt(message, lang)
            return
        if text == b["history"]:
            await history(update, context)
            return
        if text == b["stats"]:
            await statistics(update, context)
            return
        if text == b["help"]:
            await help_command(update, context)
            return
        if text == b["profile"]:
            await profile(update, context)
            return
        if not text:
            await message.reply_text(t(lang, "enter_topic"), reply_markup=back_keyboard(lang))
            return

        if nav_stack(context)[-1]["view"] != VIEW_SEARCH:
            push_view(context, VIEW_SEARCH)
        await run_search(message, context, user, text)
    except Exception as exc:
        logger.exception("handle_message ichida kutilmagan xatolik")
        lang = await current_language(context, user.id)
        await message.reply_text(f"{t(lang, 'processing')}\n{esc(str(exc)[:120])}", parse_mode=ParseMode.HTML, reply_markup=back_keyboard(lang))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    try:
        data = query.data or ""
        if data.startswith("lang_set:"):
            lang = data.split(":", maxsplit=1)[1]
            if lang not in LANGUAGE_CHOICES:
                await safe_answer(query, t("uz", "bad_lang"), show_alert=True)
                return
            context.user_data[PREFERRED_LANGUAGE_KEY] = lang
            set_root(context, VIEW_MAIN_MENU)
            try:
                await update_user_language(update.effective_user.id, lang)
            except Exception as exc:
                logger.error("Tilni bazaga saqlashda xatolik: %s", exc)
            await safe_answer(query, t(lang, "lang_saved"))
            await safe_edit_or_reply(
                query,
                f"{t(lang, 'welcome').format(name=esc(update.effective_user.first_name or 'User'))}\n\n{t(lang, 'menu_opened')}",
                parse_mode=ParseMode.HTML,
            )
            await render_main_menu(query.message, lang, t(lang, "menu_opened"))
            return
        await safe_answer(query)
    except Exception as exc:
        logger.exception("handle_callback ichida kutilmagan xatolik")
        lang = await current_language(context, update.effective_user.id)
        await safe_answer(query, t(lang, "unknown"), show_alert=True)
        if query.message:
            await query.message.reply_text(f"{t(lang, 'callback')}\n{esc(str(exc)[:120])}", parse_mode=ParseMode.HTML, reply_markup=back_keyboard(lang))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Kutilmagan xatolik: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        user_id = update.effective_user.id if update.effective_user else None
        lang = await current_language(context, user_id)
        try:
            await update.effective_message.reply_text(t(lang, "unknown"), reply_markup=back_keyboard(lang))
        except Exception:
            logger.debug("Xatolik xabarini yuborib bo'lmadi.")


def main() -> None:
    logger.info("Bot ishga tushmoqda...")
    try:
        database.init_db()
    except Exception as exc:
        logger.error("Bazani yaratishda xatolik: %s", exc)
        return
    try:
        app = (
            ApplicationBuilder()
            .token(BOT_TOKEN)
            .connect_timeout(30.0)
            .read_timeout(30.0)
            .write_timeout(30.0)
            .pool_timeout(30.0)
            .build()
        )
    except Exception as exc:
        logger.error("Application yaratishda xatolik: %s", exc)
        return
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^lang_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    logger.info("Bot tayyor. Telegram ulanishi kutilmoqda...")
    try:
        app.run_polling()
    except Exception as exc:
        logger.error("Bot ishlashda xatolik: %s", exc)
        logger.error("Internet ulanishini tekshiring va qayta urinib ko'ring.")


if __name__ == "__main__":
    main()
