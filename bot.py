# Dev by ErR
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ChatPermissions
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import Command
import sqlite3
import time
import os
import asyncio

API_TOKEN = os.getenv("BOT_TOKEN") or "6921670195:AAGCnDfsLweOIj6AbZLaG6alveYbs9NPCu4"
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID") or 0)  # ID лог-канала

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

conn = sqlite3.connect('karma.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS karma (user_id INTEGER PRIMARY KEY, username TEXT, karma INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER, target_id INTEGER, reason TEXT, timestamp INTEGER)''')
conn.commit()

def change_karma(user_id, username, delta):
    c.execute('SELECT karma FROM karma WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    if row:
        c.execute('UPDATE karma SET karma = karma + ? WHERE user_id = ?', (delta, user_id))
    else:
        c.execute('INSERT INTO karma (user_id, username, karma) VALUES (?, ?, ?)', (user_id, username, delta))
    conn.commit()

def get_karma(user_id):
    c.execute('SELECT karma FROM karma WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    return row[0] if row else 0

def log_action(text):
    if LOG_CHANNEL_ID:
        try:
            return bot.send_message(LOG_CHANNEL_ID, text)
        except Exception as e:
            logging.warning(f"Ошибка при логировании: {e}")

@dp.message_handler(commands=['plus', 'minus'])
async def karma_vote(message: types.Message):
    if not message.reply_to_message:
        await message.reply("Ответь на сообщение пользователя, чтобы изменить карму.")
        return

    target = message.reply_to_message.from_user
    if message.from_user.id == target.id:
        await message.reply("Нельзя голосовать за самого себя.")
        return

    delta = 1 if message.text.startswith('/plus') else -1
    change_karma(target.id, target.username or target.full_name, delta)
    await message.reply(f"Карма пользователя {target.full_name} теперь {get_karma(target.id)}")
    await log_action(f"{message.from_user.full_name} изменил карму {target.full_name} на {delta}")

@dp.message_handler(commands=['karma'])
async def karma_check(message: types.Message):
    user = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.reply(f"Карма пользователя {user.full_name}: {get_karma(user.id)}")

@dp.message_handler(commands=['mute'])
async def mute_user(message: types.Message):
    if not message.reply_to_message:
        await message.reply("Ответь на сообщение пользователя, чтобы замутить его.")
        return
    user_id = message.reply_to_message.from_user.id
    until_date = int(time.time()) + 60 * 5  # 5 минут по умолчанию
    await bot.restrict_chat_member(
        message.chat.id,
        user_id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=until_date
    )
    await message.reply("Пользователь замучен на 5 минут.")
    await log_action(f"{message.from_user.full_name} замутил {message.reply_to_message.from_user.full_name} на 5 минут")

@dp.message_handler(commands=['ban'])
async def ban_user(message: types.Message):
    if not message.reply_to_message:
        await message.reply("Ответь на сообщение пользователя, чтобы забанить его.")
        return
    user_id = message.reply_to_message.from_user.id
    await bot.kick_chat_member(message.chat.id, user_id)
    await message.reply("Пользователь забанен.")
    await log_action(f"{message.from_user.full_name} забанил {message.reply_to_message.from_user.full_name}")

@dp.message_handler(commands=['unban'])
async def unban_user(message: types.Message):
    if not message.reply_to_message:
        await message.reply("Ответь на сообщение пользователя, чтобы разбанить его.")
        return
    user_id = message.reply_to_message.from_user.id
    await bot.unban_chat_member(message.chat.id, user_id)
    await message.reply("Пользователь разбанен.")
    await log_action(f"{message.from_user.full_name} разбанил {message.reply_to_message.from_user.full_name}")

@dp.message_handler(commands=['report'])
async def report_user(message: types.Message):
    if not message.reply_to_message:
        await message.reply("Ответь на сообщение пользователя, чтобы пожаловаться на него.")
        return

    parts = message.text.split(maxsplit=1)
    reason = parts[1] if len(parts) > 1 else "Не указана"

    reporter = message.from_user
    target = message.reply_to_message.from_user

    c.execute('INSERT INTO reports (reporter_id, target_id, reason, timestamp) VALUES (?, ?, ?, ?)',
              (reporter.id, target.id, reason, int(time.time())))
    conn.commit()

    await message.reply(f"Жалоба на {target.full_name} отправлена модераторам.")
    await log_action(f"Жалоба от {reporter.full_name} на {target.full_name}. Причина: {reason}")

@dp.chat_member_handler()
async def welcome_new_user(event: types.ChatMemberUpdated):
    if event.new_chat_member.status == "member":
        user = event.from_user
        chat = event.chat
        welcome_message = await bot.send_message(
            chat.id,
            f"👋 Добро пожаловать, {user.full_name}, в группу ТСЖ \"Ботанический сад\"!\nПожалуйста, соблюдайте уважительное поведение и избегайте спама."
        )
        await log_action(f"{user.full_name} присоединился к группе.")
        await asyncio.sleep(180)  # 3 минуты
        try:
            await bot.delete_message(chat.id, welcome_message.message_id)
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение: {e}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
