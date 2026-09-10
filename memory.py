import os
import json

# ============================================================
#  КОНСТАНТЫ
# ============================================================
SKILL_POINTS_START = 5
HISTORY_LIMIT = 40
HISTORY_AFTER_SUMMARY = 10
WORLD_LOG_LIMIT = 50

STATE_DIR = os.path.join(os.path.dirname(__file__), "states")

# ============================================================
#  СТАТЫ КЛАССОВ
# ============================================================
CLASS_STATS = {
    "воин": {
        "сила": 16,
        "выносливость": 14,
        "ловкость": 12,
        "знание": 8,
        "восприятие": 10,
    },
    "маг": {
        "сила": 8,
        "выносливость": 10,
        "ловкость": 10,
        "знание": 16,
        "восприятие": 12,
    },
    "разбойник": {
        "сила": 12,
        "выносливость": 12,
        "ловкость": 16,
        "знание": 10,
        "восприятие": 14,
    },
}

DEFAULT_SKILLS = {
    "сила": 10,
    "ловкость": 10,
    "выносливость": 10,
    "знание": 10,
    "восприятие": 10,
}

# ============================================================
#  СОЗДАНИЕ СОСТОЯНИЯ ПО УМОЛЧАНИЮ
# ============================================================
def default_state():
    return {
        "hp": 10,
        "max_hp": 10,
        "has_torch": False,
        "is_wounded": False,
        "steps": 0,

        "class_name": None,
        "skills": DEFAULT_SKILLS.copy(),
        "skill_points_remaining": SKILL_POINTS_START,

        "inventory": [],
        "combat": None,

        "turn_count": 0,
        "chat_history": [],
        "world_log": [],
        "world_facts": {},
        "story_summary": "",

        "location": "Вход в подземелье",
    }


def reset_state(chat_id):
    state = default_state()
    save_state(chat_id, state)
    return state


# ============================================================
#  ЗАГРУЗКА / СОХРАНЕНИЕ
# ============================================================
def _state_path(chat_id):
    os.makedirs(STATE_DIR, exist_ok=True)
    return os.path.join(STATE_DIR, f"{chat_id}.json")


def load_state(chat_id):
    path = _state_path(chat_id)
    if not os.path.exists(path):
        return default_state()

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, IOError):
        # Если файл битый или не читается — возвращаем дефолт
        print(f"[memory] Файл состояния повреждён или нечитаем: {path}. Сброс на default.")
        return default_state()

    # Дополняем недостающие поля (для совместимости при обновлениях)
    default = default_state()
    for key, val in default.items():
        if key not in state:
            # Копируем словари/списки, а не присваиваем ссылку
            if isinstance(val, dict):
                state[key] = val.copy()
            elif isinstance(val, list):
                state[key] = val[:]
            else:
                state[key] = val

    return state


def save_state(chat_id, state):
    path = _state_path(chat_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[memory] Ошибка сохранения: {e}")


# ============================================================
#  ИСТОРИЯ ДИАЛОГА
# ============================================================
def add_to_history(state, role, content):
    history = state.setdefault("chat_history", [])
    history.append({"role": role, "content": content})

    if len(history) > HISTORY_LIMIT:
        state["chat_history"] = history[-HISTORY_AFTER_SUMMARY:]


# ============================================================
#  ЛОГ МИРА
# ============================================================
def add_world_event(state, event_text):
    log = state.setdefault("world_log", [])
    log.append(event_text)
    if len(log) > WORLD_LOG_LIMIT:
        state["world_log"] = log[-WORLD_LOG_LIMIT:]


def add_world_fact(state, key, value):
    facts = state.setdefault("world_facts", {})
    facts[key] = value


# ============================================================
#  СБОРКА КОНТЕКСТА ПАМЯТИ ДЛЯ ИИ
# ============================================================
def build_memory_context(state):
    parts = []

    summary = state.get("story_summary", "")
    if summary:
        parts.append(f"Сводка: {summary}")

    facts = state.get("world_facts", {})
    if facts:
        facts_text = "; ".join([f"{k}: {v}" for k, v in facts.items()])
        parts.append(f"Факты: {facts_text}")

    log = state.get("world_log", [])
    if log:
        recent = log[-8:]
        parts.append("События: " + " | ".join(recent))

    class_name = state.get("class_name")
    if class_name:
        parts.append(f"Класс: {class_name}")
        skills = state.get("skills", {})
        skills_str = ", ".join([f"{k} {v}" for k, v in skills.items()])
        parts.append(f"Навыки: {skills_str}")

    inv = state.get("inventory", [])
    if inv:
        parts.append(f"Снаряжение: {', '.join(inv)}")

    hp = state.get("hp", 10)
    max_hp = state.get("max_hp", 10)
    wounded = state.get("is_wounded", False)
    torch = state.get("has_torch", False)
    parts.append(f"HP: {hp}/{max_hp}, ранен: {'да' if wounded else 'нет'}, факел: {'горит' if torch else 'нет'}")

    combat = state.get("combat")
    if combat and combat.get("active"):
        enemies = [e for e in combat.get("enemies", []) if e.get("hp", 0) > 0]
        if enemies:
            parts.append("В бою с: " + ", ".join([e["name"] for e in enemies]))

    return "\n".join(parts) if parts else "(память пуста)"


# ============================================================
#  СУММАРИЗАЦИЯ ИСТОРИИ ЧЕРЕЗ ИИ
# ============================================================
def maybe_summarize(state, client, model):
    history = state.get("chat_history", [])
    if len(history) < HISTORY_LIMIT:
        return

    dialogue = "\n".join([f"{h['role']}: {h['content']}" for h in history])
    existing_summary = state.get("story_summary", "")

    prompt = (
        "Сожми историю приключения в краткую сводку (3-5 предложений). "
        "Сохрани ключевые факты: где герой, что произошло, важные находки. "
        "Пиши на русском, без маркеров."
    )
    if existing_summary:
        prompt += f"\n\nТекущая сводка:\n{existing_summary}"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": dialogue},
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,
            temperature=0.3,
        )
        state["story_summary"] = response.choices[0].message.content.strip()
        state["chat_history"] = history[-HISTORY_AFTER_SUMMARY:]
        print(f"[memory] История сжата. Осталось {len(state['chat_history'])} сообщений.")
    except Exception as e:
        print(f"[memory] Ошибка summarization: {e}")
        # Фоллбэк: просто обрезаем
        state["chat_history"] = history[-HISTORY_AFTER_SUMMARY:]
