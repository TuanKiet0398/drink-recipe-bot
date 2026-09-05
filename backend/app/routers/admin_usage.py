from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db.base import get_db
from app.db.models import TokenUsage

router = APIRouter(prefix="/admin/usage")

# USD per 1,000,000 tokens. A model not listed here contributes $0 to the
# cost estimate rather than raising — this is a rough-visibility estimate,
# not a billing reconciliation. Prices current as of this feature's design.
PRICES_PER_MILLION_TOKENS = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "text-embedding-3-small": {"prompt": 0.02, "completion": 0.0},
}


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = PRICES_PER_MILLION_TOKENS.get(model)
    if prices is None:
        return 0.0
    return (prompt_tokens * prices["prompt"] + completion_tokens * prices["completion"]) / 1_000_000


@router.get("")
def usage_list(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    rows = (
        db.query(TokenUsage)
        .order_by(TokenUsage.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "call_type": r.call_type,
            "model": r.model,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.total_tokens,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/summary")
def usage_summary(
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    rows = (
        db.query(
            TokenUsage.model,
            func.count(TokenUsage.id).label("calls"),
            func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
        )
        .group_by(TokenUsage.model)
        .all()
    )

    by_model = []
    total_calls = 0
    total_tokens = 0
    estimated_cost_usd = 0.0
    for row in rows:
        cost = _estimate_cost_usd(row.model, row.prompt_tokens, row.completion_tokens)
        by_model.append(
            {
                "model": row.model,
                "calls": row.calls,
                "total_tokens": row.total_tokens,
                "estimated_cost_usd": round(cost, 4),
            }
        )
        total_calls += row.calls
        total_tokens += row.total_tokens
        estimated_cost_usd += cost

    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(estimated_cost_usd, 4),
        "by_model": by_model,
    }
