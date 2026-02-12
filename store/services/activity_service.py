from typing import Optional, Any, Dict
from store.models import Activity


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
    """
    Central activity logger.

    Supports BOTH styles:
    1) emit_activity(..., target=<model instance>)
    2) emit_activity(..., target_type="Issuance", target_id=0)  # for failed attempts
    """

    if target is not None:
        resolved_type = target.__class__.__name__
        resolved_id = target.pk
    else:
        if not target_type or target_id is None:
            raise TypeError("emit_activity requires either target OR (target_type and target_id).")
        resolved_type = target_type
        resolved_id = int(target_id)

    Activity.objects.create(
        actor=actor,
        verb=verb,
        target_type=resolved_type,
        target_id=resolved_id,
        summary=summary,
        metadata=metadata or {},
    )
