from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.config import settings
from app.master_data.models import Member, Practice
from app.outbox.mailer import send_smtp
from app.outbox.models import OutboxEvent, OutboxKind, OutboxStatus
from app.prior_auth.models import PriorAuthProcedure, PriorAuthRequest


def _procedure_sequence(proc: PriorAuthProcedure) -> int:
    return proc.sequence


def render_decision_notice_body(request: PriorAuthRequest, member: Member | None) -> str:
    member_ref = member.external_id if member is not None else str(request.member_id)
    lines = [
        f"Request ID: {request.id}",
        f"Member: {member_ref}",
        f"Date of service: {request.date_of_service.isoformat()}",
        "Procedures:",
    ]
    ordered = list(request.procedures)
    ordered.sort(key=_procedure_sequence)
    for proc in ordered:
        lines.append(f"  {proc.code}: {proc.decision.value}")
    return "\n".join(lines)


def enqueue_decision_notice(db: Session, request: PriorAuthRequest) -> OutboxEvent:
    practice = db.get(Practice, request.practice_id)
    member = db.get(Member, request.member_id)
    assert practice is not None
    to_addr = practice.notification_email
    subject = f"Prior auth decision — {request.id}"
    body = render_decision_notice_body(request, member)
    event = OutboxEvent(
        kind=OutboxKind.decision_notice,
        request_id=request.id,
        practice_id=request.practice_id,
        payload={"to": to_addr, "subject": subject, "body": body},
        status=OutboxStatus.pending,
        attempts=0,
    )
    db.add(event)
    return event


def claim_batch(db: Session, *, limit: int | None = None) -> list[OutboxEvent]:
    batch_size = limit if limit is not None else settings.outbox_batch_size
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.status == OutboxStatus.pending)
        .order_by(OutboxEvent.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rows = db.scalars(stmt).all()
    return list(rows)


def mark_sent(db: Session, event: OutboxEvent) -> None:
    event.status = OutboxStatus.sent
    event.attempts = event.attempts + 1
    event.sent_at = utc_now()
    event.last_error = None


def mark_failed(db: Session, event: OutboxEvent, error: str) -> None:
    event.status = OutboxStatus.failed
    event.attempts = event.attempts + 1
    event.last_error = error[:2000]


def process_batch(
    db: Session,
    *,
    send_fn=send_smtp,
    limit: int | None = None,
) -> int:
    events = claim_batch(db, limit=limit)
    for event in events:
        payload = event.payload
        to = payload["to"]
        subject = payload["subject"]
        body = payload["body"]
        try:
            send_fn(to, subject, body)
        except Exception as exc:
            err = str(exc)
            mark_failed(db, event, err)
        else:
            mark_sent(db, event)
    if events:
        db.commit()
    return len(events)
