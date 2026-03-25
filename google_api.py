"""Google Workspace integration: Sheets, Docs, Drive, Gmail."""
import os
import pickle
import base64
import json
from email.mime.text import MIMEText
from typing import List, Dict, Optional

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

TOKEN_PATH = "google_token.pickle"
CREDENTIALS_PATH = "google_credentials.json"


def _get_creds():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    "Файл google_credentials.json не найден. "
                    "Скачай OAuth2-ключи из Google Cloud Console и положи рядом с main.py."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            # run_console() — выводит URL в терминал, не требует браузера на сервере
            creds = flow.run_console()

        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return creds


def _svc(name: str, version: str):
    from googleapiclient.discovery import build
    return build(name, version, credentials=_get_creds())


# ─── Google Sheets ──────────────────────────────────────────────────────────────

def sheets_read(spreadsheet_id: str, range_: str) -> List[List]:
    """Читает данные из диапазона Google Sheets."""
    result = _svc("sheets", "v4").spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=range_
    ).execute()
    return result.get("values", [])


def sheets_write(spreadsheet_id: str, range_: str, values: List[List]) -> Dict:
    """Записывает данные в диапазон Google Sheets."""
    result = _svc("sheets", "v4").spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_,
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()
    return {"updated_cells": result.get("updatedCells", 0)}


def sheets_append(spreadsheet_id: str, sheet_name: str, values: List[List]) -> Dict:
    """Добавляет строки в конец листа Google Sheets."""
    result = _svc("sheets", "v4").spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()
    return {"updated_cells": result.get("updates", {}).get("updatedCells", 0)}


# ─── Google Docs ────────────────────────────────────────────────────────────────

def docs_create(title: str, content: str, folder_id: str = None) -> Dict:
    """Создаёт Google Docs документ с текстом. Возвращает ID и URL."""
    docs = _svc("docs", "v1")
    drive = _svc("drive", "v3")

    doc = docs.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
    ).execute()

    if folder_id:
        file = drive.files().get(fileId=doc_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents", []))
        drive.files().update(
            fileId=doc_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        ).execute()

    return {
        "doc_id": doc_id,
        "url": f"https://docs.google.com/document/d/{doc_id}/edit",
        "title": title,
    }


def docs_read(doc_id: str) -> str:
    """Читает текстовое содержимое Google Doc."""
    doc = _svc("docs", "v1").documents().get(documentId=doc_id).execute()
    text = ""
    for el in doc.get("body", {}).get("content", []):
        para = el.get("paragraph")
        if para:
            for run in para.get("elements", []):
                tr = run.get("textRun")
                if tr:
                    text += tr.get("content", "")
    return text


# ─── Google Drive ───────────────────────────────────────────────────────────────

def drive_list(folder_id: str = None, query: str = None, max_results: int = 20) -> List[Dict]:
    """Выводит список файлов на Google Drive."""
    parts = ["trashed=false"]
    if folder_id:
        parts.append(f"'{folder_id}' in parents")
    if query:
        parts.append(f"name contains '{query}'")

    results = _svc("drive", "v3").files().list(
        q=" and ".join(parts),
        fields="files(id,name,mimeType,webViewLink,modifiedTime)",
        pageSize=max_results,
    ).execute()
    return results.get("files", [])


# ─── Gmail ──────────────────────────────────────────────────────────────────────

def gmail_send(to: str, subject: str, body: str, html: bool = False) -> Dict:
    """Отправляет письмо через Gmail."""
    mime_type = "html" if html else "plain"
    message = MIMEText(body, mime_type, "utf-8")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = _svc("gmail", "v1").users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return {"message_id": sent["id"], "to": to, "subject": subject}
