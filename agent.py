import json
from anthropic import Anthropic
import database as db

client = Anthropic()

TOOLS = [
    {
        "name": "create_task",
        "description": "Создать новую задачу/тикет в агентстве",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Название задачи"},
                "description": {"type": "string", "description": "Описание задачи"},
                "assignee": {"type": "string", "description": "Исполнитель задачи"},
                "deadline": {"type": "string", "description": "Дедлайн в формате YYYY-MM-DD"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "description": "Приоритет задачи",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_tasks",
        "description": "Получить список задач с возможностью фильтрации по статусу или исполнителю",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "done", "closed"],
                    "description": "Фильтр по статусу",
                },
                "assignee": {"type": "string", "description": "Фильтр по исполнителю"},
            },
        },
    },
    {
        "name": "update_task",
        "description": "Обновить задачу: статус, исполнителя, приоритет, дедлайн и другие поля",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "ID задачи"},
                "title": {"type": "string", "description": "Новое название"},
                "description": {"type": "string", "description": "Новое описание"},
                "assignee": {"type": "string", "description": "Новый исполнитель"},
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "done", "closed"],
                    "description": "Новый статус",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "description": "Новый приоритет",
                },
                "deadline": {"type": "string", "description": "Новый дедлайн YYYY-MM-DD"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "generate_report",
        "description": "Сгенерировать сводный отчёт о состоянии задач агентства",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "done", "closed"],
                    "description": "Показать только задачи с этим статусом (опционально)",
                }
            },
        },
    },
]

SYSTEM_PROMPT = """Ты — умный агент-менеджер агентства. Помогаешь отслеживать и управлять задачами,
проектами и делами. Общайся на русском языке.

Твои возможности:
- Создавать задачи с исполнителями, дедлайнами и приоритетами
- Просматривать и фильтровать задачи
- Обновлять статусы, исполнителей, приоритеты
- Генерировать отчёты о состоянии дел

Статусы задач: open (открыта), in_progress (в работе), done (выполнена), closed (закрыта).
Приоритеты: low, normal, high, urgent.

Отвечай кратко и по делу. Используй инструменты для работы с задачами."""


def _process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "create_task":
        task = db.create_task(**tool_input)
        return json.dumps(task, ensure_ascii=False)

    elif tool_name == "list_tasks":
        tasks = db.list_tasks(**tool_input)
        return json.dumps(tasks, ensure_ascii=False)

    elif tool_name == "update_task":
        task_id = tool_input.pop("task_id")
        task = db.update_task(task_id, **tool_input)
        if task is None:
            return json.dumps({"error": f"Задача #{task_id} не найдена"}, ensure_ascii=False)
        return json.dumps(task, ensure_ascii=False)

    elif tool_name == "generate_report":
        filter_status = tool_input.get("status")
        all_tasks = db.list_tasks()
        by_status = {}
        for t in all_tasks:
            s = t["status"]
            by_status.setdefault(s, []).append(t)
        report = {
            "total": len(all_tasks),
            "by_status": {k: len(v) for k, v in by_status.items()},
            "tasks": db.list_tasks(status=filter_status) if filter_status else all_tasks,
        }
        return json.dumps(report, ensure_ascii=False)

    return json.dumps({"error": f"Неизвестный инструмент: {tool_name}"})


class AgencyAgent:
    def __init__(self):
        # user_id -> list of messages
        self.conversations: dict[int, list] = {}

    def chat(self, user_id: int, user_message: str) -> str:
        if user_id not in self.conversations:
            self.conversations[user_id] = []

        messages = self.conversations[user_id]
        messages.append({"role": "user", "content": user_message})

        while True:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = _process_tool_call(block.name, dict(block.input))
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                text = "".join(b.text for b in response.content if hasattr(b, "text"))
                messages.append({"role": "assistant", "content": response.content})

                # Limit history to last 20 messages
                if len(messages) > 20:
                    self.conversations[user_id] = messages[-20:]

                return text
