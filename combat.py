import random
from dice import roll_d20, format_roll_result

# ============================================================
#  КЛАССЫ: базовые статы, снаряжение, атаки
#  → Добавить класс — допиши сюда.
#  → Добавить атаку — допиши в "attacks" класса.
# ============================================================
CLASSES = {
    "warrior": {
        "name": "Воин",
        "emoji": "🗡️",
        "stats": {"сила": 16, "выносливость": 14, "ловкость": 12, "знание": 8, "восприятие": 10},
        "weapon": "Двуручный меч",
        "equipment": ["Факел", "Огниво"],
        "attacks": {
            "удар": {"name": "Мощный удар", "type": "ближняя", "hits": 1, "desc": "обрушивает двуручный меч на врага"},
            "размах": {"name": "Широкий размах", "type": "ближняя", "hits": 3, "desc": "бьёт по всем врагам в радиусе удара"},
        },
    },
    "mage": {
        "name": "Маг",
        "emoji": "🔥",
        "stats": {"сила": 8, "выносливость": 10, "ловкость": 10, "знание": 16, "восприятие": 12},
        "weapon": "Посох",
        "equipment": ["Факел", "Огниво"],
        "attacks": {
            "шар": {"name": "Огненный шар", "type": "дальняя", "hits": 1, "desc": "выпускает сгусток пламени в цель"},
            "оковы": {"name": "Массовые оковы", "type": "дальняя", "hits": 5, "desc": "сковывает несколько целей магическими цепями"},
        },
    },
    "ranger": {
        "name": "Следопыт",
        "emoji": "🏹",
        "stats": {"сила": 12, "выносливость": 12, "ловкость": 16, "знание": 10, "восприятие": 14},
        "weapon": "Кинжал и лук",
        "equipment": ["Факел", "Огниво"],
        "attacks": {
            "выстрел": {"name": "Точный выстрел", "type": "дальняя", "hits": 1, "desc": "пускает стрелу из лука в цель"},
            "кинжал": {"name": "Удар кинжалом", "type": "ближняя", "hits": 1, "desc": "наносит быстрый удар кинжалом"},
            "скрытность": {"name": "Скрытая атака", "type": "ближняя", "hits": 1, "desc": "бьёт из тени, пока враг не видит"},
        },
    },
}


def perform_attack(state, atk_key):
    """Выполняет атаку по классу. Возвращает (текст, результат_кубика)."""
    class_key = state.get("class_key", "")
    cls = CLASSES.get(class_key)
    if not cls or atk_key not in cls["attacks"]:
        return "Неизвестная атака.", None

    atk = cls["attacks"][atk_key]

    if atk["type"] == "дальняя":
        skill = "ловкость" if class_key == "ranger" else "знание"
    elif atk_key == "скрытность":
        skill = "ловкость"
    else:
        skill = "сила" if class_key == "warrior" else "ловкость"

    result = roll_d20(state, skill)
    atk_desc = f"{cls['name']} {atk['desc']}."

    if result["result_type"] in ("КРИТИЧЕСКИЙ УСПЕХ", "УСПЕХ"):
        outcome = f"{atk_desc} Атака достигает цели!"
        if atk["hits"] > 1:
            outcome += f" Поражено целей: до {atk['hits']}."
    elif result["result_type"] == "ПОГРАНИЧНЫЙ РЕЗУЛЬТАТ":
        outcome = f"{atk_desc} Частичный успех — враг задет, но не полностью."
    else:
        outcome = f"{atk_desc} Атака прошла мимо или была отбита."

    roll_text = format_roll_result(result)
    full_text = f"⚔️ {atk['name']}\n\n{roll_text}\n\n{outcome}"
    return full_text, result
