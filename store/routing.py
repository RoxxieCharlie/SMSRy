from django.urls import path

from store.consumers import LiveUpdateConsumer


websocket_urlpatterns = [
    path("ws/live/", LiveUpdateConsumer.as_asgi()),
]
