import json

from channels.generic.websocket import AsyncWebsocketConsumer


class LiveUpdateConsumer(AsyncWebsocketConsumer):
    group_name = "store_live_updates"

    async def connect(self):
        user = self.scope.get("user")
        if not user:
            await self.close()
            return
        if not user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def live_update(self, event):
        await self.send(text_data=json.dumps(event.get("payload", {})))
