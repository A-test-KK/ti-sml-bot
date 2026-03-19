
import logging
import json
import os
import uuid
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration --- #
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8595929295:AAFFm4tfgoB8HVzbo3SINSP2R756zvHwQLg")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "1622282082")) # Ensure this is an integer

USERS_FILE = "users.json"
INVENTORY_FILE = "inventory.json"
ORDERS_FILE = "orders.json"

KBZPAY_NUMBER = "09xxxxxxxx"
WAVEPAY_NUMBER = "09xxxxxxxx"

# --- Data Loading/Saving --- #
def load_data(filename, default_value={}):
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(default_value, f, indent=4)
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

users = load_data(USERS_FILE)
inventory = load_data(INVENTORY_FILE)
orders = load_data(ORDERS_FILE, default_value=[])

# --- Helper Functions --- #
def is_admin(user_id):
    return user_id == ADMIN_CHAT_ID

def get_user_info(user_id):
    return users.get(str(user_id), {"balance": 0.0, "username": "N/A", "first_name": "N/A", "last_name": "N/A"})

def update_user_info(user_id, key, value):
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {"balance": 0.0, "username": "N/A", "first_name": "N/A", "last_name": "N/A", "top_up_requests": []}
    users[user_id_str][key] = value
    save_data(USERS_FILE, users)

def register_new_user(user_id, username, first_name, last_name):
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {
            "balance": 0.0,
            "username": username or "N/A",
            "first_name": first_name or "N/A",
            "last_name": last_name or "N/A",
            "top_up_requests": []
        }
        save_data(USERS_FILE, users)

# --- User Commands --- #
async def start(update: Update, context) -> None:
    user = update.effective_user
    register_new_user(user.id, user.username, user.first_name, user.last_name)
    await update.message.reply_html(
        f"<b>မင်္ဂလာပါ {user.first_name}!</b>\n\nSmile One ကုဒ်များ ဝယ်ယူရန် ကျွန်ုပ်၏ ဝန်ဆောင်မှုကို အသုံးပြုနိုင်ပါသည်။\n\nသင့်လက်ကျန်ငွေကို စစ်ဆေးရန် /balance ကိုနှိပ်ပါ။\nငွေဖြည့်ရန် /topup ကိုနှိပ်ပါ။\nကုဒ်များဝယ်ယူရန် /buy ကိုနှိပ်ပါ။"
    )

async def balance(update: Update, context) -> None:
    user_id = str(update.effective_user.id)
    user_data = get_user_info(user_id)
    current_balance = user_data["balance"]
    await update.message.reply_text(f"သင့်လက်ကျန်ငွေ: {current_balance:.2f} MMK")

async def topup(update: Update, context) -> None:
    user_id = str(update.effective_user.id)
    await update.message.reply_text(
        f"ငွေဖြည့်ရန်အတွက် KBZPay ({KBZPAY_NUMBER}) သို့မဟုတ် WavePay ({WAVEPAY_NUMBER}) သို့ ငွေလွှဲပြီး ငွေလွှဲပြေစာ (screenshot) ပို့ပေးပါ။\n\nAdmin မှ စစ်ဆေးပြီးပါက သင့်လက်ကျန်ငွေကို ဖြည့်ပေးပါမည်။"
    )
    # Store that user is expecting a screenshot for top-up
    context.user_data['awaiting_topup_screenshot'] = True

async def handle_photo(update: Update, context) -> None:
    user = update.effective_user
    user_id_str = str(user.id)

    if context.user_data.get('awaiting_topup_screenshot'):
        photo_file = await update.message.photo[-1].get_file()
        # In a real scenario, you'd upload this to a storage service (e.g., S3) and get a URL.
        # For this example, we'll just use the file_id as a placeholder.
        screenshot_url = photo_file.file_id # Placeholder

        request_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        top_up_request = {
            "request_id": request_id,
            "timestamp": timestamp,
            "screenshot_url": screenshot_url,
            "amount_requested": None, # User didn't specify amount in this flow
            "status": "pending"
        }

        if user_id_str not in users:
            register_new_user(user.id, user.username, user.first_name, user.last_name)
        users[user_id_str]["top_up_requests"].append(top_up_request)
        save_data(USERS_FILE, users)

        await update.message.reply_text("ငွေဖြည့်တောင်းဆိုမှုကို လက်ခံရရှိပါပြီ။ Admin မှ စစ်ဆေးပြီး အတည်ပြုပေးပါမည်။")
        
        # Notify admin
        admin_message = (
            f"New top-up request from user {user.first_name} ({user.username or user.id}).\n"
            f"Request ID: {request_id}\n"
            f"Screenshot: {screenshot_url}\n"
            f"To approve, use /approve_topup {user.id} {request_id} <amount>\n"
            f"To reject, use /reject_topup {user.id} {request_id}"
        )
        await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=screenshot_url, caption=admin_message)

        context.user_data['awaiting_topup_screenshot'] = False
    else:
        await update.message.reply_text("နားမလည်ပါဘူး။ /topup ကိုနှိပ်ပြီး ငွေဖြည့်တောင်းဆိုနိုင်ပါတယ်။")

async def buy(update: Update, context) -> None:
    user_id = str(update.effective_user.id)
    user_data = get_user_info(user_id)
    current_balance = user_data["balance"]

    if not inventory:
        await update.message.reply_text("လက်ရှိတွင် ဝယ်ယူနိုင်သော ကုဒ်များ မရှိသေးပါ။")
        return

    keyboard = []
    for product_name, codes in inventory.items():
        available_codes = [code for code in codes if code['status'] == 'available']
        if available_codes:
            # Assuming all codes of a product have the same price for display
            price = available_codes[0]['price']
            keyboard.append([InlineKeyboardButton(f"{product_name} ({price:.2f} MMK) - {len(available_codes)} ခု ရနိုင်သည်", callback_data=f"buy_{product_name}")])
    
    if not keyboard:
        await update.message.reply_text("လက်ရှိတွင် ဝယ်ယူနိုင်သော ကုဒ်များ မရှိသေးပါ။")
        return

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"သင်၏လက်ကျန်ငွေ: {current_balance:.2f} MMK\n\nဝယ်ယူလိုသော ကုဒ်အမျိုးအစားကို ရွေးချယ်ပါ။",
        reply_markup=reply_markup
    )

async def buy_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_data = get_user_info(user_id)
    current_balance = user_data["balance"]

    product_name = query.data.replace("buy_", "")

    if product_name not in inventory:
        await query.edit_message_text("တောင်းဆိုထားသော ကုဒ်အမျိုးအစားကို ရှာမတွေ့ပါ။")
        return

    available_codes = [code for code in inventory[product_name] if code['status'] == 'available']

    if not available_codes:
        await query.edit_message_text(f"{product_name} အတွက် ကုဒ်များ ကုန်သွားပါပြီ။")
        return
    
    # Pick the first available code
    code_to_buy = available_codes[0]
    code_price = code_to_buy['price']

    if current_balance < code_price:
        await query.edit_message_text(f"လက်ကျန်ငွေ မလုံလောက်ပါ။ လက်ကျန်ငွေ {current_balance:.2f} MMK သာရှိပြီး {code_price:.2f} MMK လိုအပ်ပါသည်။")
        return
    
    # Deduct balance and mark code as sold
    users[user_id]["balance"] -= code_price
    code_to_buy['status'] = 'sold'
    save_data(USERS_FILE, users)
    save_data(INVENTORY_FILE, inventory)

    # Log order
    order_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    orders.append({
        "order_id": order_id,
        "user_id": user_id,
        "timestamp": timestamp,
        "code_id": code_to_buy['code_id'],
        "code_value": code_to_buy['code'],
        "price_paid": code_price
    })
    save_data(ORDERS_FILE, orders)

    await query.edit_message_text(
        f"ဝယ်ယူမှု အောင်မြင်ပါသည်။\n\nသင်၏ {product_name} ကုဒ်: `{code_to_buy['code']}`\n\nကျန်ရှိသော လက်ကျန်ငွေ: {users[user_id]['balance']:.2f} MMK"
    )
    # Notify admin of the purchase
    admin_message = (
        f"User {query.from_user.first_name} ({query.from_user.username or query.from_user.id}) purchased {product_name}.\n"
        f"Code: {code_to_buy['code']}\n"
        f"Price: {code_price:.2f} MMK\n"
        f"Remaining balance: {users[user_id]['balance']:.2f} MMK"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message)

# --- Admin Commands --- #
async def admin(update: Update, context) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    await update.message.reply_text(
        "Admin Panel:\n"
        "/approve_topup <user_id> <request_id> <amount> - Approve a top-up request\n"
        "/reject_topup <user_id> <request_id> - Reject a top-up request\n"
        "/add_code <product_name> <price> <code_string> - Add a new code to inventory\n"
        "/view_inventory - View current inventory\n"
        "/view_users - View all users and their balances/top-up requests"
    )

async def approve_topup(update: Update, context) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    try:
        user_id_str, request_id, amount_str = context.args
        amount = float(amount_str)
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /approve_topup <user_id> <request_id> <amount>")
        return
    
    if user_id_str not in users:
        await update.message.reply_text(f"User {user_id_str} not found.")
        return
    
    user_data = users[user_id_str]
    request_found = False
    for req in user_data["top_up_requests"]:
        if req["request_id"] == request_id and req["status"] == "pending":
            req["status"] = "approved"
            user_data["balance"] += amount
            save_data(USERS_FILE, users)
            await update.message.reply_text(f"Top-up request {request_id} for user {user_id_str} approved. Balance increased by {amount:.2f} MMK.")
            await context.bot.send_message(chat_id=user_id, text=f"သင်၏ ငွေဖြည့်တောင်းဆိုမှု (ID: {request_id}) ကို Admin မှ အတည်ပြုပြီးပါပြီ။ သင့်လက်ကျန်ငွေ {amount:.2f} MMK ထပ်တိုးလာပါသည်။ စုစုပေါင်းလက်ကျန်ငွေ: {user_data['balance']:.2f} MMK")
            request_found = True
            break
    
    if not request_found:
        await update.message.reply_text(f"Pending top-up request {request_id} for user {user_id_str} not found or already processed.")

async def reject_topup(update: Update, context) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    try:
        user_id_str, request_id = context.args
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /reject_topup <user_id> <request_id>")
        return
    
    if user_id_str not in users:
        await update.message.reply_text(f"User {user_id_str} not found.")
        return
    
    user_data = users[user_id_str]
    request_found = False
    for req in user_data["top_up_requests"]:
        if req["request_id"] == request_id and req["status"] == "pending":
            req["status"] = "rejected"
            save_data(USERS_FILE, users)
            await update.message.reply_text(f"Top-up request {request_id} for user {user_id_str} rejected.")
            await context.bot.send_message(chat_id=user_id, text=f"သင်၏ ငွေဖြည့်တောင်းဆိုမှု (ID: {request_id}) ကို Admin မှ ပယ်ချလိုက်ပါပြီ။")
            request_found = True
            break
    
    if not request_found:
        await update.message.reply_text(f"Pending top-up request {request_id} for user {user_id_str} not found or already processed.")

async def add_code(update: Update, context) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    try:
        product_name, price_str, code_string = context.args
        price = float(price_str)
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /add_code <product_name> <price> <code_string>")
        return
    
    if product_name not in inventory:
        inventory[product_name] = []
    
    new_code = {
        "code_id": str(uuid.uuid4()),
        "code": code_string,
        "price": price,
        "status": "available"
    }
    inventory[product_name].append(new_code)
    save_data(INVENTORY_FILE, inventory)
    await update.message.reply_text(f"Code '{code_string}' for {product_name} (Price: {price:.2f} MMK) added to inventory.")

async def view_inventory(update: Update, context) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    if not inventory:
        await update.message.reply_text("Inventory is empty.")
        return
    
    response = "Current Inventory:\n"
    for product_name, codes in inventory.items():
        available_count = len([c for c in codes if c['status'] == 'available'])
        sold_count = len([c for c in codes if c['status'] == 'sold'])
        response += f"\nProduct: {product_name}\n"
        response += f"  Available: {available_count}\n"
        response += f"  Sold: {sold_count}\n"
        # Optionally list available codes (can be very long)
        # for code in codes:
        #     response += f"    - {code['code']} ({code['status']})\n"
    await update.message.reply_text(response)

async def view_users(update: Update, context) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    if not users:
        await update.message.reply_text("No users registered yet.")
        return
    
    response = "Registered Users:\n"
    for user_id, user_data in users.items():
        response += f"\nUser ID: {user_id}\n"
        response += f"  Name: {user_data.get('first_name', 'N/A')} {user_data.get('last_name', '')} (@{user_data.get('username', 'N/A')})\n"
        response += f"  Balance: {user_data['balance']:.2f} MMK\n"
        pending_requests = [req for req in user_data.get('top_up_requests', []) if req['status'] == 'pending']
        if pending_requests:
            response += "  Pending Top-up Requests:\n"
            for req in pending_requests:
                response += f"    - ID: {req['request_id']}, Screenshot: {req['screenshot_url']}\n"
                response += f"      To approve: /approve_topup {user_id} {req['request_id']} <amount>\n"
                response += f"      To reject: /reject_topup {user_id} {req['request_id']}\n"
    
    # Split long messages if necessary
    if len(response) > 4096: # Telegram message limit
        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i:i+4096])
    else:
        await update.message.reply_text(response)

# --- Main Function --- #
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # User Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("topup", topup))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))
    application.add_handler(CallbackQueryHandler(buy_callback, pattern='^buy_'))

    # Admin Handlers
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("approve_topup", approve_topup))
    application.add_handler(CommandHandler("reject_topup", reject_topup))
    application.add_handler(CommandHandler("add_code", add_code))
    application.add_handler(CommandHandler("view_inventory", view_inventory))
    application.add_handler(CommandHandler("view_users", view_users))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
