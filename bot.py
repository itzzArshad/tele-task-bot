import logging
import asyncio
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import nest_asyncio
from aiohttp import web
import threading
import random

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)

# ===== Globals =====
user_selection = {}
user_tasks = {"arshad": [], "rahmu": []}
user_states = {}
temp_task = {}

motivation_lines = [
    "🌸 You're doing amazing, keep going!",
    "💖 Small steps make big changes!",
    "🌞 You got this, one task at a time.",
    "💫 Let's make today beautiful and productive.",
    "🌼 A little progress each day adds up to big results!"
]

# ===== UI Helpers =====
def get_user_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💙 Arshad", callback_data="user_arshad")],
        [InlineKeyboardButton("💗 Rahmu", callback_data="user_rahmu")]
    ])

def get_main_menu_markup(user):
    line = random.choice(motivation_lines)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Task", callback_data="add_task")],
        [InlineKeyboardButton("📋 View Tasks", callback_data="view_tasks")],
        [InlineKeyboardButton("🗑️ Clear Tasks", callback_data="clear_tasks")]
    ]), line

def get_back_and_view_tasks_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 View Tasks", callback_data="view_tasks")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
    ])

def task_action_buttons(idx):
    return InlineKeyboardMarkup([[ 
        InlineKeyboardButton("✅ Done", callback_data=f"done_{idx}"),
        InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{idx}"),
        InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{idx}")
    ]])

def get_deadline_date_markup():
    today = datetime.now()
    buttons = []
    for i in range(8):  # today + 7 days
        d = today + timedelta(days=i)
        label = d.strftime("%A, %d %B")
        buttons.append([InlineKeyboardButton(label, callback_data=f"date_{d.strftime('%Y_%m_%d')}")])
    return InlineKeyboardMarkup(buttons)

def get_time_markup():
    kb = []
    for h in range(24):
        t = f"{h:02d}:00"
        kb.append([InlineKeyboardButton(t, callback_data=f"time_{h}_0")])
    return InlineKeyboardMarkup(kb)

# ===== Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey love, who’s using the bot today? 💕", reply_markup=get_user_markup())

async def user_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.data.split("_")[1]  # "arshad" or "rahmu"
    user_selection[q.from_user.id] = user
    markup, quote = get_main_menu_markup(user)
    await q.edit_message_text(
        f"Welcome back, {user.capitalize()} ❤️\n\n{quote}\n\nChoose what you want to do:",
        reply_markup=markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    user = user_selection.get(user_id)
    data = q.data

    if data == "add_task":
        user_states[user_id] = "awaiting_name"
        await q.edit_message_text("✨ Tell me the *task name* you'd like to add:", parse_mode="Markdown")
        return

    if data == "view_tasks":
        tasks = user_tasks.get(user, [])
        if not tasks:
            await q.edit_message_text(
                "No tasks yet, love! Let’s add one 🌷",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Task", callback_data="add_task")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
                ])
            )
            return

        await q.edit_message_text("Here are your lovely tasks:")
        for idx, t in enumerate(tasks):
            status = "✅" if t["done"] else "❌"
            text = f"{idx+1}. {status} *{t['name']}*\n🕒 {t['deadline'].strftime('%d %b %Y %H:%M')}"
            await q.message.chat.send_message(
                text, parse_mode="Markdown",
                reply_markup=task_action_buttons(idx)
            )
        await q.message.chat.send_message(
            "What next, sweetheart?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add More", callback_data="add_task")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
            ])
        )
        return

    if data == "clear_tasks":
        user_tasks[user] = []
        await q.edit_message_text("🧹 All tasks cleared, fresh start love!", reply_markup=get_back_and_view_tasks_markup())
        return

    if data.startswith(("done_", "delete_", "edit_")):
        cmd, idx_str = data.split("_")
        idx = int(idx_str)
        tasks = user_tasks[user]
        if cmd == "done" and 0 <= idx < len(tasks):
            tasks[idx]["done"] = True
            await q.edit_message_text("✅ Task marked done!", reply_markup=get_back_and_view_tasks_markup())
        elif cmd == "delete" and 0 <= idx < len(tasks):
            tasks.pop(idx)
            await q.edit_message_text("🗑️ Task deleted!", reply_markup=get_back_and_view_tasks_markup())
        elif cmd == "edit" and 0 <= idx < len(tasks):
            temp_task[user_id] = {"edit_index": idx}
            user_states[user_id] = "editing_name"
            await q.edit_message_text("✍️ What should be the new *task name*?", parse_mode="Markdown")
        return

    if data == "back_to_menu":
        markup, quote = get_main_menu_markup(user)
        await q.edit_message_text(
            f"Alrighty! What now, {user.capitalize()}? 💌\n\n{quote}",
            reply_markup=markup
        )
        return

    if data.startswith("date_"):
        _, y, m, d = data.split("_")
        dt = datetime(int(y), int(m), int(d))
        temp_task[user_id]["date"] = dt
        await q.edit_message_text("Now pick the time 🕒:", reply_markup=get_time_markup())
        return

    if data.startswith("time_"):
        _, hour_str, minute_str = data.split("_")
        h, mi = int(hour_str), int(minute_str)
        task_data = temp_task.pop(user_id, {})
        dt = task_data["date"].replace(hour=h, minute=mi)
        if "edit_index" in task_data:
            idx = task_data["edit_index"]
            user_tasks[user][idx].update({
                "name": task_data["name"],
                "deadline": dt
            })
            await q.edit_message_text("📝 Task updated, love!", reply_markup=get_back_and_view_tasks_markup())
        else:
            user_tasks[user].append({
                "name": task_data["name"],
                "deadline": dt,
                "done": False
            })
            await q.edit_message_text("🎉 Task added successfully!", reply_markup=get_back_and_view_tasks_markup())
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id)
    user = user_selection.get(user_id)

    if state in ("awaiting_name", "editing_name"):
        temp_task[user_id] = temp_task.get(user_id, {})
        temp_task[user_id]["name"] = update.message.text
        user_states[user_id] = None
        await update.message.reply_text("🗓️ Now choose a deadline date:", reply_markup=get_deadline_date_markup())
    else:
        await update.message.reply_text("Hi love, please type /start to begin 💬")

# ===== Daily Reminder Task =====
async def send_daily_reminders(app):
    while True:
        now = datetime.now()
        target_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)
        wait_time = (target_time - now).total_seconds()
        await asyncio.sleep(wait_time)

        for user_id, user in user_selection.items():
            tasks = user_tasks.get(user, [])
            if tasks:
                lines = [f"{idx+1}. {t['name']} – {'✅' if t['done'] else '❌'}" for idx, t in enumerate(tasks)]
                message = f"🌞 Good morning, {user.capitalize()}!\n\nHere's your task list:\n" + "\n".join(lines)
            else:
                message = f"🌅 Morning, {user.capitalize()}! You’ve got no tasks yet. Let’s add one today 💕"
            try:
                await app.bot.send_message(chat_id=user_id, text=message)
            except:
                continue

# ===== Health check endpoint =====
async def handle_ping(request):
    return web.Response(text="OK")

def start_health_server():
    import os
    app = web.Application()
    app.router.add_get("/health", handle_ping)
    port = int(os.environ.get("PORT", 8000))
    web.run_app(app, port=port)


# ===== Run Bot =====
async def main():
    app = ApplicationBuilder().token("7877522996:AAFljhNT3EEguS9kZECBTGRW5M5gcvivbUU").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(user_selector, pattern="^user_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Background threads
    threading.Thread(target=start_health_server, daemon=True).start()
    asyncio.create_task(send_daily_reminders(app))

    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
