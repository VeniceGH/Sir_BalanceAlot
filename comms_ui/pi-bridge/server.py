import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from serial_link import connect_serial, send_serial_command

from robot_source import get_fake_telemetry

app = FastAPI()

@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.on_event("startup")
async def startup_event():
    connect_serial()

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent / "web-ui"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def send_telemetry():
        while True:
            data = get_fake_telemetry()
            await websocket.send_json(data)
            await asyncio.sleep(0.05)

    async def receive_commands():
        while True:
            message = await websocket.receive_json()

            if message.get("type") == "command":
                command = message.get("command")
                print("Received command:", command)
                send_serial_command(command)

    try:
        await asyncio.gather(
            send_telemetry(),
            receive_commands()
        )
    except Exception:
        print("WebSocket disconnected")

@app.get("/camera-feed")
def camera_feed_placeholder():
    svg = """
    <svg width="520" height="320" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#111"/>
      <text x="50%" y="45%" dominant-baseline="middle" text-anchor="middle"
            font-family="Arial" font-size="26" fill="white">
        Camera feed not connected
      </text>
      <text x="50%" y="58%" dominant-baseline="middle" text-anchor="middle"
            font-family="Arial" font-size="16" fill="#aaa">
        Raspberry Pi camera stream will appear here
      </text>
    </svg>
    """
    return Response(content=svg, media_type="image/svg+xml")

app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web-ui")