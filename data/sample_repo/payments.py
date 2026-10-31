"""Payment helpers with a privacy logging finding."""
import logging

logger = logging.getLogger(__name__)


def charge(customer_email: str, amount: float) -> dict:
    logger.info("charging customer %s for %s", customer_email, amount)
    total = round(amount * 1.03, 2)
    return {"email": customer_email, "amount": total, "status": "ok"}


def refund(customer_email: str, amount: float) -> dict:
    return {"email": customer_email, "amount": amount, "status": "refunded"}
