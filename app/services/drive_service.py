"""Drive con OAuth local: un usuario, una carpeta, solo lectura."""
from pathlib import Path
from io import BytesIO
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
ROOT = Path(__file__).resolve().parents[2]

class DriveService:
    def __init__(self):
        token = ROOT / "token.json"
        credentials_file = ROOT / "credentials.json"
        creds = None
        if token.exists():
            creds = Credentials.from_authorized_user_file(str(token), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            if not credentials_file.exists():
                raise RuntimeError("Falta credentials.json. Configura OAuth Desktop en Google Cloud.")
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        token.write_text(creds.to_json(), encoding="utf-8")
        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_files(self, folder_id: str) -> list[dict]:
        if not folder_id: raise ValueError("Configura GOOGLE_DRIVE_FOLDER_ID en .env")
        files, page = [], None
        query = "'" + folder_id + "' in parents and trashed = false"
        while True:
            result = self.service.files().list(q=query, pageSize=100, pageToken=page,
                fields="nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink,size)",
                orderBy="name").execute()
            files.extend(result.get("files", []))
            page = result.get("nextPageToken")
            if not page: return files

    def get_bytes(self, item: dict) -> tuple[bytes, str, str]:
        mime = item["mimeType"]
        file_id = item["id"]
        if mime == "application/vnd.google-apps.document":
            req = self.service.files().export_media(fileId=file_id, mimeType="text/plain")
            filename = item["name"] + ".txt"
            target_mime = "text/plain"
        elif mime in ("application/pdf", "text/plain"):
            req = self.service.files().get_media(fileId=file_id)
            filename, target_mime = item["name"], mime
        else:
            raise ValueError("Formato no admitido: " + mime)
        stream = BytesIO()
        downloader = MediaIoBaseDownload(stream, req)
        finished = False
        while not finished:
            _, finished = downloader.next_chunk()
        return stream.getvalue(), filename, target_mime
