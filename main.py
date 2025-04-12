import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.methods import DeleteWebhook
import aiohttp
import textwrap

BOT_TOKEN = "7996849165:AAH1tkZsYQxwLfOguBvOKhc1FjareBp9_Bg"
API_TOKEN = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6ImIxM2RhY2NiLTNkYWItNDQzZC05NTlmLTM3ZGQxMDZkYmJjZCIsImV4cCI6NDg5ODA2ODgwMH0.jbBDc3pcXGiIYts9KfRgrajHfqSm6m2nrmuJ4ABb1UmnVoMsPWIJwbniYCeyGp6pyOXyoEsh0cod3PZ9PVMdXw"
MAX_MESSAGE_LENGTH = 4096

PROMPT = """
Ты — эксперт по партнёрской программе Яндекс Еда. Отвечай только по тексту ниже, игнорируя другие темы: "Это вне моего руководства. Задайте вопрос о программе." Дай точные, краткие ответы.
Особенности:
- На вопросы "Как начать?" или "Как стать партнёром?": "Свяжитесь с менеджером: @yandexproeda."
- На вопросы о ставках: "Ставки для рекрутеров зависят от города. Проверьте в ЛК: https://partners-app.taxi.yandex.ru/tariffs."
- Конкретные ставки по городам — из таблицы, только для рекрутеров, указывай город, ставку за заказ, базовую ставку, максимальный доход, период (14.04.2025–20.04.2025). Не используй ставки в постах для курьеров.
- Даты выплат: за период 1–31, до 20-го следующего месяца (например, за февраль — до 20 марта).
- Контент-план: предложи план публикаций (соцсети, job-сайты) для аудитории 18+, с примерами каналов (ВКонтакте, Telegram, hh.ru).
- Пост для соцсетей: для курьеров, укажи преимущества (гибкий график, стабильный доход, самозанятость), город, ссылку (например, bit.ly/yandexproeda, если указана). Не упоминай ставки из таблицы, только общие фразы вроде "высокий доход". Не включай шаг с презентацией. Добавь маркировку: "Реклама, erid".
- Ответ кандидату: опиши шаги для курьеров (регистрация, оформление в КЦ/чат-боте, самозанятость, первый слот, заказы), без ссылок и без упоминания презентации.
Таблица ставок (14.04.2025–20.04.2025, только для рекрутеров):
- Москва: 250 ₽/заказ, база 1250 ₽, макс. 32500 ₽/курьер.
- Солнечногорск: 300 ₽/заказ, база 1500 ₽, макс. 39000 ₽.
- Тверь: 200 ₽/заказ, база 1000 ₽, макс. 26000 ₽.
- Владимир: 150 ₽/заказ, база 750 ₽, макс. 19500 ₽.
- Люберцы: 90 ₽/заказ, база 450 ₽, макс. 11700 ₽.
- Химки, Красногорск: 300 ₽/заказ, база 1500 ₽, макс. 39000 ₽.
- Мытищи: 150 ₽/заказ, база 750 ₽, макс. 19500 ₽.
- Балашиха: 200 ₽/заказ, база 1000 ₽, макс. 26000 ₽.
- Королёв: 100 ₽/заказ, база 500 ₽, макс. 13000 ₽.
- Одинцово: 250 ₽/заказ, база 1250 ₽, макс. 32500 ₽.
- Пушкино: 160 ₽/заказ, база 800 ₽, макс. 20800 ₽.
- Санкт-Петербург, Сочи: 200 ₽/заказ, база 1000 ₽, макс. 26000 ₽.
Руководство:
- Подготовка: изучи ЛК (раздел Информация).
- Выплаты: за целевые действия, раз в месяц (1–31, до 20-го), на карту. Проверяй статус в ЛК. Оспаривай, если ошибка.
- Привлечение:
  - Источники: hh.ru, Авито, ВКонтакте, Telegram, вузы, рекомендации.
  - Аудитория: 18+, учитывай интересы.
  - Объявления: для курьеров — график, доход (без цифр). Нет отклика — смени текст/канал.
  - Процесс: найди кандидата → отправь ссылку ЛК → опиши шаги → следи за статусом → выплата.
  - Пуш: напоминай о шагах. Закрепление: 7 дней, повторная регистрация при неактивности.
- Правила: соблюдай маркировку (erid, «Реклама»), избегай фрода. Нарушение = разрыв договора.
- Вопросы:
  - "Зарегистрирован": деактивируй, перерегистрируй.
  - Статус: жди сутки, оспаривай.
  - Отказ в КЦ: дай менеджеру данные кандидата.
  - ЛК: логин без «@yandex.ru», иначе — к менеджеру.
- Кандидаты: РФ 18+ («Мой налог», КЦ/бот), 16+ (с заявлением), не РФ (документы, КЦ).
- Ресурсы: ЛК, поддержка (@yandexproeda), чат-бот: https://t.me/Eda_online_activation_bot.
Инструкции для ИИ:
- Отвечай строго по тексту/таблице.
- Кратко, с эмодзи (✅, ❓).
"""

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
sessions = {}

async def typing_animation(chat_id):
    await bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(1)

def split_message(text, max_length=MAX_MESSAGE_LENGTH):
    return textwrap.wrap(text, max_length, replace_whitespace=False)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    welcome_text = (
        "👋 Привет! Я твой помощник по партнёрской программе Яндекс Еда! 🚀\n"
        "Готов ответить на любые вопросы о привлечении курьеров, выплатах и правилах.\n"
        "❓ Задай вопрос, например: *Как привлечь курьеров?* или *Когда мне заплатят?*"
    )
    await message.answer(welcome_text, parse_mode="Markdown")
    sessions[message.chat.id] = PROMPT

@dp.message()
async def handle_message(message: Message):
    if message.text.startswith("/"):
        return

    chat_id = message.chat.id
    thinking_msg = await bot.send_sticker(chat_id, "CAACAgIAAxkBAAECmpln-pz5GKR-kKvD9qHpFPfTYfQxYAACIwADKA9qFCdRJeeMIKQGNgQ")
    await typing_animation(chat_id)

    if chat_id not in sessions:
        sessions[chat_id] = PROMPT

    url = "https://api.intelligence.io.solutions/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
    }
    data = {
        "model": "deepseek-ai/DeepSeek-R1",
        "messages": [
            {"role": "system", "content": sessions[chat_id]},
            {"role": "user", "content": message.text}
        ],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                await bot.delete_message(chat_id, thinking_msg.message_id)
                if response.status != 200:
                    error = await response.text()
                    await message.answer(f"❌ Ошибка API: {error}")
                    return

                response_data = await response.json()
                if 'choices' in response_data:
                    bot_response = response_data['choices'][0]['message']['content']
                    if '</think>' in bot_response:
                        bot_response = bot_response.split('</think>')[-1].strip()

                    messages = split_message(bot_response)
                    for msg in messages:
                        await message.answer(msg, parse_mode="Markdown")
                        if len(messages) > 1:
                            await asyncio.sleep(0.5)
                else:
                    await message.answer("❌ Не удалось обработать ответ API")
    except Exception as e:
        await bot.delete_message(chat_id, thinking_msg.message_id)
        await message.answer(f"❌ Произошла ошибка: {str(e)}")

async def main():
    await bot(DeleteWebhook(drop_pending_updates=True))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
