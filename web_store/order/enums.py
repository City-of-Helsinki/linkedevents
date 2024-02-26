from enum import Enum


class WebStoreOrderStatus(Enum):
    DRAFT = "draft"
    CANCELLED = "cancelled"


class WebStoreOrderRefundStatus(Enum):
    CREATED = "refund_created"
    PAID_ONLINE = "refund_paid_online"
    CANCELLED = "refund_cancelled"


class WebStoreOrderWebhookEventType(Enum):
    ORDER_CANCELLED = "ORDER_CANCELLED"
