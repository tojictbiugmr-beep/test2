import telebot
import os
import random
from ai_client import client, MODEL
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from memory import (
    load_state, save_state, add_to_history,
    build_memory_context, maybe_summarize, reset_state, CLASS_STATS
)
from dice import check_action, format_roll_result, roll_d20
from combat import (
    CLASSES, ENEMIES, start_combat, player_combat_round,
    get_combat_keyboard, get_combat_status,
    get_ai_combat_context, generate_narrative,
    is_combat_active,
)

# === КЛЮЧИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# === ИНИЦИАЛИЗАЦИЯ ===
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# === СОСТОЯНИЕ ИГРОКОВ ===
player_state = {}


def get_state(chat_id):
    if chat_id not in player_state:
        state = load_state(chat_id)
        player_state[chat_id] = state
    return player_state[chat_id]


def save_chat(chat_id):
    state = player_state.get(chat_id)
    if state:
        save_state(chat_id, state)


# === ОТПРАВКА ДЛИННЫХ СООБЩЕНИЙ ===
def send_long_message(chat_id, text, reply_markup=None):
    limit = 4000
    if len(text) <= limit:
        bot.send_message(chat_id, text, reply_markup=reply_markup)
        return
    for i in range(0, len(text), limit):
        chunk = text[i:i + limit]
        bot.send_message(chat_id, chunk, reply_markup=reply_markup if i == 0 else None)


# === КЛАВИАТУРЫ ===
def class_keyboard():
    markup = InlineKeyboardMarkup()
    for key, cls in CLASSES.items():
        markup.add(InlineKeyboardButton(
            f"{cls['emoji']} {cls['name']}",
            callback_data=f"cls:{key}"
        ))
    return markup


def dice_keyboard():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🎲 Кинуть d20", callback_data="dice:roll"))
    markup.row(
        InlineKeyboardButton("💪 Сила", callback_data="dice:сила"),
        InlineKeyboardButton("🏃 Ловкость", callback_data="dice:ловкость"),
        InlineKeyboardButton("🛡️ Выносл.", callback_data="dice:выносливость"),
    )
    markup.row(
        InlineKeyboardButton("📖 Знание", callback_data="dice:знание"),
        InlineKeyboardButton("👁️ Восприятие", callback_data="dice:восприятие"),
    )
    return markup


# === ХЕЛПЕР СТАТУСА ===
def build_status(state):
    return (
        f"HP: {state['hp']}/{state['max_hp']}, факел: {'есть' if state['has_torch'] else 'нет'}, "
        f"ранен: {'да' if state['is_wounded'] else 'нет'}, шагов: {state['steps']}."
    )


# === ПРОМПТ МАСТЕРА ===
SYSTEM_PROMPT = (
    "Ты - Dungeon Master мрачного фэнтези. Веди сюжет к ключевым точкам, "
    "но не лишай игрока свободы. Используй принцип 'Да, но...' или 'Нет, и...'. "
    "Каждое случайное событие должно быть связано с глобальным лором. "
    "Пиши атмосферно, на русском, без списков и маркеров. Только живой текст. "
    "Используй факты из памяти и НАВЫКИ героя для поддержания непрерывности мира. "
    "Если игроку был показан результат броска кубика, учитывай его в описании: "
    "успех — действие удалось, неудача — действие провалилось с последствиями."
)


# === ГЕНЕРАЦИЯ СЦЕНЫ ===
def generate_scene(state):
    memory = build_memory_context(state)
    status = build_status(state)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Контекст памяти:\n{memory}"},
        {"role": "user", "content": f"Опиши сцену в 2-3 предложениях. Контекст героя: {status}"}
    ]
    try:
        scene_text = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7
        ).choices[0].message.content.strip()
        add_to_history(state, "assistant", scene_text)
        return scene_text
    except Exception as e:
        return f"Тьма сгущается... (ошибка: {e})"


# === СВОБОДНЫЙ РАЗГОВОР С ИИ ===
def chat_with_ai(user_text, state):
    memory = build_memory_context(state)
    status = build_status(state)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Контекст памяти:\n{memory}"}
    ]
    for entry in state["chat_history"]:
        messages.append({"role": entry["role"], "content": entry["content"]})
    user_msg = f"Игрок делает: {user_text}\nКонтекст героя: {status}"
    messages.append({"role": "user", "content": user_msg})

    try:
        reply = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=800,
            temperature=0.8
        ).choices[0].message.content.strip()
        add_to_history(state, "user", user_text)
        add_to_history(state, "assistant", reply)
        state["turn_count"] += 1
        maybe_summarize(state, client, MODEL)
        return reply
    except Exception as e:
        return f"Голос подземелья молчит... (ошибка: {e})"


# ============================================================
#  ОБРАБОТЧИКИ: /start
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    state = reset_state(chat_id)
    player_state[chat_id] = state

    text = (
        "Добро пожаловать в мрачные руины!\n\n"
        "Выбери свой путь — от него зависят навыки, оружие и стиль боя:"
    )
    send_long_message(chat_id, text, reply_markup=class_keyboard())
    save_chat(chat_id)


# ============================================================
#  ВЫБОР КЛАССА (callback)
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("cls:"))
def handle_class_choice(call):
    chat_id = call.message.chat.id
    class_key = call.data.split(":")[1]

    if class_key not in CLASSES:
        bot.answer_callback_query(call.id, "Ошибка выбора класса.", show_alert=True)
        return

    cls = CLASSES[class_key]
    state = get_state(chat_id)

    state["class_name"] = class_key
    state["skills"] = CLASS_STATS[class_key].copy()
    state["skill_points_remaining"] = 5
    state["inventory"] = cls["equipment"].copy() + [cls["weapon"]]
    state["has_torch"] = False

    reply = (
        f"{cls['emoji']} Ты выбрал: {cls['name']}\n\n"
        f"Статы: {', '.join([f'{k}: {v}' for k, v in state['skills'].items()])}\n"
        f"Очки прокачки: {state['skill_points_remaining']}\n"
        f"Снаряжение: {', '.join(state['inventory'])}\n\n"
        "Используй /прокачка сила +2 и т.п. для распределения очков.\n"
        "Когда закончишь — просто действуй: «иду вперёд», «осматриваю комнату»."
    )

    try:
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=reply)
    except:
        send_long_message(chat_id, reply)

    save_chat(chat_id)


# ============================================================
#  КНОПКА КУБИКА (callback)
#  --- Теперь обрабатывает и ручной бросок, и бросок с действием ---
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("dice:"))
def handle_dice_button(call):
    chat_id = call.message.chat.id
    state = get_state(chat_id)
    param = call.data.split(":")[1] if len(call.data.split(":")) > 1 else "roll"

    roll = roll_d20()

    # --- Если есть отложенное действие игрока — обрабатываем его ---
    pending = state.pop("pending_action", None)

    if pending:
        # Игрок выбрал навык для проверки действия
        stat_name = param if param != "roll" else "ловкость"
        stat_value = state["skills"].get(stat_name, 10)
        modifier = (stat_value - 10) // 2
        total = roll + modifier
        difficulty = 15

        success = total >= difficulty

        if success:
            roll_text = (
                f"🎲 Проверка: {stat_name}\n"
                f"Бросок: {roll} {'+' if modifier >= 0 else '-'} {abs(modifier)} = {total}\n"
                f"✅ Успех! (нужно было ≥{difficulty})"
            )
            modified_text = (
                f"{pending} "
                f"[Проверка {stat_name}: успех, бросок {total} vs сложность {difficulty}]"
            )
        else:
            roll_text = (
                f"🎲 Проверка: {stat_name}\n"
                f"Бросок: {roll} {'+' if modifier >= 0 else '-'} {abs(modifier)} = {total}\n"
                f"❌ Провал! (нужно было ≥{difficulty})"
            )
            modified_text = (
                f"{pending} "
                f"[Проверка {stat_name}: провал, бросок {total} vs сложность {difficulty}]"
            )

        bot.answer_callback_query(call.id)
        send_long_message(chat_id, roll_text)

        # Отправляем действие с результатом кубика в ИИ
        reply = chat_with_ai(modified_text, state)
        send_long_message(chat_id, reply)
        save_chat(chat_id)
        return

    # --- Обычный бросок кубика без действия ---
    if param == "roll":
        text = format_roll_result(roll, 0, roll, "🎲 Обычный бросок d20")
    else:
        stat_value = state["skills"].get(param, 10)
        modifier = (stat_value - 10) // 2
        total = roll + modifier
        text = format_roll_result(roll, modifier, total, f"🎲 Проверка: {param}")

    bot.answer_callback_query(call.id)
    send_long_message(chat_id, text, reply_markup=dice_keyboard())
    save_chat(chat_id)


# ============================================================
#  КНОПКА АТАКИ (callback)
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("atk:"))
def handle_attack_button(call):
    chat_id = call.message.chat.id
    state = get_state(chat_id)
    atk_key = call.data.split(":")[1]

    result = player_combat_round(state, "attack", atk_key)
    save_chat(chat_id)

    if not result["combat_ended"]:
        narrative = generate_narrative(state, client, MODEL)
        result["text"] += f"\n\n✨ {narrative}"

    bot.answer_callback_query(call.id)

    if result["combat_ended"]:
        bot.edit_message_text(result["text"], chat_id, call.message.message_id)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⚔️ Новый бой", callback_data="cmb:newfight"))
        bot.send_message(chat_id, "Что будешь делать дальше?", reply_markup=kb)
    else:
        kb = get_combat_keyboard(state)
        bot.edit_message_text(result["text"], chat_id, call.message.message_id, reply_markup=kb)


# ============================================================
#  КНОПКА БОЕВЫХ ДЕЙСТВИЙ (callback)
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("cmb:"))
def handle_combat_action(call):
    chat_id = call.message.chat.id
    state = get_state(chat_id)
    action = call.data.split(":")[1]

    if action == "newfight":
        intro = start_combat(state)
        save_chat(chat_id)
        kb = get_combat_keyboard(state)
        bot.edit_message_text(intro, chat_id, call.message.message_id, reply_markup=kb)
        return

    action_map = {"retreat": "retreat", "escape": "escape", "potion": "potion"}
    if action not in action_map:
        bot.answer_callback_query(call.id, "Неизвестное действие.")
        return

    result = player_combat_round(state, action_map[action])
    save_chat(chat_id)

    if not result["combat_ended"]:
        narrative = generate_narrative(state, client, MODEL)
        result["text"] += f"\n\n✨ {narrative}"

    bot.answer_callback_query(call.id)

    if result["combat_ended"]:
        bot.edit_message_text(result["text"], chat_id, call.message.message_id)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⚔️ Новый бой", callback_data="cmb:newfight"))
        bot.send_message(chat_id, "Что будешь делать дальше?", reply_markup=kb)
    else:
        kb = get_combat_keyboard(state)
        bot.edit_message_text(result["text"], chat_id, call.message.message_id, reply_markup=kb)


# ============================================================
#  /прокачка
# ============================================================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("/прокачка "))
def upgrade_skill(message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    parts = message.text.lower().replace("/прокачка ", "").split()

    if len(parts) < 2:
        send_long_message(chat_id, "Формат: /прокачка <навык> <изменение>, например: /прокачка сила +2")
        return

    skill = parts[0]
    change_str = parts[1]

    if skill not in state["skills"]:
        send_long_message(chat_id, f"Неверный навык. Доступные: {', '.join(state['skills'].keys())}")
        return

    try:
        change = int(change_str)
    except ValueError:
        send_long_message(chat_id, "Изменение должно быть числом, например +2 или -1.")
        return

    current = state["skills"][skill]
    new_val = current + change

    if new_val < 6:
        send_long_message(chat_id, f"Навык нельзя опустить ниже 6. Сейчас: {current}.")
        return

    cost = abs(change)
    if change > 0 and cost > state["skill_points_remaining"]:
        send_long_message(chat_id, f"Не хватает очков. Осталось: {state['skill_points_remaining']}")
        return

    if change > 0:
        state["skill_points_remaining"] -= cost

    state["skills"][skill] = new_val

    reply = (
        f"{skill} изменён: {current} → {new_val}\n"
        f"Осталось очков: {state['skill_points_remaining']}\n\n"
        f"Текущие навыки: {', '.join([f'{k}: {v}' for k, v in state['skills'].items()])}"
    )

    if state["skill_points_remaining"] == 0:
        reply += "\n\n✨ Очки распределены! Ты чувствуешь, как силы наполняют тебя…\n\n"
        scene = generate_scene(state)
        reply += scene
        send_long_message(chat_id, reply)
    else:
        send_long_message(chat_id, reply)

    save_chat(chat_id)


# ============================================================
#  ТЕКСТОВЫЕ КОМАНДЫ И СВОБОДНЫЙ ВВОД
# ============================================================
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    text = message.text.lower().strip()

    # --- КУБИК (просто бросок, без действия) ---
    if text in ("кубик", "d20", "dice", "/кубик"):
        send_long_message(chat_id, "Выбери бросок:", reply_markup=dice_keyboard())
        return

    # --- АТАКА / БОЙ ---
    if text in ("атака", "/атака", "атаковать", "бой", "/бой", "fight"):
        if is_combat_active(state):
            kb = get_combat_keyboard(state)
            if kb:
                send_long_message(chat_id, "Выбери атаку:", reply_markup=kb)
            else:
                send_long_message(chat_id, "Сначала выбери класс через /start")
        else:
            intro = start_combat(state)
            save_chat(chat_id)
            kb = get_combat_keyboard(state)
            send_long_message(chat_id, intro, reply_markup=kb)
        return

    # --- ВПЕРЁД ---
    if text == "вперёд":
        state["steps"] += 1
        roll = random.randint(1, 20)
        event = ""
        if roll <= 5:
            state["hp"] -= 1
            state["is_wounded"] = True
            event = "Что-то пошло не так… Ты оступился и ударился."
        elif roll >= 18:
            if state["hp"] < state["max_hp"]:
                state["hp"] += 1
                state["is_wounded"] = False
            event = "Удача на твоей стороне! Ты ловко перепрыгнул опасную трещину."
        scene = generate_scene(state)
        reply = scene
        if event:
            reply += f"\n{event}"
        reply += f"\nHP: {state['hp']}/{state['max_hp']}"
        send_long_message(chat_id, reply)
        save_chat(chat_id)
        return

    # --- ФАКЕЛ ---
    if text in ("факел", "свет", "зажечь факел"):
        if not state["has_torch"]:
            state["has_torch"] = True
            if "world_facts" not in state:
                state["world_facts"] = {}
            state["world_facts"]["Факел_зажжён"] = "Факел горит ровным пламенем, освещая 5 метров вокруг."
            send_long_message(chat_id, "Ты зажёг факел огнивом. Пламя разгорается, разгоняя тьму.")
        else:
            send_long_message(chat_id, "Факел уже горит.")
        save_chat(chat_id)
        return

    # --- ПАМЯТЬ ---
    if text == "память":
        summary = state.get("story_summary", "(пока пусто)")
        facts = "\n".join([f"  {k}: {v}" for k, v in state.get("world_facts", {}).items()])
        if not facts:
            facts = "(пока пусто)"
        events = " | ".join(state.get("world_log", [])[-8:])
        if not events:
            events = "(пока пусто)"
        skills_str = ", ".join([f"{k}: {v}" for k, v in state.get("skills", {}).items()])
        class_name = state.get("class_name", "не выбран")
        points = state.get("skill_points_remaining", 0)
        inv = ", ".join(state.get("inventory", []))

        send_long_message(chat_id,
            f"=== ПАМЯТЬ МАСТЕРА ===\n\n"
            f"Класс: {class_name}\n"
            f"Очки прокачки: {points}\n"
            f"Навыки: {skills_str}\n"
            f"Снаряжение: {inv}\n\n"
            f"Сводка сюжета:\n{summary}\n\n"
            f"Факты мира:\n{facts}\n\n"
            f"События:\n{events}\n\n"
            f"Ход: {state.get('turn_count', 0)}"
        )
        save_chat(chat_id)
        return

    # --- СНАРЯЖЕНИЕ ---
    if text in ("снаряжение", "инвентарь", "рюкзак"):
        inv = state.get("inventory", [])
        if not inv:
            send_long_message(chat_id, "Рюкзак пуст.")
        else:
            send_long_message(chat_id, "🎒 Снаряжение:\n" + "\n".join([f"• {item}" for item in inv]))
        save_chat(chat_id)
        return

    # --- СВОБОДНОЕ ДЕЙСТВИЕ: просим игрока кинуть кубик ---
    # Сохраняем текст действия и показываем кнопки кубика
    state["pending_action"] = message.text
    save_chat(chat_id)

    send_long_message(
        chat_id,
        f"🎲 Твоё действие: \"{message.text}\"\n"
        f"Выбери навык для проверки кубиком:",
        reply_markup=dice_keyboard()
    )


print("Бот запущен и готов к приключениям!")
bot.polling(none_stop=True)
    
