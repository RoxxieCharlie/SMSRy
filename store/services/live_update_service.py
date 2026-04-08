from django.utils import timezone


LIVE_UPDATE_GROUP = "store_live_updates"


def publish_live_update(topics, payload=None):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except Exception:
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    message = {
        "topics": list(topics),
        "payload": payload or {},
        "sent_at": timezone.now().isoformat(),
    }
    message.update(message.pop("payload"))

    async_to_sync(channel_layer.group_send)(
        LIVE_UPDATE_GROUP,
        {
            "type": "live.update",
            "payload": message,
        },
    )
