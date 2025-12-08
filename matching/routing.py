# config/routing.py とかにある想定
from django.urls import re_path
from matching.consumers import CallConsumer

websocket_urlpatterns = [
    re_path(r"ws/call/(?P<room_id>\d+)/$", CallConsumer.as_asgi()),
]
