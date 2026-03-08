import os
import json
import openai
import asyncio
from dotenv import load_dotenv

load_dotenv()
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from .models import ChatMessage

openai.api_key = os.getenv("OPENAI_API_KEY")


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):

        self.room_group_name = "support_chat"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):

        data = json.loads(text_data)

        message = data["message"]
        username = data["username"]

        user = await User.objects.aget(username=username)

        await ChatMessage.objects.acreate(user=user, message=message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": message, "username": username},
        )

        # AI Auto Reply
        asyncio.create_task(self.ai_auto_reply(message))

    async def chat_message(self, event):

        await self.send(
            text_data=json.dumps(
                {"message": event["message"], "username": event["username"]}
            )
        )

    async def ai_auto_reply(self, message):

        await asyncio.sleep(3)

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are KishanHub agricultural assistant helping farmers.",
                },
                {"role": "user", "content": message},
            ],
        )

        ai_text = response["choices"][0]["message"]["content"]

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": ai_text, "username": "AI Assistant"},
        )
