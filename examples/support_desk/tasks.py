"""Durable, tenant-aware background work for the reference app."""

from aksara import task

from .models import DeliveryAttempt, Ticket


@task(name="support_desk.deliver_ticket", max_attempts=3, queue="deliveries")
async def deliver_ticket(ticket_id: str, *, fail_until_attempt: int = 0) -> dict[str, object]:
    ticket = await Ticket.objects.get(id=ticket_id)
    records = await DeliveryAttempt.objects.filter(ticket_id=ticket.id).all()
    attempt = records[0] if records else await DeliveryAttempt.objects.create(
        tenant_id=ticket.tenant_id,
        ticket_id=ticket.id,
        attempts=0,
        delivered=False,
    )
    attempt.attempts += 1
    if attempt.attempts <= fail_until_attempt:
        attempt.last_error = "simulated downstream outage"
        await attempt.save()
        raise RuntimeError("simulated downstream outage")

    attempt.delivered = True
    attempt.last_error = None
    await attempt.save()
    return {
        "ticket_id": str(ticket.id),
        "tenant_id": str(ticket.tenant_id),
        "attempts": attempt.attempts,
        "delivered": True,
    }
