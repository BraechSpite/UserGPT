# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Your credentials
API_ID = 23844616
API_HASH = '4aeca3680a20f9b8bc669f9897d5402f'
SESSION_NAME = 'user_session'  # Make sure user_session.session is present

# Target chat ID for forwarding messages
TARGET_CHAT_ID = -1002593995412

# Store for tracking message processing
processing_queue = []
current_processing = None

# Initialize the client
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# Log all messages from the target chat
@client.on(events.NewMessage(chats=TARGET_CHAT_ID))
async def log_target_chat_messages(event):
    logger.info(f"[TARGET CHAT] {event.sender_id}: {event.text}")

# Store pending responses: {sender_id: message_id_sent_to_target_chat}
pending_responses = {}

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handle_new_message(event):
    global current_processing
    if current_processing is not None:
        return
    try:
        sender_id = event.sender_id
        if sender_id not in processing_queue:
            processing_queue.append(sender_id)
        current_processing = sender_id
        formatted_message = f"@CopilotOfficialBot {event.text} , reply in short"
        sent_message = await client.send_message(TARGET_CHAT_ID, formatted_message)
        pending_responses[sender_id] = sent_message.id
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        if current_processing in processing_queue:
            processing_queue.remove(current_processing)
        current_processing = None

@client.on(events.NewMessage(chats=TARGET_CHAT_ID))
async def forward_response_to_user(event):
    global current_processing
    for sender_id, sent_msg_id in list(pending_responses.items()):
        if event.reply_to_msg_id == sent_msg_id or (event.id > sent_msg_id and current_processing == sender_id):
            try:
                await client.send_message(sender_id, event.text)
                logger.info(f"Forwarded response to user {sender_id}")
            except Exception as e:
                logger.error(f"Failed to forward response: {e}")
            if sender_id in processing_queue:
                processing_queue.remove(sender_id)
            pending_responses.pop(sender_id, None)
            current_processing = None
            break

# FastAPI app for Render health checks
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await client.start()
    asyncio.create_task(client.run_until_disconnected())
    logger.info("Telethon client started in background.")
    yield
    # Shutdown (optional):
    await client.disconnect()
    logger.info("Telethon client disconnected.")

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"status": "OK"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("UserGpt:app", host="0.0.0.0", port=port, reload=False) 