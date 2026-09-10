import random
from config import bot, client
from combat import CLASSES, perform_attack
from game import build_status, generate_scene, chat_with_ai
from inventory import init_inventory, get_inventory_text
from dice import check_action, format_roll_result, roll_d20
from memory import load_state, save_state, reset_state

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============================================================
#  СОСТОЯНИЕ ИГРОКОВ
# ============================================================
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

# ============================================================
#  ОТПРАВКА
# ============================================================
def send_long_message(chat_id, text, reply_markup=None):
    limit = 4000
    if len(text) <= limit:
        bot.send_message(chat_id, text, reply_markup=reply_markup)
        return
    for i in range(0, len(text), limit):
        chunk = text[i:i+limit]
        bot.send_message(chat_id, chunk, reply_markup=reply_markup if i == 0 else None)

# ============================================================
#  КЛАВИАТУРЫ
# ============================================================

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

def attack_keyboard(state):
    class_key = state.get("class_key", "")
    cls = CLASSES.get(class_key)
    if not cls:
        return None
    markup = InlineKeyboardMarkup()
    for atk_key, atk in cls["attacks"].items():
        markup.add(InlineKeyboardButton(
            atk["name"],
            callback_data=f"atk:{atk_key}"
        ))
    return markup

# ============================================================
#  /start
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

    state["class_key"] = class_key
    state["class_name"] = cls["name"]
    state["skills"] = cls["stats"].copy()
    state["skill_points_remaining"] = 5
    init_inventory(state, class_key, cls)

    reply = (
        f"{cls['emoji']} Ты выбрал: {cls['name']}\n\n"
        f"Статы: {', '.join([f'{k}: {v}' for k, v in cls['stats'].items()])}\n"
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

    if skill not in state.get("skills", {}):
        send_long_message(chat_id, f"Неверный навык. Доступные: {', '.join(state.get('skills', {}).keys())}")
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
        atk_kb = attack_keyboard(state)
        send_long_message(chat_id, reply, reply_markup=atk_kb)
    else:
        send_long_message(chat_id, reply)

    save_chat(chat_id)

# ============================================================
#  КНОПКА КУБИКА (callback)
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("dice:"))
def handle_dice_button(call):
    chat_id = call.message.chat.id
    state = get_state(chat_id)
    param = call.data.split(":")[1] if len(call.data.split(":")) > 1 else "roll"

    if param == "roll":
        result = roll_d20(state, "обычный")
    else:
        result = roll_d20(state, param)

    text = format_roll_result(result)
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

    attack_text, result = perform_attack(state, atk_key)
    modified = f"Атака: {atk_key}. {attack_text}"
    ai_reply = chat_with_ai(modified, state)

    full_reply = f"{attack_text}\n\n{ai_reply}"
    bot.answer_callback_query(call.id)
    send_long_message(chat_id, full_reply, reply_markup=attack_keyboard(state))
    save_chat(chat_id)

# ============================================================
#  ТЕКСТОВЫЕ КОМАНДЫ И СВОБОДНЫЙ ВВОД
# ============================================================
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    text = message.text.lower().strip()

    if text in ("кубик", "d20", "dice", "/кубик"):
        send_long_message(chat_id, "Выбери бросок:", reply_markup=dice_keyboard())
        return

    if text in ("атака", "/атака", "атаковать"):
        kb = attack_keyboard(state)
        if kb:
            send_long_message(chat_id, "Выбери атаку:", reply_markup=kb)
        else:
            send_long_message(chat_id, "Сначала выбери класс через /start")
        return

    if text == "вперёд":
        state["steps"] = state.get("steps", 0) + 1
        roll = random.randint(1, 20)
        event = ""
        if roll <= 5:
            state["hp"] = state.get("hp", 10) - 1
            state["is_wounded"] = True
            event = "Что-то пошло не так… Ты оступился и ударился."
        elif roll >= 18:
            if state["hp"] < state["max_hp"]:
                state["hp"] += 1
                state["is_wounded"] = False
            event = "Удача! Ты ловко перепрыгнул опасную трещину."
        scene = generate_scene(state)
        reply = scene
        if event:
            reply += f"\n{event}"
        reply += f"\nHP: {state['hp']}/{state['max_hp']}"
        send_long_message(chat_id, reply)
        save_chat(chat_id)
        return

    if text in ("факел", "свет", "зажечь факел"):
        if not state.get("has_torch"):
            state["has_torch"] = True
            if "world_facts" not in state:
                state["world_facts"] = {}
            state["world_facts"]["Факел_зажжён"] = "Факел горит ровным пламенем, освещая 5 метров вокруг."
            send_long_message(chat_id, "Ты зажёг факел огнивом. Пламя разгорается, разгоняя тьму.")
        else:
            send_long_message(chat_id, "Факел уже горит.")
        save_chat(chat_id)
        return

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

    if text in ("снаряжение", "инвентарь", "рюкзак"):
        send_long_message(chat_id, get_inventory_text(state))
        save_chat(chat_id)
        return

    # --- ОБЫЧНЫЙ ХОД С АВТОПРОВЕРКОЙ КУБИКА ---
    result = check_action(message.text, state, client)
    if result is not None:
        roll_text = format_roll_result(result)
        modified_text = (
            f"{message.text} "
            f"[Бросок: {result['total']} vs сложность {result['difficulty']} — "
            f"{result['result_type']}. {result['reason']}]"
        )
        reply = chat_with_ai(modified_text, state)
        send_long_message(chat_id, roll_text + "\n\n" + reply)
    else:
        reply = chat_with_ai(message.text, state)
        send_long_message(chat_id, reply)
    save_chat(chat_id)
  
