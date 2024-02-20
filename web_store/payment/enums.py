from enum import Enum


class WebStorePaymentStatus(Enum):
    CREATED = "payment_created"
    PAID = "payment_paid_online"
    CANCELLED = "payment_cancelled"


class WebStorePaymentWebhookEventType(Enum):
    PAYMENT_PAID = "PAYMENT_PAID"
    PAYMENT_CANCELLED = "PAYMENT_CANCELLED"
