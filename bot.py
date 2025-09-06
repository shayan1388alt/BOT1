import os
import random
import logging
import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler
)
import database

load_dotenv("config.env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
CURRENCY_NAME = os.getenv("CURRENCY_NAME", "SHI")
STARS_PER_SHI = int(database.get_setting("STARS_PER_SHI", os.getenv("STARS_PER_SHI","5")))
DAILY_SHI = float(database.get_setting("DAILY_SHI", os.getenv("DAILY_SHI","1")))
COINS_PER_SHI = int(os.getenv("COINS_PER_SHI","100"))

buying_shi_users = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SHI-BOT")

# ----------------- HELPERS -----------------
def admin_check(user_id:int):
    return user_id == OWNER_ID

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="start")]])

def admin_keyboard():
    kb = [
        [InlineKeyboardButton("آمار", callback_data="admin_stats"), InlineKeyboardButton("آیتم‌ها", callback_data="admin_items")],
        [InlineKeyboardButton("تراکنش‌ها", callback_data="admin_txs")],
        [InlineKeyboardButton("بازگشت", callback_data="start")]
    ]
    return InlineKeyboardMarkup(kb)

# ----------------- START -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.register_user(user.id, user.username)
    text = "به بازی خوش آمدی! منو رو باز کن."
    keyboard = [
        [InlineKeyboardButton("👤 پروفایل", callback_data="profile")],
        [InlineKeyboardButton("⚔️ مبارزه", callback_data="battle")],
        [InlineKeyboardButton("🛒 فروشگاه", callback_data="shop")],
        [InlineKeyboardButton(f"💫 خرید {CURRENCY_NAME} با Stars", callback_data="buy_shi")]
    ]
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ----------------- BUTTON HANDLER -----------------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u = database.get_user(user_id)
    if not u:
        database.register_user(user_id, query.from_user.username)
        u = database.get_user(user_id)
    data = query.data

    if data == "start":
        if update.callback_query:
            return await start(update, context)

    if data == "profile":
        await query.edit_message_text(
            f"پروفایل تو:\n💰 {CURRENCY_NAME}: {u['shi_balance']}\n🪙 سکه: {u['coins']}\n"
            f"⭐ استارز: {u['stars_balance']}\n🎚️ Level: {u['level']}  EXP: {u['exp']}",
            reply_markup=back_keyboard()
        ); return

    if data == "battle":
        base = int(u['level']) + random.randint(0,5)
        npc = random.randint(3, 18)
        win = base >= npc
        reward_coins = random.randint(10,50)
        database.add_coins(user_id, reward_coins)
        shi_from_coins = database.coins_to_shi_convert(user_id, coins_per_shi=COINS_PER_SHI, shi_per_chunk=0.01)
        database.record_battle(user_id, "NPC", win, shi_from_coins, reward_coins)
        if win:
            text = f"🎉 بردی! سکه گرفتیش: {reward_coins}\nتبدیل سکه -> SHI: {shi_from_coins:.2f}"
        else:
            text = f"باختی 😵 اما باز هم سکه گرفتی: {reward_coins}\nاگر سکه‌ها به حد رسید تبدیل میشه."
        await query.edit_message_text(text, reply_markup=back_keyboard()); return

    if data == "shop":
        items = database.get_items()
        lines = []
        kb = []
        for it in items:
            lines.append(f"• {it['name']} | power:{it['power']} | قیمت: {it['price_shi']} {CURRENCY_NAME}")
            kb.append([InlineKeyboardButton(f"خرید {it['name']}", callback_data=f"buyitem_{it['id']}")])
        kb.append([InlineKeyboardButton("↩️ بازگشت", callback_data="start")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb)); return

    if data.startswith("buyitem_"):
        item_id = int(data.split("_",1)[1])
        ok = database.buy_item(user_id, item_id)
        await query.edit_message_text("✅ خرید موفق!" if ok else "⛔ SHI کافی نیست!", reply_markup=back_keyboard()); return

    if data == "buy_shi":
        buying_shi_users[user_id] = True
        await query.edit_message_text(
            f"چند واحد {CURRENCY_NAME} می‌خوای بخری؟ (یک عدد بفرست)\nنرخ فعلی: هر {CURRENCY_NAME} = {database.get_setting('STARS_PER_SHI',str(STARS_PER_SHI))} ⭐",
            reply_markup=back_keyboard()
        ); return

# ----------------- HIDDEN ADMIN -----------------
async def hidden_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not admin_check(user_id):
        return
    await update.message.reply_text("🔒 پنل ادمین باز شد", reply_markup=admin_keyboard())

# ----------------- HANDLE TEXT -----------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    txt = (update.message.text or "").strip()

    if txt.startswith("/shayan7"):
        await hidden_admin_cmd(update, context)
        return

    if buying_shi_users.get(user_id):
        if not txt.isdigit():
            await update.message.reply_text("لطفاً فقط عدد بفرست.")
            buying_shi_users[user_id] = False
            return
        amount_shi = int(txt)
        stars_per_shi = int(database.get_setting("STARS_PER_SHI", str(STARS_PER_SHI)))
        stars_needed = amount_shi * stars_per_shi
        invoice = LabeledPrice(label=f"{amount_shi} {CURRENCY_NAME}", amount=stars_needed)
        try:
            await context.bot.send_invoice(
                chat_id=user_id,
                title=f"خرید {amount_shi} {CURRENCY_NAME}",
                description=f"پرداخت با Telegram Stars",
                payload=f"buy_{amount_shi}_{user_id}",
                provider_token="",
                currency="XTR",
                prices=[invoice],
                start_parameter="buy-shi"
            )
        except Exception as e:
            logger.exception("send_invoice failed")
            await update.message.reply_text("مشکل در ارسال فاکتور. بعداً تلاش کن.")
        buying_shi_users[user_id] = False
        return

    await update.message.reply_text("از منو استفاده کنید یا /start رو بزنین.", reply_markup=back_keyboard())

# ----------------- DAILY -----------------
async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    database.register_user(user_id, update.effective_user.username)
    u = database.get_user(user_id)
    last = int(u.get("last_daily", 0))
    now = int(datetime.datetime.utcnow().timestamp())
    if now - last < 24*3600:
        await update.message.reply_text("پاداش روزانه قبلاً گرفته شده. فردا بیا.", reply_markup=back_keyboard())
        return
    daily_shi = float(database.get_setting("DAILY_SHI", str(DAILY_SHI)))
    minc = int(database.get_setting("DAILY_COINS_MIN","10"))
    maxc = int(database.get_setting("DAILY_COINS_MAX","30"))
    coins = random.randint(minc, maxc)
    database.update_shi(user_id, daily_shi)
    database.add_coins(user_id, coins)
    database.set_setting(f"user_{user_id}_last_daily", str(now))
    await update.message.reply_text(f"🎁 پاداش روزانه: {daily_shi} {CURRENCY_NAME} و {coins} سکه دریافت شد!", reply_markup=back_keyboard())

# ----------------- LEADERBOARD -----------------
async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = database.get_leaderboard()
    lines = [f"{i+1}. {u['username']} - {u['shi_balance']} {CURRENCY_NAME}" for i,u in enumerate(top_users)]
    await update.message.reply_text("🏆 لیدربورد:\n" + "\n".join(lines), reply_markup=back_keyboard())

# ----------------- PRECHECKOUT & PAYMENT -----------------
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if not (query.invoice_payload or "").startswith("buy_"):
        await query.answer(ok=False, error_message="payload نامعتبر")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sp = update.message.successful_payment
    user_id = update.effective_user.id
    payload = sp.invoice_payload or ""
    try:
        parts = payload.split("_")
        if parts[0] == "buy":
            amount_shi = int(parts[1])
        else:
            amount_shi = max(1, int(int(sp.total_amount) // STARS_PER_SHI))
    except:
        amount_shi = max(1, int(int(sp.total_amount) // STARS_PER_SHI))
    database.update_shi(user_id, amount_shi)
    database.set_setting("last_payment_ts", str(int(datetime.datetime.now().timestamp())))
    await update.message.reply_text(f"✅ پرداخت موفق! {amount_shi} {CURRENCY_NAME} به حساب شما اضافه شد.", reply_markup=back_keyboard())

# ----------------- ERROR HANDLER -----------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("یه خطای داخلی رخ داد. دوباره تلاش کن 🙏")
    except:
        pass

# ----------------- MAIN -----------------
def main():
    if not BOT_TOKEN:
        print("لطفا BOT_TOKEN رو در config.env بذار.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CommandHandler("shayan7", hidden_admin_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_error_handler(error_handler)

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
