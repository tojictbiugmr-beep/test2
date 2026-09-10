# ============================================================
#  УПРАВЛЕНИЕ СНАРЯЖЕНИЕМ
#  → Добавить функции для новых типов предметов сюда.
# ============================================================

def init_inventory(state, class_key, cls):
    """Инициализирует инвентарь при выборе класса."""
    state["inventory"] = cls["equipment"].copy() + [cls["weapon"]]
    state["equipped_weapon"] = cls["weapon"]
    state["has_torch_item"] = True
    state["has_torch"] = False


def get_inventory_text(state):
    """Возвращает текст инвентаря."""
    inv = state.get("inventory", [])
    if not inv:
        return "Рюкзак пуст."
    return "🎒 Снаряжение:\n" + "\n".join([f"• {item}" for item in inv])


def add_item(state, item):
    """Добавляет предмет в инвентарь."""
    if "inventory" not in state:
        state["inventory"] = []
    state["inventory"].append(item)


def remove_item(state, item):
    """Удаляет предмет из инвентаря."""
    inv = state.get("inventory", [])
    if item in inv:
        inv.remove(item)
        return True
    return False


def has_item(state, item):
    """Проверяет наличие предмета."""
    return item in state.get("invento
    ry", [])
