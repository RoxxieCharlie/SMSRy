from typing import Optional, Any, Dict

from store.models import Activity
from store.services.live_update_service import publish_live_update


def _live_topics_for_activity(verb):
    verb_value = str(verb).lower()
    topics = {"activity", "dashboard"}

    request_markers = ("request",)
    issuance_markers = ("issuance",)
    stock_markers = ("stock", "low_stock")

    if any(marker in verb_value for marker in request_markers):
        topics.add("requests")
    if any(marker in verb_value for marker in issuance_markers):
        topics.update({"requests", "inventory", "history"})
    if any(marker in verb_value for marker in stock_markers):
        topics.update({"inventory", "history"})

    return topics


def emit_activity(
    *,
    actor,
    verb,
    summary: str,
    metadata: Optional[Dict[str, Any]] = None,
    target=None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
):
    """Central activity logger and live-update publisher."""

    if target is not None:
        resolved_type = target.__class__.__name__
        resolved_id = target.pk
    else:
        if not target_type:
            raise TypeError("emit_activity requires either target or target_type and target_id.")
        if target_id is None:
            raise TypeError("emit_activity requires either target or target_type and target_id.")
        resolved_type = target_type
        resolved_id = int(target_id)

    activity = Activity.objects.create(
        actor=actor,
        verb=verb,
        target_type=resolved_type,
        target_id=resolved_id,
        summary=summary,
        metadata=metadata or {},
    )

    publish_live_update(
        _live_topics_for_activity(verb),
        {
            "activity_id": activity.id,
            "verb": str(verb),
            "target_type": resolved_type,
            "target_id": resolved_id,
        },
    )

    return activity
