"""Tool schemas (для Claude) и диспетчер вызовов."""
import json
import traceback
import database as db
import google_api as gapi

# ─── Schemas ────────────────────────────────────────────────────────────────────

TOOLS = [
    # Bloggers
    {
        "name": "add_blogger",
        "description": "Добавить нового блогера/создателя контента в базу данных агентства",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Имя блогера"},
                "telegram": {"type": "string", "description": "Telegram username (без @)"},
                "email": {"type": "string"},
                "platforms": {
                    "type": "object",
                    "description": 'Платформы и охват, например {"instagram": 50000, "youtube": 10000}',
                },
                "niche": {"type": "string", "description": "Ниша/тематика контента"},
                "rate": {"type": "number", "description": "Ставка (USD/BRL)"},
                "status": {
                    "type": "string",
                    "enum": ["prospect", "negotiation", "active", "paused", "inactive"],
                    "description": "Статус сотрудничества",
                },
                "notes": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "search_bloggers",
        "description": "Поиск блогеров в базе. Можно фильтровать по имени, статусу, платформе",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Строка поиска (имя, telegram, email, ниша)"},
                "status": {"type": "string", "enum": ["prospect", "negotiation", "active", "paused", "inactive"]},
                "platform": {"type": "string", "description": "Платформа: instagram, youtube, tiktok..."},
            },
        },
    },
    {
        "name": "update_blogger",
        "description": "Обновить данные блогера (статус, контакты, ставку и т.д.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "blogger_id": {"type": "integer"},
                "name": {"type": "string"},
                "telegram": {"type": "string"},
                "email": {"type": "string"},
                "platforms": {"type": "object"},
                "niche": {"type": "string"},
                "rate": {"type": "number"},
                "status": {"type": "string", "enum": ["prospect", "negotiation", "active", "paused", "inactive"]},
                "notes": {"type": "string"},
            },
            "required": ["blogger_id"],
        },
    },
    # Campaigns
    {
        "name": "create_campaign",
        "description": "Создать новую кампанию агентства",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "client": {"type": "string", "description": "Клиент/бренд"},
                "budget": {"type": "number", "description": "Бюджет кампании"},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                "status": {"type": "string", "enum": ["planning", "active", "completed", "cancelled"]},
                "description": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "link_blogger_to_campaign",
        "description": "Добавить блогера в кампанию с указанием этапа и условий",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "integer"},
                "blogger_id": {"type": "integer"},
                "stage": {
                    "type": "string",
                    "enum": ["invited", "negotiating", "contracted", "briefed", "published", "paid"],
                },
                "agreed_rate": {"type": "number", "description": "Согласованная сумма"},
                "payment_status": {"type": "string", "enum": ["pending", "partial", "paid"]},
                "post_url": {"type": "string", "description": "URL опубликованного поста"},
                "notes": {"type": "string"},
            },
            "required": ["campaign_id", "blogger_id"],
        },
    },
    {
        "name": "update_campaign_blogger",
        "description": "Обновить этап, оплату или данные блогера в кампании",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "integer"},
                "blogger_id": {"type": "integer"},
                "stage": {"type": "string", "enum": ["invited", "negotiating", "contracted", "briefed", "published", "paid"]},
                "agreed_rate": {"type": "number"},
                "payment_status": {"type": "string", "enum": ["pending", "partial", "paid"]},
                "post_url": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["campaign_id", "blogger_id"],
        },
    },
    {
        "name": "get_campaign_report",
        "description": "Получить полный отчёт по кампании: блогеры, этапы, бюджет, оплаты",
        "input_schema": {
            "type": "object",
            "properties": {"campaign_id": {"type": "integer"}},
            "required": ["campaign_id"],
        },
    },
    # Tasks
    {
        "name": "create_task",
        "description": "Создать задачу (можно привязать к блогеру или кампании)",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "assignee": {"type": "string"},
                "deadline": {"type": "string", "description": "YYYY-MM-DD"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
                "blogger_id": {"type": "integer"},
                "campaign_id": {"type": "integer"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_tasks",
        "description": "Список задач с фильтрацией по статусу, исполнителю, блогеру или кампании",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["open", "in_progress", "done", "closed"]},
                "assignee": {"type": "string"},
                "blogger_id": {"type": "integer"},
                "campaign_id": {"type": "integer"},
            },
        },
    },
    {
        "name": "update_task",
        "description": "Обновить задачу (статус, исполнитель, приоритет и т.д.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "assignee": {"type": "string"},
                "status": {"type": "string", "enum": ["open", "in_progress", "done", "closed"]},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
                "deadline": {"type": "string"},
            },
            "required": ["task_id"],
        },
    },
    # Google Workspace
    {
        "name": "sheets_read",
        "description": "Прочитать данные из Google Sheets",
        "input_schema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string", "description": "ID таблицы из URL"},
                "range_": {"type": "string", "description": 'Диапазон, например "Sheet1!A1:E20"'},
            },
            "required": ["spreadsheet_id", "range_"],
        },
    },
    {
        "name": "sheets_write",
        "description": "Записать данные в Google Sheets",
        "input_schema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string"},
                "range_": {"type": "string"},
                "values": {
                    "type": "array",
                    "items": {"type": "array"},
                    "description": "Двумерный массив значений",
                },
            },
            "required": ["spreadsheet_id", "range_", "values"],
        },
    },
    {
        "name": "sheets_append",
        "description": "Добавить строки в конец листа Google Sheets",
        "input_schema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string"},
                "sheet_name": {"type": "string", "description": "Название листа"},
                "values": {"type": "array", "items": {"type": "array"}},
            },
            "required": ["spreadsheet_id", "sheet_name", "values"],
        },
    },
    {
        "name": "docs_create",
        "description": "Создать Google Docs документ (отчёт, бриф и т.д.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Текстовое содержимое документа"},
                "folder_id": {"type": "string", "description": "ID папки на Drive (опционально)"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "docs_read",
        "description": "Прочитать содержимое Google Docs документа",
        "input_schema": {
            "type": "object",
            "properties": {"doc_id": {"type": "string", "description": "ID документа из URL"}},
            "required": ["doc_id"],
        },
    },
    {
        "name": "drive_list",
        "description": "Просмотреть файлы на Google Drive (по папке или поиску)",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_id": {"type": "string", "description": "ID папки (опционально)"},
                "query": {"type": "string", "description": "Поиск по имени файла"},
                "max_results": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "gmail_send",
        "description": "Отправить письмо через Gmail",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Email получателя"},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Текст письма (можно HTML)"},
                "html": {"type": "boolean", "default": False, "description": "True если тело в HTML"},
            },
            "required": ["to", "subject", "body"],
        },
    },
]


# ─── Dispatcher ─────────────────────────────────────────────────────────────────

def dispatch(tool_name: str, tool_input: dict) -> str:
    try:
        result = _call(tool_name, tool_input)
        return json.dumps(result, ensure_ascii=False, default=str)
    except FileNotFoundError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "trace": traceback.format_exc()}, ensure_ascii=False)


def _call(name: str, inp: dict):
    # Bloggers
    if name == "add_blogger":
        return db.add_blogger(**inp)
    if name == "search_bloggers":
        return db.search_bloggers(**inp)
    if name == "update_blogger":
        bid = inp.pop("blogger_id")
        return db.update_blogger(bid, **inp)

    # Campaigns
    if name == "create_campaign":
        return db.create_campaign(**inp)
    if name == "link_blogger_to_campaign":
        return db.link_blogger_to_campaign(**inp)
    if name == "update_campaign_blogger":
        return db.update_campaign_blogger(**inp)
    if name == "get_campaign_report":
        return db.get_campaign_report(**inp)

    # Tasks
    if name == "create_task":
        return db.create_task(**inp)
    if name == "list_tasks":
        return db.list_tasks(**inp)
    if name == "update_task":
        tid = inp.pop("task_id")
        return db.update_task(tid, **inp)

    # Google Workspace
    if name == "sheets_read":
        return gapi.sheets_read(inp["spreadsheet_id"], inp["range_"])
    if name == "sheets_write":
        return gapi.sheets_write(inp["spreadsheet_id"], inp["range_"], inp["values"])
    if name == "sheets_append":
        return gapi.sheets_append(inp["spreadsheet_id"], inp["sheet_name"], inp["values"])
    if name == "docs_create":
        return gapi.docs_create(inp["title"], inp["content"], inp.get("folder_id"))
    if name == "docs_read":
        return gapi.docs_read(inp["doc_id"])
    if name == "drive_list":
        return gapi.drive_list(inp.get("folder_id"), inp.get("query"), inp.get("max_results", 20))
    if name == "gmail_send":
        return gapi.gmail_send(inp["to"], inp["subject"], inp["body"], inp.get("html", False))

    return {"error": f"Неизвестный инструмент: {name}"}
