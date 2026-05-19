import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

from robot_source import get_fake_telemetry

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent / "web-ui"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            data = get_fake_telemetry()
            await websocket.send_json(data)
            await asyncio.sleep(0.05)
    except Exception:
        print("WebSocket disconnected")


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web-ui")