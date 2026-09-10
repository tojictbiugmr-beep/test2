import os
import json

# ============================================================
#  КОНСТАНТЫ
# ============================================================
SKILL_POINTS_START = 5
HISTORY_LIMIT = 40           # сколько сообщений хранить до summarization
HISTORY_AFTER_SUMMARY = 10   # сколько оставить после summarization
WORLD_LOG_LIMIT = 50         # сколько событий хранить в логе мира

STATE_DIR = os.path.join(os.path.dirname(__file__), "states")

# ============================================================
#  СТАТЫ КЛАССОВ
#  Ключи — русские, совпадают с combat.CLASSES
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

        # Класс и навыки
        "class_name": None,
        "skills": DEFAULT_SKILLS.copy(),
        "skill_points_remaining": SKILL_POINTS_START,

        # Инвентарь
        "inventory": [],

        # Бой
        "combat": None,

        # Память
        "turn_count": 0,
        "chat_history": [],
        "world_log": [],
        "world_facts": {},
        "story_summary": "",

        # Локация
        "location": "Вход в подземелье",
    }


def reset_state(chat_id):
    """Создаёт свежее состояние и сохраняет его."""
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
    """Загружает состояние игрока. Если нет — создаёт дефолтное."""
    path = _state_path(chat_id)
    if not os.path.exists(path):
        return default_state()
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        # Дополняем недостающие поля (для совместимости при обновлениях)
    default = default_state()
    for key, val in default.items():
        if key not in state:
            state[key] = val if isinstance(val, (str, int, float, bool)) else val.copy()
    return state


def save_state(chat_id, state):
    """Сохраняет состояние игрока в JSON-файл."""
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
    """Добавляет сообщение в историю диалога."""
    history = state.setdefault("chat_history", [])
    history.append({"role": role, "content": content})

    # Ограничиваем длину
    if len(history) > HISTORY_LIMIT:
        # Оставляем последние HISTORY_AFTER_SUMMARY + нарастающий хвост
        state["chat_history"] = history[-HISTORY_AFTER_SUMMARY:]


# ============================================================
#  ЛОГ МИРА
# ============================================================
def add_world_event(state, event_text):
    """Добавляет короткое событие в мировой лог."""
    log = state.setdefault("world_log", [])
    log.append(event_text)
    if len(log) > WORLD_LOG_LIMIT:
        state["world_log"] = log[-WORLD_LOG_LIMIT:]


def add_world_fact(state, key, value):
    """Добавляет или обновляет факт мира."""
    facts = state.setdefault("world_facts", {})
    facts[key] = value


# ============================================================
#  СБОРКА КОНТЕКСТА ПАМЯТИ ДЛЯ ИИ
# ============================================================
def build_memory_context(state):
    """Собирает текстовый контекст из сводки, фактов, событий и навыков."""
    parts = []

    # Сводка сюжета
    summary = state.get("story_summary", "")
    if summary:
        parts.append(f"Сводка: {summary}")

    # Факты мира
    facts = state.get("world_facts", {})
    if facts:
        facts_text = "; ".join([f"{k}: {v}" for k, v in facts.items()])
        parts.append(f"Факты: {facts_text}")

    # Последние события
    log = state.get("world_log", [])
    if log:
        recent = log[-8:]
        parts.append("События: " + " | ".join(recent))

    # Класс и навыки
    class_name = state.get("class_name")
    if class_name:
        parts.append(f"Класс: {class_name}")
        skills = state.get("skills", {})
        skills_str = ", ".join([f"{k} {v}" for k, v in skills.items()])
        parts.append(f"Навыки: {skills_str}")

    # Снаряжение
    inv = state.get("inventory", [])
    if inv:
        parts.append(f"Снаряжение: {', '.join(inv)}")

    # Состояние героя
    hp = state.get("hp", 10)
    max_hp = state.get("max_hp", 10)
    wounded = state.get("is_wounded", False)
    torch = state.get("has_torch", False)
    parts.append(f"HP: {hp}/{max_hp}, ранен: {'да' if wounded else 'нет'}, факел: {'горит' if torch else 'нет'}")

    # Боевой контекст
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
    """Если история длинная — просит ИИ сжать её в краткую сводку."""
    history = state.get("chat_history", [])
    if len(history) < HISTORY_LIMIT:
        return

    # Собираем текст для summarization
    dialogue = "\n".join([f"{h['role']}: {h['content']}" for h in history])

    existing_summary = state.get("story_summary", "")
    prompt = (
        "Сожми историю приключения в краткую сводку (3-5 предложений). "
        "Сохрани ключевые факты: где герой, что произошло, важные находки. "
        "Пиши на русском, без маркеров."
    )
    if existing_summary:
        prompt += f"\n\nТекущая сводка:\n{existing_summary}"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": dialogue},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        state["story_summary"] = response.choices[0].message.content.strip()
        # Оставляем только последние сообщения после сводки
        state["chat_history"] = history[-HISTORY_AFTER_SUMMARY:]
        print(f"[memory] История сжата. Осталось {len(state['chat_history'])} сообщений.")
    except Exception as e:
        print(f"[memory] Ошибка summarization: {e}")
        # Фоллбэк: просто обрезаем
        state["chat_history"] = history[-HISTORY_AFTER_SUMMARY:]
      
