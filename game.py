from config import client, MODEL, SYSTEM_PROMPT
from memory import build_memory_context, add_to_history, maybe_summarize


def build_status(state):
    return (
        f"HP: {state['hp']}/{state['max_hp']}, "
        f"факел: {'есть' if state.get('has_torch') else 'нет'}, "
        f"ранен: {'да' if state.get('is_wounded') else 'нет'}, "
        f"шагов: {state.get('steps', 0)}."
    )


def generate_scene(state):
    memory = build_memory_context(state)
    status = build_status(state)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Контекст памяти:\n{memory}"},
        {"role": "user", "content": f"Опиши сцену в 2-3 предложениях. Контекст героя: {status}"}
    ]
    try:
        response = client.chat.completions.create(
            model=MODEL, messages=messages, max_tokens=500, temperature=0.7
        )
        scene_text = response.choices[0].message.content.strip()
        add_to_history(state, "assistant", scene_text)
        return scene_text
    except Exception as e:
        return f"Тьма сгущается... (ошибка: {e})"


def chat_with_ai(user_text, state):
    memory = build_memory_context(state)
    status = build_status(state)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Контекст памяти:\n{memory}"}
    ]
    for entry in state.get("chat_history", []):
        messages.append({"role": entry["role"], "content": entry["content"]})
    user_msg = f"Игрок делает: {user_text}\nКонтекст героя: {status}"
    messages.append({"role": "user", "content": user_msg})
    try:
        response = client.chat.completions.create(
            model=MODEL, messages=messages, max_tokens=800, temperature=0.8
        )
        reply = response.choices[0].message.content.strip()
        add_to_history(state, "user", user_text)
        add_to_history(state, "assistant", reply)
        state["turn_count"] = state.get("turn_count", 0) + 1
        maybe_summarize(state, client, MODEL)
        return reply
    except Exception as e:
        return f"Голос подземелья молчит... (ошибка: 
        {e})"
