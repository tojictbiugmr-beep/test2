import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============================================================
#  КОНСТАНТЫ БОЯ
# ============================================================
HIT_CHANCE_PLAYER = 95
HIT_CHANCE_ENEMY  = 85
ESCAPE_CHANCE     = 50
POTION_STACK_MAX  = 5
POTION_HEAL_DICE  = 6
LOOT_CHANCE       = 40

# ============================================================
#  КЛАССЫ: атаки, снаряжение
#  Статы берутся из memory.CLASS_STATS, здесь только боевое.
# ============================================================
CLASSES = {
    "воин": {
        "name": "Воин",
        "emoji": "🗡️",
        "main_stat": "сила",
        "weapon": "Двуручный меч",
        "equipment": ["Факел", "Огниво"],
        "can_retreat": False,
        "attacks": {
            "удар": {
                "name": "Мощный удар",
                "dice": 8,
                "distance_req": "close",
                "desc": "обрушивает двуручный меч на врага",
                "proc_chance": 0,
                "proc_type": None,
            },
            "размах": {
                "name": "Широкий размах",
                "dice": 6,
                "distance_req": "close",
                "desc": "бьёт по врагам в радиусе удара",
                "proc_chance": 30,
                "proc_type": "multi_target",
            },
            "бросок": {
                "name": "Бросок вперёд",
                "dice": 8,
                "distance_req": "not_close",
                "damage_mult": 0.65,
                "closes_distance": True,
                "desc": "бросается навстречу врагу",
                "proc_chance": 0,
                "proc_type": None,
            },
        },
    },
    "маг": {
        "name": "Маг",
        "emoji": "🔥",
        "main_stat": "знание",
        "weapon": "Посох",
        "equipment": ["Факел", "Огниво"],
        "can_retreat": True,
        "attacks": {
            "шар": {
                "name": "Огненный шар",
                "dice": 6,
                "distance_req": "any",
                "desc": "выпускает сгусток пламени в цель",
                "proc_chance": 0,
                "proc_type": None,
            },
            "оковы": {
                "name": "Массовые оковы",
                "dice": 4,
                "distance_req": "any",
                "targets": "all",
                "desc": "сковывает врагов магическими цепями",
                "proc_chance": 30,
                "proc_type": "freeze",
            },
        },
    },
    "разбойник": {
        "name": "Следопыт",
        "emoji": "🏹",
        "main_stat": "ловкость",
        "weapon": "Кинжал и лук",
        "equipment": ["Факел", "Огниво"],
        "can_retreat": True,
        "attacks": {
            "выстрел": {
                "name": "Точный выстрел",
                "dice": 6,
                "distance_req": "any",
                "desc": "пускает стрелу из лука в цель",
                "proc_chance": 30,
                "proc_type": "second_shot",
            },
            "кинжал": {
                "name": "Удар кинжалом",
                "dice": 4,
                "distance_req": "close",
                "desc": "наносит быстрый удар кинжалом",
                "proc_chance": 0,
                "proc_type": None,
            },
            "скрытность": {
                "name": "Скрытая атака",
                "dice": 8,
                "distance_req": "close",
                "desc": "бьёт из тени, пока враг не видит",
                "proc_chance": 30,
                "proc_type": "stealth",
            },
        },
    },
}

# ============================================================
#  ВРАГИ
# ============================================================
ENEMIES = {
    "гоблин": {"name": "Гоблин", "hp": 8, "damage_dice": 4, "damage_mod": 1, "initiative_mod": 3, "emoji": "👺"},
    "орк": {"name": "Орк", "hp": 16, "damage_dice": 8, "damage_mod": 2, "initiative_mod": -1, "emoji": "👹"},
    "скелет": {"name": "Скелет", "hp": 10, "damage_dice": 6, "damage_mod": 0, "initiative_mod": 0, "emoji": "💀"},
    "волк": {"name": "Свирепый волк", "hp": 6, "damage_dice": 4, "damage_mod": 1, "initiative_mod": 2, "emoji": "🐺"},
    "разбойник": {"name": "Разбойник", "hp": 12, "damage_dice": 6, "damage_mod": 1, "initiative_mod": 1, "emoji": "🗡️"},
}

# ============================================================
#  УТИЛИТЫ
# ============================================================
def get_modifier(stat_value):
    return (stat_value - 10) // 2

def get_class_modifier(state):
    cls = CLASSES.get(state.get("class_name", ""))
    if not cls:
        return 0
    return get_modifier(state.get("skills", {}).get(cls["main_stat"], 10))

def roll_damage(dice_size, modifier):
    return random.randint(1, dice_size) + modifier

def chance(percent):
    return random.randint(1, 100) <= percent

def distance_name(distance):
    if distance >= 3:
        return "дальняя"
    elif distance == 2:
        return "средняя-дальняя"
    elif distance == 1:
        return "средняя"
    return "ближняя"

# ============================================================
#  БАЛАНС ВРАГОВ
# ============================================================
def generate_enemies(state):
    hp = state.get("hp", 10)
    max_hp = state.get("max_hp", 10)
    wounded = state.get("is_wounded", False)
    has_torch = state.get("has_torch", False)

    count = 1
    if hp > max_hp * 0.8:
        count += 1
    if has_torch:
        count += 1
    if wounded:
        count -= 1
    count = max(1, min(4, count))

    pool = list(ENEMIES.keys())
    return [random.choice(pool) for _ in range(count)]

# ============================================================
#  УПРАВЛЕНИЕ БОЕМ
# ============================================================
def start_combat(state, enemy_types=None):
    if enemy_types is None:
        enemy_types = generate_enemies(state)

    enemies = []
    name_counts = {}
    for etype in enemy_types:
        tmpl = ENEMIES.get(etype)
        if not tmpl:
            continue
        name_counts[etype] = name_counts.get(etype, 0) + 1
        display_name = tmpl["name"]
        if name_counts[etype] > 1:
            display_name = f"{tmpl['name']} {name_counts[etype]}"
        enemies.append({
            "type": etype, "name": display_name,
            "hp": tmpl["hp"], "max_hp": tmpl["hp"],
            "damage_dice": tmpl["damage_dice"], "damage_mod": tmpl["damage_mod"],
            "initiative_mod": tmpl["initiative_mod"], "emoji": tmpl["emoji"],
        })

    dex_mod = get_modifier(state.get("skills", {}).get("ловкость", 10))
    player_init = random.randint(1, 20) + dex_mod
    enemy_init = max(random.randint(1, 20) + e["initiative_mod"] for e in enemies) if enemies else 0
    goes_first = "player" if player_init >= enemy_init else "enemy"

    state["combat"] = {
        "active": True, "enemies": enemies,
        "distance": 3, "turn": 1,
        "initiative": goes_first,
        "frozen": False, "player_hidden": False,
    }

    enemy_list = ", ".join([f"{e['emoji']} {e['name']}" for e in enemies])
    init_str = "ты ходишь первым" if goes_first == "player" else "враги ходят первыми"
    return (
        f"⚔️ Бой начинается!\n\n"
        f"Враги: {enemy_list}\n"
        f"Инициатива: {init_str}\n"
        f"Дистанция: {distance_name(3)}\n\n"
        f"{get_combat_status(state)}"
    )

def is_combat_active(state):
    return state.get("combat", {}).get("active", False)

def check_combat_end(state):
    if not is_combat_active(state):
        return None
    if all(e["hp"] <= 0 for e in state["combat"]["enemies"]):
        return "victory"
    if state.get("hp", 0) <= 0:
        return "defeat"
    return None

def end_combat(state, result):
    combat = state.get("combat", {})
    combat["active"] = False
    combat["result"] = result
    if result == "victory":
        loot = get_loot()
        for item in loot:
            inv = state.setdefault("inventory", [])
            if item == "Зелье лечения":
                if inv.count("Зелье лечения") < POTION_STACK_MAX:
                    inv.append("Зелье лечения")
        return loot
    elif result == "defeat":
        state["is_wounded"] = True
    return None

def get_loot():
    return ["Зелье лечения"] if chance(LOOT_CHANCE) else []

# ============================================================
#  ДЕЙСТВИЯ ИГРОКА
# ============================================================
def player_attack(state, atk_key):
    combat = state.get("combat", {})
    if not combat.get("active"):
        return "Бой не идёт.", None

    cls = CLASSES.get(state.get("class_name", ""))
    if not cls or atk_key not in cls["attacks"]:
        return "Неизвестная атака.", None

    atk = cls["attacks"][atk_key]
    distance = combat["distance"]
    alive = [e for e in combat["enemies"] if e["hp"] > 0]
    if not alive:
        return "Врагов нет.", None

    req = atk.get("distance_req", "any")
    if req == "close" and distance > 0:
        return f"{atk['name']} — слишком далеко! Нужно приблизиться.", None
    if req == "not_close" and distance == 0:
        return f"{atk['name']} — ты уже в ближнем бою!", None

    if chance(100 - HIT_CHANCE_PLAYER):
        return f"⚔️ {atk['name']}\n\n❌ Промах!", None

    mod = get_class_modifier(state)
    damage_mult = atk.get("damage_mult", 1.0)
    base = roll_damage(atk["dice"], mod)
    damage = int(base * damage_mult)

    if atk.get("closes_distance"):
        combat["distance"] = 0

    proc_text = ""
    if atk.get("targets") == "all":
        targets = list(alive)
    else:
        targets = [alive[0]]

    if atk.get("proc_type") == "multi_target" and chance(atk["proc_chance"]):
        n = random.randint(1, min(3, len(alive)))
        targets = alive[:n]
        proc_text = f"⚡ Прок! Поражено целей: {len(targets)}."

    lines = []
    for t in targets:
        if t["type"] == "скелет" and chance(10):
            lines.append(f"  {t['name']}: 0 (игнор урона!)")
            continue
        t["hp"] -= damage
        lines.append(f"  {t['name']}: -{damage} (HP: {max(0, t['hp'])}/{t['max_hp']})")

    if atk.get("proc_type") == "second_shot" and chance(atk["proc_chance"]):
        extra = roll_damage(atk["dice"], mod)
        tgt = targets[0]
        if tgt["type"] == "скелет" and chance(10):
            proc_text = "⚡ Прок! Вторая стрела — скелет игнорирует урон."
        else:
            tgt["hp"] -= extra
            proc_text = f"⚡ Прок! Вторая стрела: +{extra} урона по {tgt['name']}."

    if atk.get("proc_type") == "stealth" and chance(atk["proc_chance"]):
        combat["player_hidden"] = True
        proc_text = "⚡ Прок! Ты остался незамеченным — враги не атакуют в этот ход."

    if atk.get("proc_type") == "freeze" and chance(atk["proc_chance"]):
        combat["frozen"] = True
        proc_text = "⚡ Прок! Враги скованы — не могут приблизиться!"

    text = f"⚔️ {atk['name']}\n\nУрон: {damage}"
    if damage_mult < 1.0:
        text += f" (базовый {base} × {damage_mult})"
    text += "\n"
    for ln in lines:
        text += ln + "\n"
    if proc_text:
        text += proc_text + "\n"
    text += f"\n{get_combat_status(state)}"
    return text, {"damage": damage}

def player_retreat(state):
    combat = state.get("combat", {})
    if not combat.get("active"):
        return "Бой не идёт.", None

    cls = CLASSES.get(state.get("class_name", ""))
    if not cls or not cls.get("can_retreat"):
        return "Твой класс не может отступать с атакой.", None

    distance = combat["distance"]
    if distance >= 3:
        return "Уже на максимальной дистанции.", None

    combat["distance"] += 1
    text = f"🏃 Ты отступаешь. Дистанция: {distance_name(combat['distance'])}.\n"

    if chance(30):
        mod = get_class_modifier(state)
        atk_key = "шар" if state["class_name"] == "маг" else "выстрел"
        atk = cls["attacks"][atk_key]
        if chance(100 - HIT_CHANCE_PLAYER):
            text += "Атака при отходе — промах!"
        else:
            dmg = roll_damage(atk["dice"], mod)
            alive = [e for e in combat["enemies"] if e["hp"] > 0]
            if alive:
                t = alive[0]
                if t["type"] == "скелет" and chance(10):
                    text += f"Атака при отходе: {t['name']} игнорирует урон!"
                else:
                    t["hp"] -= dmg
                    text += f"Атака при отходе: {t['name']} -{dmg} (HP: {max(0, t['hp'])}/{t['max_hp']})"
    else:
        text += "Атака при отходе не получилась."

    text += f"\n\n{get_combat_status(state)}"
    return text, None

def player_escape(state):
    if not is_combat_active(state):
        return "Бой не идёт.", False
    if chance(ESCAPE_CHANCE):
        end_combat(state, "escape")
        return "🏃 Ты успешно сбежал из боя!", True
    return "❌ Побег не удался! Враги атакуют.", False

def use_potion_in_combat(state):
    if not is_combat_active(state):
        return "Бой не идёт.", None
    inv = state.get("inventory", [])
    if "Зелье лечения" not in inv:
        return "У тебя нет зелья лечения.", None

    heal = random.randint(1, POTION_HEAL_DICE)
    state["hp"] = min(state.get("max_hp", 20), state.get("hp", 0) + heal)
    inv.remove("Зелье лечения")
    if state["hp"] >= state.get("max_hp", 0):
        state["is_wounded"] = False

    return (
        f"🧪 Ты выпиваешь зелье. Восстановлено: {heal} HP.\n"
        f"HP: {state['hp']}/{state['max_hp']}\n"
        f"Ход потрачен — враги атакуют."
    ), heal

# ============================================================
#  ХОД ВРАГОВ
# ============================================================
def enemy_turn(state):
    combat = state.get("combat", {})
    if not combat.get("active"):
        return ""

    alive = [e for e in combat["enemies"] if e["hp"] > 0]
    if not alive:
        return ""

    if combat.get("player_hidden"):
        combat["player_hidden"] = False
        return "👁️ Враги не замечают тебя и топчутся на месте."

    frozen = combat.get("frozen", False)
    combat["frozen"] = False

    text = ""
    if frozen:
        text += "❄️ Враги скованы оковами и не могут двигаться.\n"

    if not frozen and combat["distance"] > 0:
        combat["distance"] -= 1
        text += f"Враги приближаются. Дистанция: {distance_name(combat['distance'])}.\n"

    attacks = []
    for e in alive:
        can_attack = False
        if combat["distance"] == 0:
            can_attack = True
        elif combat["distance"] == 1 and e["type"] == "разбойник":
            can_attack = True

        if not can_attack:
            continue

        if chance(100 - HIT_CHANCE_ENEMY):
            attacks.append(f"  {e['name']} промахивается!")
            continue

        dmg = roll_damage(e["damage_dice"], e["damage_mod"])
        if e["type"] == "волк" and chance(5):
            dmg += roll_damage(e["damage_dice"], e["damage_mod"])
            attacks.append(f"  {e['name']} двойная атака! -{dmg} HP")
        else:
            attacks.append(f"  {e['name']} наносит {dmg} урона")

        state["hp"] = max(0, state.get("hp", 0) - dmg)
        if state["hp"] < state.get("max_hp", 0):
            state["is_wounded"] = True

    if attacks:
        text += "Атаки врагов:\n" + "\n".join(attacks)
    elif combat["distance"] > 0:
        text += "Враги приближаются, но пока не могут атаковать."

    text += f"\n\n{get_combat_status(state)}"
    return text

# ============================================================
#  ПОЛНЫЙ БОЕВОЙ РАУНД
# ============================================================
def player_combat_round(state, action_type, action_key=None):
    result = {"text": "", "combat_ended": False, "result_type": None, "loot": []}

    if action_type == "attack":
        p_text, _ = player_attack(state, action_key)
    elif action_type == "retreat":
        p_text, _ = player_retreat(state)
    elif action_type == "escape":
        p_text, escaped = player_escape(state)
        if escaped:
            result["text"] = p_text
            result["combat_ended"] = True
            result["result_type"] = "escape"
            return result
    elif action_type == "potion":
        p_text, _ = use_potion_in_combat(state)
    else:
        result["text"] = "Неизвестное действие."
        return result

    result["text"] = p_text

    end = check_combat_end(state)
    if end == "victory":
        loot = end_combat(state, "victory")
        result["loot"] = loot
        result["combat_ended"] = True
        result["result_type"] = "victory"
        if loot:
            result["text"] += f"\n\n📦 Награда: {', '.join(loot)}"
        else:
            result["text"] += "\n\nВраги повержены, но добычи нет."
        return result

    if end == "defeat":
        end_combat(state, "defeat")
        result["combat_ended"] = True
        result["result_type"] = "defeat"
        result["text"] += "\n\n💀 Ты потерял сознание..."
        return result

    if state.get("combat", {}).get("player_hidden"):
        state["combat"]["player_hidden"] = False
        e_text = ""
    else:
        e_text = enemy_turn(state)

    if e_text:
        result["text"] += "\n\n" + e_text

    end = check_combat_end(state)
    if end == "defeat":
        end_combat(state, "defeat")
        result["combat_ended"] = True
        result["result_type"] = "defeat"
        result["text"] += "\n\n💀 Ты потерял сознание..."
        return result

    state["combat"]["turn"] += 1
    return result

# ============================================================
#  UI: СТАТУС, КЛАВИАТУРА, КОНТЕКСТ ДЛЯ ИИ
# ============================================================
def get_combat_status(state):
    combat = state.get("combat", {})
    if not combat.get("active"):
        return ""

    alive = [e for e in combat["enemies"] if e["hp"] > 0]
    dead = [e for e in combat["enemies"] if e["hp"] <= 0]

    lines = ["=== БОЙ ==="]
    lines.append(f"Ход: {combat['turn']} | Дистанция: {distance_name(combat['distance'])}")
    init = "твоя" if combat["initiative"] == "player" else "врагов"
    lines.append(f"Инициатива: {init}")
    if alive:
        lines.append("Враги:")
        for e in alive:
            lines.append(f"  {e['emoji']} {e['name']}: {e['hp']}/{e['max_hp']} HP")
    if dead:
        lines.append("Повержены: " + ", ".join([e["name"] for e in dead]))
    lines.append(f"HP героя: {state.get('hp', 0)}/{state.get('max_hp', 0)}")

    potions = state.get("inventory", []).count("Зелье лечения")
    if potions > 0:
        lines.append(f"🧪 Зелья: {potions}/{POTION_STACK_MAX}")
    return "\n".join(lines)

def get_combat_keyboard(state):
    combat = state.get("combat", {})
    if not combat.get("active"):
        return None

    cls = CLASSES.get(state.get("class_name", ""))
    if not cls:
        return None

    distance = combat["distance"]
    markup = InlineKeyboardMarkup()

    for atk_key, atk in cls["attacks"].items():
        req = atk.get("distance_req", "any")
        if req == "close" and distance > 0:
            continue
        if req == "not_close" and distance == 0:
            continue
        markup.add(InlineKeyboardButton(atk["name"], callback_data=f"atk:{atk_key}"))

    if cls.get("can_retreat") and distance < 3:
        markup.add(InlineKeyboardButton("🏃 Отступить", callback_data="cmb:retreat"))

    markup.add(InlineKeyboardButton("🚪 Побег (50/50)", callback_data="cmb:escape"))

    potions = state.get("inventory", []).count("Зелье лечения")
    if potions > 0:
        markup.add(InlineKeyboardButton(f"🧪 Зелье ({potions})", callback_data="cmb:potion"))

    return markup

def get_ai_combat_context(state):
    combat = state.get("combat", {})
    if not combat.get("active"):
        return ""

    alive = [e for e in combat["enemies"] if e["hp"] > 0]
    dead = [e for e in combat["enemies"] if e["hp"] <= 0]

    parts = [
        f"Бой активен. Ход {combat['turn']}.",
        f"Дистанция: {distance_name(combat['distance'])}.",
        f"Инициатива: {'игрок' if combat['initiative'] == 'player' else 'враги'}.",
    ]
    if alive:
        parts.append("Живые враги: " + ", ".join([f"{e['name']} ({e['hp']}/{e['max_hp']} HP)" for e in alive]))
    if dead:
        parts.append("Повержены: " + ", ".join([e["name"] for e in dead]))
    parts.append(f"HP героя: {state.get('hp', 0)}/{state.get('max_hp', 0)}.")
    parts.append(f"Класс: {state.get('class_name', '?')}.")
    return " ".join(parts)

def generate_narrative(state, client, model):
    context = get_ai_combat_context(state)
    if not context:
        return ""
    cls_name = state.get("class_name", "Герой")
    hp = state.get("hp", 0)
    max_hp = state.get("max_hp", 1)
    prompt = (
        "Ты — мастер подземелий. Опиши текущую сцену боя одним предложением (не более 15 слов). "
        f"Класс: {cls_name}. HP: {hp}/{max_hp}. {context} "
        "Ответ — только одно предложение на русском, без маркеров и пояснений."
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Отвечай только одним коротким предложением на русском."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=30,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Бой продолжается, враги наступают."
