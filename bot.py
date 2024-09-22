


import asyncio
import logging
import aiohttp
import sys
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import  Message, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery, ReplyKeyboardMarkup, KeyboardButton

TOKEN = "7511166749:AAEeEAYIraX-VHhWZa1EYxuPqXeJ195IZO0"
ADMINS = [5541564692]

bot = Bot(token=TOKEN)
dp = Dispatcher()


logging.basicConfig(level=logging.INFO, handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler('bot.log')
])


user_states = {}


async def check_subscription(user_id):
    url = 'https://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/channels/'  # Kanallar API manzili

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            channels = await response.json()

    for channel in channels:
        try:
            chat_id = channel['channel_id']
            chat_member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if chat_member.status in ['left', 'kicked']:
                return False

        except Exception as e:
            logging.error(f"Error checking subscription for channel {channel['channel_id']}: {e}")
            return False
    return True


async def ensure_subscription(message: Message):
    user_id = message.from_user.id

    if not await check_subscription(user_id):
        # If user is not subscribed, remove all buttons and show the subscription prompt
        await send_subscription_prompt(message)
        return False  # Indicate that the user is not subscribed
    return True  # User is subscribed


async def get_inline_keyboard_for_channels():
    url = 'https://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/channels/'  # Kanallar API manzili
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            channels = await response.json()

    inline_keyboard = []
    for channel in channels:
        channel_name = channel['name']
        channel_url = channel['url']
        inline_keyboard.append([InlineKeyboardButton(text=f"{channel_name}", url=channel_url)])

    # "A'zo bo'ldim" button
    inline_keyboard.append([InlineKeyboardButton(text="✅A'zo bo'ldim", callback_data='azo')])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

async def send_subscription_prompt(message: Message):
    user_id = message.from_user.id

    # Remove old inline keyboard if exists
    if 'last_inline_message_id' in user_states.get(user_id, {}):
        await delete_previous_inline_message(message.chat.id, user_states[user_id]['last_inline_message_id'])

    inline_keyboard = await get_inline_keyboard_for_channels()
    sent_message = await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=inline_keyboard)

    # Store the message ID for future reference
    user_states[user_id] = user_states.get(user_id, {})
    user_states[user_id]['last_inline_message_id'] = sent_message.message_id


@dp.callback_query(lambda c: c.data == 'azo')
async def callback_handler(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username

    if await check_subscription(user_id):
        # Foydalanuvchini `users` ro'yxatiga qo'shish yoki yangilash
        url = 'https://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/users/'
        headers = {
            'Authorization': f'Bearer {TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            'telegram_id': user_id,
            'username': username,
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 201:
                        logging.info(f"User {username} successfully added via API.")
                    elif response.status == 400:
                        response_text = await response.text()
                        if "user with this telegram id already exists" in response_text:
                            logging.info(f"User {username} already exists")
                        else:
                            logging.error(f"Failed to add user via API: {response.status} - {response_text}")
                            await callback_query.message.answer("Foydalanuvchini qo'shishda xatolik yuz berdi.")
                            return
                    else:
                        logging.error(f"Failed to add user via API: {response.status}")
                        await callback_query.message.answer("Foydalanuvchini qo'shishda xatolik yuz berdi.")
                        return
            except Exception as e:
                logging.error(f"Error communicating with API: {e}")
                await callback_query.message.answer("Foydalanuvchini qo'shishda xatolik yuz berdi.")
                return
        user_states[user_id] = {'state': 'searching_movie'}

        # `command_start_handler` funksiyasini chaqirish
        await command_start_handler(callback_query.message, callback_query.from_user.first_name)
    else:
        await send_subscription_prompt(callback_query.message)


async def delete_previous_inline_message(chat_id, message_id):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logging.error(f"Failed to delete previous inline message: {e}")


@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Obuna holatini tekshiramiz
    if not await ensure_subscription(message):
        return

    url = 'https://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/users/'
    payload = {
        'telegram_id': user_id,
        'username': username,
    }
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json'
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 201:
                    logging.info(f"User {username} successfully added via API.")
                elif response.status == 400:
                    response_text = await response.text()
                    if "user with this telegram id already exists" in response_text:
                        logging.info(f"User {username} already exists")
                    else:
                        logging.error(f"Failed to add user via API: {response.status} - {response_text}")
                        await message.answer("Foydalanuvchini qo'shishda xatolik yuz berdi.")
                        return
                else:
                    logging.error(f"Failed to add user via API: {response.status}")
                    await message.answer("Foydalanuvchini qo'shishda xatolik yuz berdi.")
                    return
        except Exception as e:
            logging.error(f"Error communicating with API: {e}")
            await message.answer("Foydalanuvchini qo'shishda xatolik yuz berdi.")
            return

    # Set the user state to 'searching_movie' after adding/updating the user
    user_states[user_id] = {'state': 'searching_movie'}
    await command_start_handler(message, message.from_user.first_name)


async def command_start_handler(message: Message, first_name: str):
    user_id = message.from_user.id

    if await check_subscription(user_id):
        is_admin = user_id in ADMINS

        admin_buttons = []
        if is_admin:
            admin_buttons = [
                [KeyboardButton(text="🛠 Admin Panel")]
            ]

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🤖 Telegram bot yasatish")],
                *admin_buttons
            ],
            resize_keyboard=True
        )
        user_states[user_id] = {'state': 'searching_movie'}
        await message.answer(f"<b>👋Salom {first_name}</b>\n\n<i>Kino kodini kiriting...</i>", reply_markup=keyboard,
                             parse_mode='html')
    else:
        await send_subscription_prompt(message)



@dp.message(lambda message: message.text == "🛠 Admin Panel")
async def admin_panel(message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.answer("Sizda admin panelga kirish huquqi mavjud emas.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data='add_movie')],
        [InlineKeyboardButton(text="📣 Xabar yuborish", callback_data='send_message')],
        [InlineKeyboardButton(text="📊 Statistika", callback_data='stats')],
    ])
    await message.answer("Admin panel:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data == 'add_movie')
async def add_movie_start(message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.answer("Sizda kino qo'shish huquqi mavjud emas.")
        return
    user_states[message.from_user.id] = {'state': 'adding_movie', 'step': 'title'}
    await message.answer("Kino nomini yuboring.", reply_markup=only_back_keyboard())

# State dictionary to track user actions

@dp.callback_query(lambda c: c.data == 'send_message')
async def send_message_prompt(callback_query: CallbackQuery):
    """Handler for the 'send_message' button - prompts admin to send a message."""
    await callback_query.message.answer("Xabar yuborish uchun xabar matnini yuboring (text, file, MP4, MP3).")
    user_states[callback_query.from_user.id] = {'state': 'sending_message'}


@dp.message(lambda m: user_states.get(m.from_user.id, {}).get('state') == 'sending_message')
async def handle_send_message(message: Message):
    """Handler for processing the message content after the admin sends a message."""
    user_id = message.from_user.id

    # Check subscription before proceeding
    if not await ensure_subscription(message):
        return

    # Fetch the text or file content to send
    text = message.text  # You can extend this to handle files or other media types if needed

    # Fetch the list of users from the API
    async with aiohttp.ClientSession() as session:
        async with session.get('https://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/users/') as response:
            if response.status != 200:
                await message.answer("Foydalanuvchilarni olishda xatolik yuz berdi!")
                return

            users = await response.json()

    # Send the message to each user
    sent_count = 0
    failed_count = 0

    for user in users:
        user_telegram_id = user['telegram_id']
        try:
            await bot.send_message(user_telegram_id, text)
            sent_count += 1
        except Exception as e:
            logging.error(f"Xabar yuborishda xatolik {user_telegram_id} ga: {e}")
            failed_count += 1

    # Send confirmation message to the admin
    await message.answer(
        f"Xabar yuborildi:\n"
        f"✅ Muvaffaqiyatli: {sent_count} foydalanuvchi\n"
        f"❌ Xatoliklar: {failed_count} foydalanuvchi"
    )

    # Reset the state for this user
    user_states[user_id] = {'state': 'searching_movie'}


@dp.callback_query(lambda c: c.data == 'stats')
async def stats(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if not await ensure_subscription(callback_query.message):
        return

    # Statistika olish (har bir API'dan alohida)
    async with aiohttp.ClientSession() as session:
        async with session.get(
                'https://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/users/') as users_response:
            users_data = await users_response.json()
            total_users = len(users_data)  # Assuming the API returns a list of users

        async with session.get(
                'https://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/channels/') as channels_response:
            channels_data = await channels_response.json()
            total_channels = len(channels_data)  # Assuming the API returns a list of channels

        async with session.get(
                'https://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/movies/') as movies_response:
            movies_data = await movies_response.json()
            total_movies = len(movies_data)  # Assuming the API returns a list of movies

    # Statistika xabarini yaratish
    stats_message = (
        f"📊 Statistika:\n"
        f"• Kanallar: {total_channels}\n"
        f"• Filmlar: {total_movies}\n"
        f"• Foydalanuvchilar: {total_users}\n"
    )

    await callback_query.message.answer(stats_message)


@dp.message(lambda message: message.text == "🤖 Telegram bot yasatish")
async def telegram_service_request(message: Message):
    user_id = message.from_user.id
    t = ("<b>🤖Telegram bot yaratish xizmati🤖</b>\n\n"
         "Admin: @otabek_mma1\n\n"
         "<i>Adminga bot nima haqida\n"
         "bot qanday vazifalarni bajarish kerak\n"
         "toliq malumot yozib qo'ying</i>\n\n"
         "Shunga qarab narxi kelishiladi")
    await message.answer(text=t, parse_mode='html')
async def save_movie_to_db(user_id):
    movie_data = user_states.get(user_id)
    if not movie_data:
        return False

    url = 'https://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/movies/'

    async with aiohttp.ClientSession() as session:
        data = {
            'title': movie_data.get('title'),
            'year': movie_data.get('year'),
            'genre': movie_data.get('genre'),
            'language': movie_data.get('language'),
            'code': movie_data.get('code'),
            'video_file_id': movie_data.get('video_file_id'),
        }
        async with session.post(url, json=data) as resp:
            if resp.status == 201:
                return True
            else:
                logging.error(f"Error saving movie: {await resp.text()}")
                return False

def only_back_keyboard():
    # Implement this function to provide a keyboard with a back button
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔙 Orqaga")]
    ], resize_keyboard=True)

# Handler for adding movie
@dp.message(lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get('state') == 'adding_movie')
async def add_movie(message: Message):
    user_id = message.from_user.id
    state = user_states[user_id]['step']

    if message.text == "🔙 Orqaga":
        await command_start_handler(message, message.from_user.first_name)
        return

    if state == 'title':
        user_states[user_id]['title'] = message.text
        user_states[user_id]['step'] = 'year'
        await message.answer("Kino yilini yuboring.", reply_markup=only_back_keyboard())
    elif state == 'year':
        try:
            user_states[user_id]['year'] = int(message.text)
            user_states[user_id]['step'] = 'genre'
            await message.answer("Kino janrini yuboring.", reply_markup=only_back_keyboard())
        except ValueError:
            await message.answer("Yil raqam bo'lishi kerak. Iltimos, qaytadan kiriting.")
    elif state == 'genre':
        user_states[user_id]['genre'] = message.text
        user_states[user_id]['step'] = 'language'
        await message.answer("Kino tilini yuboring.", reply_markup=only_back_keyboard())
    elif state == 'language':
        user_states[user_id]['language'] = message.text
        user_states[user_id]['step'] = 'code'
        await message.answer("Kino kodini yuboring.", reply_markup=only_back_keyboard())
    elif state == 'code':
        user_states[user_id]['code'] = message.text
        user_states[user_id]['step'] = 'video'
        await message.answer("Kino videosini yuklang (faqat MP4 format).", reply_markup=only_back_keyboard())
    elif state == 'video':
        if message.video and message.video.mime_type == 'video/mp4':
            file_id = message.video.file_id

            # Save the movie details including the video file ID to the database
            user_states[user_id]['video_file_id'] = file_id
            if await save_movie_to_db(user_id):
                await message.answer(f"Kino muvaffaqiyatli qo'shildi: {user_states[user_id]['title']}")
            else:
                await message.answer("Kino qo'shishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

            # Clear user state and go back to the admin panel
            user_states.pop(user_id, None)
            await command_start_handler(message, message.from_user.first_name)
        else:
            await message.answer("Iltimos, MP4 formatidagi videoni yuboring.")

async def search_movie_by_code(message: Message):
    user_id = message.from_user.id
    if not await ensure_subscription(message):
        return
    movie_code = message.text.strip()
    url = f'http://protected-wave-24975-ac981f81033d.herokuapp.com/api/v1/movies/?code={movie_code}'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                movies = await response.json()
                if movies:
                    movie = movies[0]
                    caption = (
                        f"<b>🎬Nomi:</b> {movie['title']}\n"
                        f"<b>📆Yili:</b> {movie['year']}\n"
                        f"<b>🎞Janr:</b> {movie['genre']}\n"
                        f"<b>🌍Tili:</b> {movie['language']}\n"
                        f"<b>🗂Yuklash:</b> {movie['code']}\n\n"
                        f"<b>🤖Bot:</b> @codermoviebot"
                    )

                    if movie['video_file_id']:
                        await bot.send_video(
                            chat_id=message.chat.id,
                            video=movie['video_file_id'],
                            caption=caption,
                            parse_mode='HTML'
                        )
                    else:
                        await message.answer("Kino videosi topilmadi.")
                else:
                    await message.answer("Kino topilmadi.")
            else:
                await message.answer("Ma'lumotlar bazasiga ulanishda xatolik.")

    # Foydalanuvchidan yana kod kiritishini so'raymiz
    user_states[user_id] = {'state': 'searching_movie'}

# Holatni tekshiradigan handler
@dp.message(lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get('state') == 'searching_movie')
async def search_movie_by_code_handler(message: Message):
    await search_movie_by_code(message)


async def main():
    await dp.start_polling(bot)



if __name__ == "__main__":
    asyncio.run(main())

