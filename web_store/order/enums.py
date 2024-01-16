from enum import Enum


class WebStoreOrderStatus(Enum):
    DRAFT = "draft"
    CANCELLED = "cancelled"


class WebStoreOrderWebhookEventType(Enum):
    ORDER_CANCELLED = "ORDER_CANCELLED"
