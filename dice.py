import random

# ============================================================
#  БАЗОВЫЕ БРОСКИ
# ============================================================
def roll_d20():
    """Бросок d20."""
    return random.randint(1, 20)

def roll_dice(count, sides):
    """Бросок нескольких кубиков: count * d(sides)."""
    return sum(random.randint(1, sides) for _ in range(count))

# ============================================================
#  ПРОВЕРКИ ДЕЙСТВИЙ (для квестов/навыков)
# ============================================================
def check_action(stat_value, difficulty=10):
    """
    Проверка действия: бросок d20 + модификатор против сложности.
    Возвращает: (успех: bool, бросок: int, итого: int)
    """
    roll = roll_d20()
    # Модификатор по D&D-формуле: (stat - 10) // 2
    modifier = (stat_value - 10) // 2
    total = roll + modifier
    success = total >= difficulty
    return success, roll, total

# ============================================================
#  ФОРМАТИРОВАНИЕ РЕЗУЛЬТАТОВ
# ============================================================
def format_roll_result(roll, modifier, total, description=""):
    """
    Красиво оформляет результат броска.
    Пример: "🎲 Проверка Ловкости: 15 + 2 = 17 (успех)"
    """
    sign = "+" if modifier >= 0 else "-"
    mod_abs = abs(modifier)
    status = "✅ успех" if total >= 10 else "❌ провал"
    
    parts = []
    if description:
        parts.append(f"{description}:")
    parts.append(f"🎲 {roll} {sign} {mod_abs} = {total} ({status})")
    return " ".join(parts)

# ============================================================
#  БОЕВЫЕ БРОСКИ (попадание/урон)
# ============================================================
def roll_to_hit(attack_bonus, ac):
    """Проверка попадания: d20 + бонус атаки против AC цели."""
    roll = roll_d20()
    total = roll + attack_bonus
    hit = total >= ac
    return hit, roll, total

def roll_damage(dice_count, dice_sides, modifier=0):
    """Урон: count*d(sides) + модификатор."""
    base = roll_dice(dice_count, dice_sides)
    return base + modifier

# ============================================================
#  СПЕЦИАЛЬНЫЕ МЕХАНИКИ
# ============================================================
def critical_check(roll):
    """Возвращает тип крита: 'crit_hit', 'crit_fail', или None."""
    if roll == 20:
        return "crit_hit"
    if roll == 1:
        return "crit_fail"
    return None
