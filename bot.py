import re 
import asyncio
from bs4 import BeautifulSoup
import telebot
from telebot import types
from playwright.async_api import async_playwright

# ==================== الإعدادات ====================
BOT_TOKEN = "8467970543:AAEw_vtsjqMMytzITlbeqEAgiaXY8xG72lk"  # ضع توكين البوت هنا
ADMIN_ID = 8008834583                  # ضع آيدي الأدمن هنا
# ===================================================

bot = telebot.TeleBot(BOT_TOKEN)

stock_emails = []  # قائمة الإيميلات المتاحة
user_scores = {}    # نقاط المستخدمين
active_orders = {}  # الإيميلات النشطة للمستخدمين

async def extract_code_with_playwright(mail_address, mail_password):
    """فتح متصفح حقيقي لتجاوز الجافاسكريبت وسحب الكود"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # 1. التوجه لصفحة الدخول
            await page.goto("https://login.live.com/login.srf", timeout=30000)
            
            # 2. كتابة الإيميل
            await page.wait_for_selector('input[type="email"]', timeout=15000)
            await page.fill('input[type="email"]', mail_address)
            
            # الضغط على زر التالي (يدعم كل أزرار مايكروسوفت)
            await page.click('input[type="submit"], #idSIButton9, button[type="submit"]')
            await page.wait_for_timeout(3000)

            # 3. كتابة كلمة السر
            await page.wait_for_selector('input[type="password"]', timeout=15000)
            await page.fill('input[type="password"]', mail_password)
            
            # الضغط على زر تسجيل الدخول
            await page.click('input[type="submit"], #idSIButton9, button[type="submit"]')
            await page.wait_for_timeout(5000)

            # 4. التخلص من شاشة "البقاء قيد تسجيل الدخول" (Stay signed in) إن ظهرت
            try:
                if await page.is_visible('#idSIButton9'):
                    await page.click('#idSIButton9')
                    await page.wait_for_timeout(3000)
                elif await page.is_visible('input[type="submit"]'):
                    await page.click('input[type="submit"]')
                    await page.wait_for_timeout(3000)
            except Exception:
                pass

            # 5. جلب محتوى البريد الإلكتروني
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            clean_text = soup.get_text(separator=' ')

            await browser.close()

            # استخراج أرقام الكود
            specific_code = re.findall(r'(?:رمز|كود|code|security|verification|confirm)[^\d]*(\d{4,8})', clean_text, re.IGNORECASE)
            if specific_code:
                return specific_code[-1], None

            fallback_codes = re.findall(r'\b\d{5,8}\b', clean_text)
            if fallback_codes:
                return fallback_codes[-1], None

            return None, "تم تسجيل الدخول لكن لم ينزل كود بالصندوق حتى الآن."

        except Exception as e:
            await browser.close()
            return None, f"خطأ في العناصر: {str(e)}"

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📩 الحصول على كود التفعيل"),
        types.KeyboardButton("💳 شراء حساب جديد")
    )
    markup.add(
        types.KeyboardButton("📦 سجل مشترياتي"),
        types.KeyboardButton("👤 حسابي الشخصي")
    )
    markup.add(
        types.KeyboardButton("📖 كيفية الاستخدام"),
        types.KeyboardButton("💰 شحن رصيد")
    )
    markup.add(types.KeyboardButton("🛠️ الدعم الفني"))
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if user_id not in user_scores:
        user_scores[user_id] = 100

    welcome_text = (
        f"السلام عليكم ورحمة الله وبركاته\n"
        f"رصيدك الحالي: {user_scores[user_id]}\n"
        f"عدد الإيميلات المتاحة: {len(stock_emails)}"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())

# أمر إضافة إيميلات (للأدمن)
@bot.message_handler(commands=['add'])
def add_stock(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "غير مسموح لك باستخدام هذا الأمر.")
        return

    try:
        args = message.text.split()[1:]
        cost = int(args[0])
        raw_emails = args[1:]
        added_count = 0

        for item in raw_emails:
            if ":" in item:
                m, p = item.split(":", 1)
                stock_emails.append({"mail": m, "pass": p, "cost": cost})
                added_count += 1

        bot.reply_to(message, f"تم إضافة {added_count} إيميل بنجاح بسعر {cost} نقطة.")
    except Exception:
        bot.reply_to(message, "الاستخدام الصحيح:\n`/add 10 email1:pass1 email2:pass2`", parse_mode="Markdown")

# أمر تعديل النقاط (للأدمن)
@bot.message_handler(commands=['setscore'])
def set_user_score(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "غير مسموح لك باستخدام هذا الأمر.")
        return

    try:
        args = message.text.split()
        target_id = int(args[1])
        points = int(args[2])

        user_scores[target_id] = points
        bot.reply_to(message, f"✅ تم تحديث رصيد المستخدم `{target_id}` بنجاح إلى {points} نقطة.", parse_mode="Markdown")

        try:
            bot.send_message(target_id, f"🎉 تم تحديث رصيدك الحالي ليصبح: {points} نقطة.")
        except Exception:
            pass

    except Exception:
        bot.reply_to(message, "الاستخدام الصحيح:\n`/setscore ID_المستخدم عدد_النقاط`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_menu_click(message):
    user_id = message.from_user.id
    text = message.text

    if text in ["💳 شراء حساب جديد", "حساب جديد 📧"]:
        if not stock_emails:
            bot.reply_to(message, "عذراً، لا توجد إيميلات متاحة حالياً.")
            return

        item = stock_emails[0]
        cost = item["cost"]
        current_score = user_scores.get(user_id, 0)

        if current_score < cost:
            bot.reply_to(message, f"عذراً، لا تملك نقاط كافية. مطلوب: {cost} | لديك: {current_score}")
            return

        user_scores[user_id] -= cost
        email_data = stock_emails.pop(0)
        active_orders[user_id] = email_data

        msg_text = (
            f"📧 البريد: `{email_data['mail']}`\n\n"
            f"📌 للحصول على الكود، اضغط على زر (📩 الحصول على كود التفعيل)."
        )
        bot.send_message(message.chat.id, msg_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif text == "📩 الحصول على كود التفعيل":
        if user_id not in active_orders:
            bot.reply_to(message, "ليس لديك إيميل نشط حالياً لطلب الكود.")
            return

        bot.send_message(message.chat.id, "🌐 جارِ فتح المتصفح وتجاوز حماية الجافاسكريبت لجلب الكود...")
        acc = active_orders[user_id]
        
        # تشغيل Playwright
        code, error = asyncio.run(extract_code_with_playwright(acc["mail"], acc["pass"]))

        if code:
            res_text = (
                f"📩 كود التفعيل المستخرج بنجاح:\n\n"
                f"✅ الحساب: `{acc['mail']}`\n"
                f"🔑 الكود: `{code}`"
            )
            bot.send_message(message.chat.id, res_text, parse_mode="Markdown", reply_markup=get_main_keyboard())
            del active_orders[user_id]
        else:
            bot.send_message(message.chat.id, f"❌ لم نتمكن من جلب الكود: {error}")

    elif text == "👤 حسابي الشخصي":
        bot.reply_to(message, f"معلومات حسابك:\nالرصيد: {user_scores.get(user_id, 0)} نقطة\nالآيدي: `{user_id}`", parse_mode="Markdown")

    elif text == "💰 شحن رصيد":
        bot.reply_to(message, "لتعبئة رصيدك يرجى التواصل مع الدعم الفني.")

    elif text == "🛠️ الدعم الفني":
        bot.reply_to(message, "تواصل مع الدعم الفني عبر الحساب الرسمي.")

    elif text == "📖 كيفية الاستخدام":
        bot.reply_to(message, "قم بشراء حساب جديد، ثم اضغط على زر 'الحصول على كود التفعيل'.")

    elif text == "📦 سجل مشترياتي":
        bot.reply_to(message, "لا توجد عمليات سابقة مسجلة.")

bot.polling(non_stop=True)

            # 3. إدخال كلمة السر
            await page.fill('input[type="password"]', mail_password)
            await page.click('input[type="submit"]')
            await page.wait_for_timeout(5000)

            # 4. تجاوز شاشات التنبيه المباشرة إذا ظهرت (مثل Stay Signed In)
            if await page.query_selector('input[type="submit"]'):
                await page.click('input[type="submit"]')
                await page.wait_for_timeout(3000)

            # 5. جلب محتوى النص الكامل للصفحة بعد تنفيذ الجافاسكريبت
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            clean_text = soup.get_text(separator=' ')

            await browser.close()

            # البحث عن أحدث كود أرقام مرتبط بكلمات التأكيد
            specific_code = re.findall(r'(?:رمز|كود|code|security|verification|confirm)[^\d]*(\d{4,8})', clean_text, re.IGNORECASE)
            if specific_code:
                return specific_code[-1], None

            fallback_codes = re.findall(r'\b\d{5,8}\b', clean_text)
            if fallback_codes:
                return fallback_codes[-1], None

            return None, "تم الدخول ولكن لم يتم العثور على أرقام كود في الصفحة."

        except Exception as e:
            await browser.close()
            return None, f"خطأ أثناء فتح المتصفح: {str(e)}"

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📩 الحصول على كود التفعيل"),
        types.KeyboardButton("💳 شراء حساب جديد")
    )
    markup.add(
        types.KeyboardButton("📦 سجل مشترياتي"),
        types.KeyboardButton("👤 حسابي الشخصي")
    )
    markup.add(
        types.KeyboardButton("📖 كيفية الاستخدام"),
        types.KeyboardButton("💰 شحن رصيد")
    )
    markup.add(types.KeyboardButton("🛠️ الدعم الفني"))
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if user_id not in user_scores:
        user_scores[user_id] = 100

    welcome_text = (
        f"السلام عليكم ورحمة الله وبركاته\n"
        f"رصيدك الحالي: {user_scores[user_id]}\n"
        f"عدد الإيميلات المتاحة: {len(stock_emails)}"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())

# أمر إضافة إيميلات (للأدمن)
@bot.message_handler(commands=['add'])
def add_stock(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "غير مسموح لك باستخدام هذا الأمر.")
        return

    try:
        args = message.text.split()[1:]
        cost = int(args[0])
        raw_emails = args[1:]
        added_count = 0

        for item in raw_emails:
            if ":" in item:
                m, p = item.split(":", 1)
                stock_emails.append({"mail": m, "pass": p, "cost": cost})
                added_count += 1

        bot.reply_to(message, f"تم إضافة {added_count} إيميل بنجاح بسعر {cost} نقطة.")
    except Exception:
        bot.reply_to(message, "الاستخدام الصحيح:\n`/add 10 email1:pass1 email2:pass2`", parse_mode="Markdown")

# أمر تعديل النقاط (للأدمن)
@bot.message_handler(commands=['setscore'])
def set_user_score(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "غير مسموح لك باستخدام هذا الأمر.")
        return

    try:
        args = message.text.split()
        target_id = int(args[1])
        points = int(args[2])

        user_scores[target_id] = points
        bot.reply_to(message, f"✅ تم تحديث رصيد المستخدم `{target_id}` بنجاح إلى {points} نقطة.", parse_mode="Markdown")

        try:
            bot.send_message(target_id, f"🎉 تم تحديث رصيدك الحالي ليصبح: {points} نقطة.")
        except Exception:
            pass

    except Exception:
        bot.reply_to(message, "الاستخدام الصحيح:\n`/setscore ID_المستخدم عدد_النقاط`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_menu_click(message):
    user_id = message.from_user.id
    text = message.text

    if text in ["💳 شراء حساب جديد", "حساب جديد 📧"]:
        if not stock_emails:
            bot.reply_to(message, "عذراً، لا توجد إيميلات متاحة حالياً.")
            return

        item = stock_emails[0]
        cost = item["cost"]
        current_score = user_scores.get(user_id, 0)

        if current_score < cost:
            bot.reply_to(message, f"عذراً، لا تملك نقاط كافية. مطلوب: {cost} | لديك: {current_score}")
            return

        user_scores[user_id] -= cost
        email_data = stock_emails.pop(0)
        active_orders[user_id] = email_data

        msg_text = (
            f"📧 البريد: `{email_data['mail']}`\n\n"
            f"📌 للحصول على الكود، اضغط على زر (📩 الحصول على كود التفعيل)."
        )
        bot.send_message(message.chat.id, msg_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif text == "📩 الحصول على كود التفعيل":
        if user_id not in active_orders:
            bot.reply_to(message, "ليس لديك إيميل نشط حالياً لطلب الكود.")
            return

        bot.send_message(message.chat.id, "🌐 جارِ فتح المتصفح وتجاوز حماية الجافاسكريبت لجلب الكود...")
        acc = active_orders[user_id]
        
        # تشغيل Playwright من داخل بيئة البوت المتزامنة
        code, error = asyncio.run(extract_code_with_playwright(acc["mail"], acc["pass"]))

        if code:
            res_text = (
                f"📩 كود التفعيل المستخرج بنجاح:\n\n"
                f"✅ الحساب: `{acc['mail']}`\n"
                f"🔑 الكود: `{code}`"
            )
            bot.send_message(message.chat.id, res_text, parse_mode="Markdown", reply_markup=get_main_keyboard())
            del active_orders[user_id]
        else:
            bot.send_message(message.chat.id, f"❌ لم نتمكن من جلب الكود: {error}")

    elif text == "👤 حسابي الشخصي":
        bot.reply_to(message, f"معلومات حسابك:\nالرصيد: {user_scores.get(user_id, 0)} نقطة\nالآيدي: `{user_id}`", parse_mode="Markdown")

    elif text == "💰 شحن رصيد":
        bot.reply_to(message, "لتعبئة رصيدك يرجى التواصل مع الدعم الفني.")

    elif text == "🛠️ الدعم الفني":
        bot.reply_to(message, "تواصل مع الدعم الفني عبر الحساب الرسمي.")

    elif text == "📖 كيفية الاستخدام":
        bot.reply_to(message, "قم بشراء حساب جديد، ثم اضغط على زر 'الحصول على كود التفعيل'.")

    elif text == "📦 سجل مشترياتي":
        bot.reply_to(message, "لا توجد عمليات سابقة مسجلة.")

bot.polling(non_stop=True)
