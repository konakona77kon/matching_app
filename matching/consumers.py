# matching/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # /ws/call/<room_id>/ から room_id を取得
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"call_{self.room_id}"

        # グループに参加
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # 他の参加者に「誰か入ったよ」と通知（必要なら使う）
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "signal_message",
                "event": "join",
                "sender": self.channel_name,
                "data": None,
            },
        )

    async def disconnect(self, close_code):
        # 離脱通知
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "signal_message",
                "event": "leave",
                "sender": self.channel_name,
                "data": None,
            },
        )
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """
        フロントから来る JSON:
          { "event": "offer" | "answer" | "candidate" | ...,
            "data": {...} }
        をそのままルームの「相手」に中継する。
        """
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        event = payload.get("event")
        data = payload.get("data")

        # ルーム内の全員にブロードキャスト（自分自身には後で除外）
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "signal_message",
                "event": event,
                "sender": self.channel_name,
                "data": data,
            },
        )

    async def signal_message(self, event):
        """
        group_send で呼ばれる。
        自分が送ったものはスキップして「相手」にだけ送る。
        """
        if event["sender"] == self.channel_name:
            return

        await self.send(
            text_data=json.dumps(
                {
                    "event": event["event"],
                    "data": event.get("data"),
                }
            )
        )
