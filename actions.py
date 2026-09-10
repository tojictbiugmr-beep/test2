import random

# ============================================================
#  УРОВНИ СЛОЖНОСТИ (D&D-стиль)
# ============================================================
DC_TRIVIAL   = 5    # проще простого
DC_EASY      = 8    # лёгкая задача
DC_MEDIUM    = 10   # средняя задача (по умолчанию)
DC_HARD      = 14   # сложная задача
DC_VERY_HARD = 18   # почти невозможно

# ============================================================
#  КЛЮЧЕВЫЕ СЛОВА ДЛЯ ОПРЕДЕЛЕНИЯ СЛОЖНОСТИ
#  (проверяются по порядку: сначала самые сложные)
# ============================================================
HARD_KEYWORDS = [
    "взломать", "взлом", "обойти ловушку", "обезвредить",
    "акробатика", "перепрыгнуть пропасть", "сложный трюк",
    "подобраться незаметно", "сразить одним ударом",
    "поднять тяжёлый", "сдвинуть тяжёлый",
]

MEDIUM_KEYWORDS = [
    "прыгнуть", "перепрыгнуть", "карабкаться", "влезть",
    "спуститься", "поднять", "толкнуть", "выломать",
    "искать", "поиск", "осмотреть внимательно", "прочесть",
    "сбить", "разбить",
]

EASY_KEYWORDS = [
    "осмотреть", "осмотреться", "прислушаться", "принюхаться",
    "прочитать", "открыть", "взять", "подобрать",
    "идти", "перейти", "заглянуть", "проверить",
]

TRIVIAL_KEYWORDS = [
    "постоять", "подождать", "посидеть", "отдохнуть",
    "посмотреть", "спросить",
]


def determine_difficulty(action_text):
    """Определяет сложность проверки по ключевым словам в действии."""
    text = action_text.lower()

    for kw in HARD_KEYWORDS:
        if kw in text:
            return DC_HARD

    for kw in MEDIUM_KEYWORDS:
        if kw in text:
            return DC_MEDIUM

    for kw in EASY_KEYWORDS:
        if kw in text:
            return DC_EASY

    for kw in TRIVIAL_KEYWORDS:
        if kw in text:
            return DC_TRIVIAL

    return DC_MEDIUM  # по умолчанию


# ============================================================
#  МОДИФИКАТОР
# ============================================================
def get_modifier(stat_value):
    return (stat_value - 10) // 2


# ============================================================
#  РАЗРЕШЕНИЕ ПРОВЕРКИ ДЕЙСТВИЯ
# ============================================================
def resolve_action(action_text, stat_name, state):
    """
    Бросок с проверкой для отложенного действия игрока.
    Возвращает словарь с полным результатом.
    """
    stat_value = state.get("skills", {}).get(stat_name, 10)
    modifier = get_modifier(stat_value)
    roll = random.randint(1, 20)
    total = roll + modifier
    difficulty = determine_difficulty(action_text)

    # Критические случаи
    if roll == 20:
        result_type = "критический успех"
        reason = "идеальное выполнение!"
        success = True
    elif roll == 1:
        result_type = "критический провал"
        reason = "катастрофическая неудача!"
        success = False
    else:
        success = total >= difficulty
        if success:
            result_type = "успех"
            reason = "действие удалось"
        else:
            result_type = "провал"
            reason = "действие не удалось"

    return {
        "success": success,
        "roll": roll,
        "modifier": modifier,
        "total": total,
        "difficulty": difficulty,
        "stat": stat_name,
        "stat_value": stat_value,
        "result_type": result_type,
        "reason": reason,
    }


# ============================================================
#  ПРОСТОЙ БРОСОК КУБИКА (без действия)
# ============================================================
def resolve_dice_roll(stat_name, state):
    """
    Ручной бросок кубика по навыку (без привязки к действию).
    """
    stat_value = state.get("skills", {}).get(stat_name, 10)
    modifier = get_modifier(stat_value)
    roll = random.randint(1, 20)
    total = roll + modifier

    return {
        "roll": roll,
        "modifier": modifier,
        "total": total,
        "stat": stat_name,
    }


# ============================================================
#  ФОРМАТИРОВАНИЕ РЕЗУЛЬТАТОВ
# ============================================================
def format_action_result(result):
    """Форматирует результат проверки действия для игрока."""
    sign = "+" if result["modifier"] >= 0 else "-"
    mod_abs = abs(result["modifier"])

    text = (
        f"🎲 Проверка: {result['stat']}\n"
        f"Бросок: {result['roll']} {sign} {mod_abs} = {result['total']}\n"
    )

    if result["success"]:
        text += f"✅ Успех! (нужно было ≥{result['difficulty']})"
    else:
        text += f"❌ Провал! (нужно было ≥{result['difficulty']})"

    if result["result_type"] in ("критический успех", "критический провал"):
        text += f"\n💥 {result['reason']}"

    return text


def format_dice_result(result):
    """Форматирует результат простого броска."""
    stat_name = result.get("stat", "")
    if stat_name:
        sign = "+" if result["modifier"] >= 0 else "-"
        mod_abs = abs(result["modifier"])
        return f"🎲 {stat_name}: {result['roll']} {sign} {mod_abs} = {result['total']}"
    else:
        return f"🎲 Бросок: {result['roll']}"
