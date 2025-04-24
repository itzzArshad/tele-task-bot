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

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)

# ===== Globals =====
user_selection = {}
user_tasks = {"arshad": [], "rahmu": []}
user_states = {}
temp_task = {}

# ===== UI Helpers =====
def get_user_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Arshad", callback_data="user_arshad")],
        [InlineKeyboardButton("Rahmu", callback_data="user_rahmu")]
    ])

def get_main_menu_markup(user):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Task", callback_data="add_task")],
        [InlineKeyboardButton("📋 View Tasks", callback_data="view_tasks")],
        [InlineKeyboardButton("🗑️ Clear Tasks", callback_data="clear_tasks")]
    ])

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
    await update.message.reply_text("Who is using the bot?", reply_markup=get_user_markup())

async def user_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.data.split("_")[1]  # "arshad" or "rahmu"
    user_selection[q.from_user.id] = user
    await q.edit_message_text(
        f"Welcome {user.capitalize()}! Choose an action:",
        reply_markup=get_main_menu_markup(user)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    user = user_selection.get(user_id)
    data = q.data

    # ➕ Add Task
    if data == "add_task":
        user_states[user_id] = "awaiting_name"
        await q.edit_message_text("Enter the *task name*:", parse_mode="Markdown")
        return

    # 📋 View Tasks
    if data == "view_tasks":
        tasks = user_tasks.get(user, [])
        # If no tasks, show buttons
        if not tasks:
            await q.edit_message_text(
                "No tasks found.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add More Tasks", callback_data="add_task")],
                    [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
                ])
            )
            return

        # Otherwise list tasks
        await q.edit_message_text("Here are your tasks:")
        for idx, t in enumerate(tasks):
            status = "✅" if t["done"] else "❌"
            text = f"{idx+1}. {status} *{t['name']}*\n⏰ {t['deadline'].strftime('%d %b %Y %H:%M')}"
            await q.message.chat.send_message(
                text, parse_mode="Markdown",
                reply_markup=task_action_buttons(idx)
            )
        # After listing, show navigation buttons
        await q.message.chat.send_message(
            "What next?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add More Tasks", callback_data="add_task")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ])
        )
        return

    # 🗑️ Clear Tasks
    if data == "clear_tasks":
        user_tasks[user] = []
        await q.edit_message_text(
            "All tasks cleared.",
            reply_markup=get_back_and_view_tasks_markup()
        )
        return

    # ✅ Done, 🗑️ Delete, ✏️ Edit
    if data.startswith(("done_", "delete_", "edit_")):
        cmd, idx_str = data.split("_")
        idx = int(idx_str)
        tasks = user_tasks[user]
        if cmd == "done" and 0 <= idx < len(tasks):
            tasks[idx]["done"] = True
            await q.edit_message_text("Task marked done.", reply_markup=get_back_and_view_tasks_markup())
            return
        if cmd == "delete" and 0 <= idx < len(tasks):
            tasks.pop(idx)
            await q.edit_message_text("Task deleted.", reply_markup=get_back_and_view_tasks_markup())
            return
        if cmd == "edit" and 0 <= idx < len(tasks):
            temp_task[user_id] = {"edit_index": idx}
            user_states[user_id] = "editing_name"
            await q.edit_message_text("Enter the *new task name*:", parse_mode="Markdown")
            return

    # 🔙 Back to Menu
    if data == "back_to_menu":
        await q.edit_message_text(
            f"What would you like to do, {user.capitalize()}?",
            reply_markup=get_main_menu_markup(user)
        )
        return

    # 📅 Date selected
    if data.startswith("date_"):
        _, y, m, d = data.split("_")
        dt = datetime(int(y), int(m), int(d))
        temp_task[user_id]["date"] = dt
        await q.edit_message_text("Select the time:", reply_markup=get_time_markup())
        return

    # ⏰ Time selected
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
            await q.edit_message_text(
                "✅ Task updated!",
                reply_markup=get_back_and_view_tasks_markup()
            )
        else:
            user_tasks[user].append({
                "name": task_data["name"],
                "deadline": dt,
                "done": False
            })
            await q.edit_message_text(
                "✅ Task added!",
                reply_markup=get_back_and_view_tasks_markup()
            )
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id)
    user = user_selection.get(user_id)

    # Entering or editing task name
    if state in ("awaiting_name", "editing_name"):
        temp_task[user_id] = temp_task.get(user_id, {})
        temp_task[user_id]["name"] = update.message.text
        user_states[user_id] = None
        await update.message.reply_text(
            "Now choose a deadline date:",
            reply_markup=get_deadline_date_markup()
        )
    else:
        await update.message.reply_text("Please use /start to begin.")

async def main():
    app = ApplicationBuilder().token("7877522996:AAFljhNT3EEguS9kZECBTGRW5M5gcvivbUU").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(user_selector, pattern="^user_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot is running…")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
