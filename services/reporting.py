import asyncio
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import InputReportReasonSpam
from telethon.errors import FloodWaitError
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ReportingService:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.active_tasks: Dict[str, Dict] = {}
        self.task_lock = asyncio.Lock()

    async def start_reporting(self, chat_id: str, msg_id: int, is_private: bool) -> str:
        """Start a new reporting task."""
        task_id = str(uuid.uuid4())
        async with self.task_lock:
            self.active_tasks[task_id] = {
                'chat_id': chat_id,
                'msg_id': msg_id,
                'is_private': is_private,
                'status': 'running',
                'success_count': 0,
                'failed_count': 0,
                'start_time': datetime.now()
            }

        asyncio.create_task(self.process_reporting(task_id))
        return task_id

    async def process_reporting(self, task_id: str) -> None:
        """Process reporting task with session rotation."""
        task = self.active_tasks.get(task_id)
        if not task:
            return

        clients = self.session_manager.get_active_sessions()
        for i, client in enumerate(clients):
            try:
                await client.connect()
                chat = await client.get_entity(task['chat_id'] if not task['is_private'] else int(f"-100{task['chat_id']}"))
                await client(ReportRequest(
                    peer=chat,
                    id=[task['msg_id']],
                    reason=InputReportReasonSpam()
                ))
                task['success_count'] += 1
                logger.info(f"Successful report: Task {task_id}, Session {i}")
                await asyncio.sleep(1)  # Rate limiting
            except FloodWaitError as e:
                task['failed_count'] += 1
                logger.warning(f"Flood wait: {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                task['failed_count'] += 1
                logger.error(f"Report failed: {e}")
            finally:
                await client.disconnect()

            # Rotate sessions every 10 minutes
            if i % 10 == 0:
                await asyncio.sleep(600)

        async with self.task_lock:
            task['status'] = 'completed'
            logger.info(f"Task {task_id} completed: {task['success_count']} successful, {task['failed_count']} failed")

    async def stop_task(self, task_id: str) -> bool:
        """Stop a specific reporting task."""
        async with self.task_lock:
            if task_id in self.active_tasks:
                self.active_tasks[task_id]['status'] = 'stopped'
                return True
            return False
