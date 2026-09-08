from typing import Any

import firebase_admin
import httpx
from celery import shared_task
from firebase_admin import credentials, messaging

from app.core.config import settings


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.notifications.send_whatsapp_otp",
)
def send_whatsapp_otp(self, phone: str, otp: str) -> dict:  # type: ignore[no-untyped-def]
    """Envia OTP por WhatsApp (Meta Cloud API). En dev sin config: log y ok."""
    if not settings.WHATSAPP_API_URL or not settings.WHATSAPP_API_TOKEN:
        print(f"[WhatsApp DEV] OTP para {phone}: {otp}")
        return {"status": "logged_dev", "phone": phone}
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
                headers={
                    "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": phone.replace("+", ""),
                    "type": "template",
                    "template": {
                        "name": "otp_verification",
                        "language": {"code": "es"},
                        "components": [
                            {"type": "body", "parameters": [{"type": "text", "text": otp}]},
                        ],
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()
            msgs = payload.get("messages", [{}])
            return {"status": "sent", "message_id": msgs[0].get("id")}
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(name="app.tasks.notifications.send_fcm_notification")
def send_fcm_notification(
    token: str, title: str, body: str, data: dict[str, Any] | None = None
) -> dict:
    """Envía una notificación FCM; en desarrollo sin credenciales sólo registra."""
    preview = token[:20] if len(token) > 20 else token
    if not settings.FCM_CREDENTIALS_PATH:
        print(f"[FCM DEV] To: {preview}... Title: {title} Body: {body} Data: {data}")
        return {"status": "logged_dev"}
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(settings.FCM_CREDENTIALS_PATH))
    message_id = messaging.send(
        messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data={key: str(value) for key, value in (data or {}).items()},
        )
    )
    return {"status": "sent", "message_id": message_id}


@shared_task(name="app.tasks.notifications.notify_restaurant_new_order")
def notify_restaurant_new_order(restaurant_id: str, order_number: str) -> dict:
    print(
        f"[Notify] Restaurante {restaurant_id} nueva orden {order_number} (PREPARING, campana 3 tonos)"
    )
    return {"status": "logged_dev"}


@shared_task(name="app.tasks.notifications.notify_driver_new_order")
def notify_driver_new_order(driver_id: str, order_id: str, order_number: str) -> dict:
    print(f"[Notify] Driver {driver_id} orden disponible {order_number}")
    return {"status": "logged_dev"}


@shared_task(name="app.tasks.notifications.notify_customer_order_status")
def notify_customer_order_status(
    customer_id: str, order_id: str, status: str, message: str
) -> dict:
    print(f"[Notify] Cliente {customer_id} orden {order_id} -> {status}: {message}")
    return {"status": "logged_dev"}


@shared_task(name="app.tasks.notifications.notify_admin_payment_pending")
def notify_admin_payment_pending(payment_id: str, phase: str) -> dict:
    print(f"[Notify] Admin pago pendiente {payment_id} fase {phase}")
    return {"status": "logged_dev"}


@shared_task(name="app.tasks.notifications.notify_driver_reassigned")
def notify_driver_reassigned(driver_id: str, order_id: str, reason: str) -> dict:
    print(f"[Notify] Driver {driver_id} reasignado orden {order_id}: {reason}")
    return {"status": "logged_dev"}
