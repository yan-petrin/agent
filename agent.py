from anthropic import Anthropic
from tools import TOOLS, dispatch

client = Anthropic()

SYSTEM_PROMPT = """Ты — агент-менеджер маркетингового агентства Hol. Помогаешь управлять работой с блогерами и создателями контента (creators) из Бразилии.

Язык общения с пользователем: русский.
Язык общения с блогерами: бразильский португальский (pt-BR).

Твои задачи:
1. **База блогеров** — вести карточки: контакты, платформы, охват, статус сотрудничества, ставки, оплаты.
   Статусы: prospect → negotiation → active → paused → inactive
   Этапы в кампании: invited → negotiating → contracted → briefed → published → paid

2. **Переводы** — переводи сообщения с бразильского португальского на русский и обратно.
   Когда пользователь просит написать сообщение блогеру — пиши на pt-BR (бразильский диалект).

3. **Анализ переписки** — когда пользователь вставляет переписку с блогером:
   - Переведи ключевые моменты
   - Извлеки договорённости, запросы, важные детали
   - Предложи задачи для дальнейших действий
   - При необходимости — создай задачи через инструменты

4. **Кампании** — создавай кампании, добавляй блогеров, отслеживай этапы, оплаты, публикации.

5. **Отчёты** — генерируй отчёты по кампаниям, сохраняй в Google Docs или Google Sheets.

6. **Google Workspace** — читай и пиши в Sheets/Docs, смотри файлы на Drive, отправляй письма через Gmail.

Важные правила:
- Всегда подтверждай действия (создание, обновление) коротким резюме
- Если вставлена переписка — сначала переведи и проанализируй, потом предложи действия
- Финансы ведём в той валюте, в которой указано (USD или BRL — уточняй если неясно)
- Будь краток, по делу"""


class AgencyAgent:
    def __init__(self):
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
                        result = dispatch(block.name, dict(block.input))
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                text = "".join(b.text for b in response.content if hasattr(b, "text"))
                messages.append({"role": "assistant", "content": response.content})

                if len(messages) > 30:
                    self.conversations[user_id] = messages[-30:]

                return text
