from .branches import is_bili_dispatch_candidate
from .models import WorkflowRequest


def workflow_from_natural_language(text: str) -> WorkflowRequest | None:
    raw = str(text or "").strip()
    if not raw or not is_bili_dispatch_candidate(raw):
        return None
    return WorkflowRequest(
        "ai_dispatch",
        target=raw,
        params={"text": raw},
        source="natural",
    )
