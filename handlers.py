import telebot
from telebot import types
import json
import os

# Импортируем боевую логику
from combat import (
    start_combat,
    player_combat_round,
    get_combat_keyboard,
    get_ai_combat_context,
    generate_enemies,
)

# ============================================================
#  НАСТРОЙКИ БОТА
# ============================================================
BOT_TOKEN = "ТВОЙ_ТОКЕН"  # <-- ВСТАВЬ СЮДА ТОКЕН ОТ @BotFather
bot = telebot.TeleBot(BOT_TOKEN)

# Путь к файлу сохранения состояний (в продакшене лучше БД)
STATE_FILE = "states.json"

# ============================================================
#  РАБОТА С СОСТОЯНИЯМИ (STATE)
# ============================================================

def load_state(user_id):
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(str(user_id), {})
    except:
        return {}

def save_state(user_id, state):
    data = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    data[str(user_id)] = state
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================
#  СТАРТОВЫЕ КОМАНДЫ
# ============================================================

@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id
    state = load_state(user_id)
    
    # Если есть активный бой — предупреждаем, что начинаем заново
    if state.get("combat", {}).get("active"):
        bot.reply_to(message, "⚠️ У тебя уже идёт бой! Чтобы начать заново, используй /reset или сначала заверши бой.")
        return

    # Создаём базовое состояние
    state = {
        "user_id": user_id,
        "class_key": "warrior",          # по умолчанию воин
        "class_name": "Воин",
        "hp": 20,
        "max_hp": 20,
        "is_wounded": False,
        "inventory": [],
        "has_torch": True,
        "skills": {
            "сила": 16,
            "выносливость": 14,
            "ловкость": 10,
            "знание": 8,
            "восприятие": 12,
        },
        "combat": None,
    }
    save_state(user_id, state)
    
    text = (
        "🎮 Добро пожаловать в RPG-бот!\n\n"
        "Ты — Воин. У тебя есть факел, и ты готов к приключениям.\n"
        "Нажми /fight, чтобы начать бой с врагами."
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=["fight"])
def cmd_fight(message):
    user_id = message.from_user.id
    state = load_state(user_id)
    
    if state.get("combat", {}).get("active"):
        bot.reply_to(message, "⚔️ Ты уже в бою! Используй кнопки под сообщением.")
        return
    
    # Запускаем бой
    intro_text = start_combat(state)
    save_state(user_id, state)
    
    kb = get_combat_keyboard(state)
    bot.send_message(user_id, intro_text, reply_markup=kb)

@bot.message_handler(commands=["reset"])
def cmd_reset(message):
    user_id = message.from_user.id
    os.remove(STATE_FILE) if os.path.exists(STATE_FILE) else None
    bot.reply_to(message, "🧹 Сохранения сброшены. Напиши /start, чтобы начать заново.")

# ============================================================
#  ОБРАБОТКА КНОПОК (CALLBACKS)
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    user_id = call.from_user.id
    state = load_state(user_id)
    
    # Если нет состояния или бой не активен — игнорируем старые кнопки
    if not state.get("combat", {}).get("active") and not call.data.startswith("cmb:start"):
        bot.answer_callback_query(call.id, "Бой не идёт. Нажми /fight для начала.")
        return

    action = None
    action_key = None

    # Парсим callback_data
    # Варианты: atk:удар, atk:размах, cmb:retreat, cmb:escape, cmb:potion
    if call.data.startswith("atk:"):
        action = "attack"
        action_key = call.data[4:]
    elif call.data == "cmb:retreat":
        action = "retreat"
    elif call.data == "cmb:escape":
        action = "escape"
    elif call.data == "cmb:potion":
        action = "potion"
    else:
        bot.answer_callback_query(call.id, "Неизвестная команда.")
        return

    # Выполняем боевой раунд
    result = player_combat_round(state, action, action_key)
    save_state(user_id, state)

    # Обновляем сообщение
    if result["combat_ended"]:
        if result["result_type"] == "victory":
            text = f"{result['text']}\n\n🏆 Победа! Ты одолел врагов."
        elif result["result_type"] == "defeat":
            text = f"{result['text']}\n\n💀 Ты потерял сознание. Враги решают твою судьбу..."
        elif result["result_type"] == "escape":
            text = f"{result['text']}\n\n💨 Ты вырвался из боя!"
        else:
            text = result["text"]
        
        # Убираем клавиатуру при конце боя
        bot.edit_message_text(text, user_id, call.message.message_id)
        # Можно добавить кнопку «Начать заново»
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🗡️ Начать заново", callback_data="cmb:start"))
        bot.send_message(user_id, "Что будешь делать дальше?", reply_markup=kb)
    else:
        # Бой продолжается — обновляем текст и клавиатуру
        kb = get_combat_keyboard(state)
        bot.edit_message_text(result["text"], user_id, call.message.message_id, reply_markup=kb)

    bot.answer_callback_query(call.id)

# ============================================================
#  ИНТЕГРАЦИЯ С ИИ-МАСТЕРОМ (ДЛЯ НАРРАТИВА)
# ============================================================

# Пример: если ты хочешь, чтобы ИИ писал описание после каждого раунда,
# передавай get_ai_combat_context(state) в промпт ИИ.
# Ниже — заглушка, как это можно сделать.

def generate_narrative(state):
    """
    Здесь ты подключаешь свой ИИ-мастер.
    Возвращает дополнительный нарративный текст на основе состояния боя.
    """
    context = get_ai_combat_context(state)
    # TODO: вызвать API или локальную модель с этим контекстом
    # narration = ai_master.generate(context)
    narration = f"[ИИ-МАСТЕР: {context}]"  # заглушка
    return narration

# Если хочешь, чтобы после каждого хода ИИ добавлял описание,
# можно модифицировать player_combat_round в combat.py, чтобы он возвращал
# не только текст, но и «narrative_extra», а потом вставлять его в result["text"].

# ============================================================
#  ЗАПУСК
# ============================================================

if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True)
    
