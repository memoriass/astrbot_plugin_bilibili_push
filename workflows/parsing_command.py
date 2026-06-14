from __future__ import annotations

import re

from .models import WorkflowRequest
from .pending import extract_task_ref
from .utils import normalize_workflow, normalize_sub_type


def workflow_from_cli(workflow: str, args: str = "") -> WorkflowRequest:
    selected = normalize_workflow(workflow or "list_subscriptions")
    target = str(args or "").strip()
    params = _parse_cli_params(target)
    return WorkflowRequest(
        workflow=selected,
        target=target,
        params=params,
        source="cli",
    )


def workflow_from_pending_shortcut(text: str) -> WorkflowRequest | None:
    task_ref = extract_task_ref(text)
    if not task_ref:
        return None
    action = re.sub(re.escape(task_ref), "", str(text or ""), count=1).strip()
    return WorkflowRequest(
        workflow="continue_pending",
        target=task_ref,
        params={"task_id": task_ref, "action": action},
        source="pending",
    )


def _parse_cli_params(text: str) -> dict:
    params = {}
    sub_type = normalize_sub_type(text)
    if sub_type != "dynamic":
        params["sub_type"] = sub_type
    uid_match = re.search(r"\b(\d{2,20})\b", text)
    if uid_match:
        params["uid"] = uid_match.group(1)
    return params
