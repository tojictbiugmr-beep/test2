import os
import json

# ============================================================
#  КОНСТАНТЫ
# ============================================================
SKILL_POINTS_START = 5

# Слой 3: рабочая память
HISTORY_LIMIT = 12
HISTORY_AFTER_SUMMARY = 6

# Слой 2: эпизодическая память
WORLD_LOG_LIMIT = 30
CHAPTER_EVENT_THRESHOLD = 10  # сколько событий накопить до создания главы

# Слой 1: постоянная память
WORLD_FACTS_LIMIT = 50
CHAPTER_SUMMARIES_LIMIT = 20

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
#  СОСТОЯНИЕ ПО УМОЛЧАНИЮ
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

        # --- СЛОЙ 1: ПОСТОЯННАЯ ПАМЯТЬ ---
        "world_facts": {},           # факты мира (накапливаются, не сжимаются)
        "chapter_summaries": [],     # сводки завершённых глав (накапливаются)

        # --- СЛОЙ 2: ЭПИЗОДИЧЕСКАЯ ПАМЯТЬ ---
        "world_log": [],             # важные события текущей главы
        "chapter_summary": "",       # сводка текущей главы (ещё не завершена)
        "chapter_event_count": 0,   # счётчик событий для создания главы

        # --- СЛОЙ 3: РАБОЧАЯ ПАМЯТЬ ---
        "chat_history": [],          # сырые сообщения (обрезаются)
        "story_summary": "",         # сводка последних ходов (обновляется)

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
        print(f"[memory] Файл состояния повреждён: {path}. Сброс.")
        return default_state()

    default = default_state()
    for key, val in default.items():
        if key not in state:
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
#  ИСТОРИЯ ДИАЛОГА + АВТОЛОГ
# ============================================================
def add_to_history(state, role, content):
    history = state.setdefault("chat_history", [])
    history.append({"role": role, "content": content})

    # Автолог: краткая запись ответа ИИ в world_log (Слой 2)
    if role == "assistant":
        short = content[:100].replace("\n", " ").strip()
        if short:
            add_world_event(state, short)

    if len(history) > HISTORY_LIMIT:
        state["chat_history"] = history[-HISTORY_AFTER_SUMMARY:]


# ============================================================
#  СЛОЙ 2: СОБЫТИЯ
# ============================================================
def add_world_event(state, event_text):
    log = state.setdefault("world_log", [])
    if log and log[-1] == event_text:
        return
    log.append(event_text)
    state["chapter_event_count"] = state.get("chapter_event_count", 0) + 1
    if len(log) > WORLD_LOG_LIMIT:
        state["world_log"] = log[-WORLD_LOG_LIMIT:]


# ============================================================
#  СЛОЙ 1: ФАКТЫ
# ============================================================
def add_world_fact(state, key, value):
    facts = state.setdefault("world_facts", {})
    key = key.strip()
    value = value.strip()
    if not key or not value:
        return
    facts[key] = value

    if len(facts) > WORLD_FACTS_LIMIT:
        keys = list(facts.keys())
        for k in keys[:len(keys) - WORLD_FACTS_LIMIT]:
            del facts[k]


# ============================================================
#  СБОРКА КОНТЕКСТА ПАМЯТИ ДЛЯ ИИ
# ============================================================
def build_memory_context(state):
    parts = []

    # --- СЛОЙ 1: ПОСТОЯННАЯ ПАМЯТЬ ---
    chapters = state.get("chapter_summaries", [])
    if chapters:
        parts.append("Прошлые главы:")
        for i, ch in enumerate(chapters[-3:], 1):  # последние 3 главы
            parts.append(f"  Глава {len(chapters) - 3 + i}: {ch}")

    facts = state.get("world_facts", {})
    if facts:
        facts_text = "; ".join([f"{k}: {v}" for k, v in facts.items()])
        parts.append(f"Факты мира: {facts_text}")

    # --- СЛОЙ 2: ЭПИЗОДИЧЕСКАЯ ПАМЯТЬ ---
    chapter = state.get("chapter_summary", "")
    if chapter:
        parts.append(f"Текущая глава: {chapter}")

    log = state.get("world_log", [])
    if log:
        recent = log[-8:]
        parts.append("События: " + " | ".join(recent))

    # --- СЛОЙ 3: РАБОЧАЯ ПАМЯТЬ ---
    summary = state.get("story_summary", "")
    if summary:
        parts.append(f"Недавнее: {summary}")

    # --- ТЕКУЩЕЕ СОСТОЯНИЕ ---
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
    parts.append(
        f"HP: {hp}/{max_hp}, ранен: {'да' if wounded else 'нет'}, "
        f"факел: {'горит' if torch else 'нет'}"
    )

    combat = state.get("combat")
    if combat and combat.get("active"):
        enemies = [e for e in combat.get("enemies", []) if e.get("hp", 0) > 0]
        if enemies:
            parts.append("В бою с: " + ", ".join([e["name"] for e in enemies]))

    return "\n".join(parts) if parts else "(память пуста)"


# ============================================================
#  СЖАТИЕ СЛОЯ 3 → СЛОЙ 2 + ИЗВЛЕЧЕНИЕ ФАКТОВ В СЛОЙ 1
# ============================================================
def maybe_summarize(state, client, model):
    history = state.get("chat_history", [])
    if len(history) < HISTORY_LIMIT:
        return

    dialogue = "\n".join([f"{h['role']}: {h['content']}" for h in history])

    existing_facts = state.get("world_facts", {})
    existing_facts_str = (
        "; ".join([f"{k}: {v}" for k, v in existing_facts.items()])
        if existing_facts else "(пока нет)"
    )

    prompt = (
        "Ты — архивариус текстовой RPG. Проанализируй недавний диалог и извлеки:\n\n"
        "1. СВОДКА — что произошло за последние ходы (2-3 предложения).\n"
        "2. ФАКТЫ — важные постоянные факты о мире, персонажах, локациях.\n"
        "   Каждый факт: ФАКТ: название = значение\n"
        "   НЕ дублируй уже известные факты.\n\n"
        f"Уже известные факты:\n{existing_facts_str}\n\n"
        "Формат ответа:\n"
        "СВОДКА:\n<текст>\n\n"
        "ФАКТЫ:\nФАКТ: название = значение\n\n"
        "Если новых фактов нет — только СВОДКА."
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": dialogue},
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=400,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()

        new_facts_added = 0

        if "СВОДКА:" in raw:
            parts = raw.split("СВОДКА:", 1)
            after_summary = parts[1]

            if "ФАКТЫ:" in after_summary:
                summary_part, facts_part = after_summary.split("ФАКТЫ:", 1)
                state["story_summary"] = summary_part.strip()

                for line in facts_part.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("ФАКТ:") and "=" in line:
                        fact_content = line.replace("ФАКТ:", "").strip()
                        key, _, value = fact_content.partition("=")
                        if key.strip() and value.strip():
                            if key.strip() not in existing_facts:
                                add_world_fact(state, key, value)
                                new_facts_added += 1
            else:
                state["story_summary"] = after_summary.strip()
        else:
            state["story_summary"] = raw[:300]

        state["chat_history"] = history[-HISTORY_AFTER_SUMMARY:]

        # --- Проверяем: накопилось ли событий для создания главы ---
        maybe_close_chapter(state, client, model)

        print(
            f"[memory] Слой 3→2: сводка обновлена, фактов +{new_facts_added}, "
            f"всего фактов: {len(state.get('world_facts', {}))}, "
            f"событий: {len(state.get('world_log', []))}, "
            f"глав: {len(state.get('chapter_summaries', []))}"
        )

    except Exception as e:
        print(f"[memory] Ошибка summarization: {e}")
        state["chat_history"] = history[-HISTORY_AFTER_SUMMARY:]


# ============================================================
#  СЖАТИЕ СЛОЯ 2 → СЛОЙ 1 (ЗАВЕРШЕНИЕ ГЛАВЫ)
# ============================================================
def maybe_close_chapter(state, client, model):
    """
    Если в world_log накопилось достаточно событий —
    сжимаем их в главу и переносим в постоянную память.
    """
    event_count = state.get("chapter_event_count", 0)
    if event_count < CHAPTER_EVENT_THRESHOLD:
        return

    log = state.get("world_log", [])
    if not log:
        return

    existing_summary = state.get("chapter_summary", "")

    prompt = (
        "Ты — летописец текстовой RPG. Сожми события текущей главы "
        "в связный рассказ (4-6 предложений). Сохрани ключевые повороты, "
        "находки, встречи. Пиши на русском, без маркеров."
    )
    if existing_summary:
        prompt += f"\n\nТекущая сводка главы:\n{existing_summary}"

    events_text = "\n".join([f"- {e}" for e in log])
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": events_text},
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,
            temperature=0.4,
        )
        chapter_text = response.choices[0].message.content.strip()

        # Сохраняем главу в постоянную память (Слой 1)
        chapters = state.setdefault("chapter_summaries", [])
        chapters.append(chapter_text)
        if len(chapters) > CHAPTER_SUMMARIES_LIMIT:
            state["chapter_summaries"] = chapters[-CHAPTER_SUMMARIES_LIMIT:]

        # Очищаем Слой 2
        state["world_log"] = []
        state["chapter_summary"] = ""
        state["chapter_event_count"] = 0

        print(f"[memory] Слой 2→1: глава завершена (#{len(chapters)}). "
              f"Постоянных глав: {len(chapters)}")

    except Exception as e:
        print(f"[memory] Ошибка close_chapter: {e}")
