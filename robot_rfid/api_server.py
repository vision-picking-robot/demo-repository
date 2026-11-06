import asyncio
import os
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator

from database import Database, normalize_uid


class ScanEvent(BaseModel):
    uid: str
    quantity: int = Field(default=1, ge=1, le=10000)
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=128)

    @field_validator('uid')
    @classmethod
    def valid_uid(cls, value):
        return normalize_uid(value)


class Progress(BaseModel):
    completed: int = Field(ge=0)
    status: str
    error: str | None = None


def create_app(db_path=None):
    db = Database(db_path or os.getenv('RFID_DB', 'rfid.db'))
    clients: set[asyncio.Queue] = set()

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(db.initialize)
        yield

    app = FastAPI(title='RFID Pick-and-Place', lifespan=lifespan)
    app.state.database = db

    def broadcast(packet):
        for queue in tuple(clients):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(packet)

    @app.get('/api/v1/tags/{uid}')
    async def get_tag(uid: str):
        try:
            product = await asyncio.to_thread(db.product, uid)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if product is None:
            raise HTTPException(404, 'Unknown tag')
        return product

    @app.post('/api/v1/scan-event')
    async def scan(event: ScanEvent):
        try:
            task, created = await asyncio.to_thread(db.enqueue, event.uid, event.quantity, event.event_id)
        except KeyError as exc:
            raise HTTPException(404, 'Unknown tag') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        packet = {'type': 'scan', 'task': task, 'product': await asyncio.to_thread(db.product, event.uid)}
        if created:
            broadcast(packet)
        return {**packet, 'created': created}

    @app.get('/api/v1/current-task')
    async def current_task():
        return {'task': await asyncio.to_thread(db.current_task)}

    @app.patch('/api/v1/tasks/{task_id}')
    async def progress(task_id: str, body: Progress):
        try:
            await asyncio.to_thread(db.progress, task_id, body.completed, body.status, body.error)
        except KeyError as exc:
            raise HTTPException(404, 'Unknown task') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        packet = {'type': 'task_progress', 'task_id': task_id, **body.model_dump()}
        broadcast(packet)
        return packet

    @app.websocket('/ws')
    async def websocket(socket: WebSocket):
        await socket.accept()
        queue = asyncio.Queue(maxsize=100)
        clients.add(queue)

        async def sender():
            while True:
                await socket.send_json(await queue.get())

        writer = asyncio.create_task(sender())
        try:
            await socket.send_json({'type': 'snapshot', 'task': await asyncio.to_thread(db.current_task)})
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(queue)
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)

    return app


app = create_app()
