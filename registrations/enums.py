from decimal import Decimal
from enum import Enum


class VatPercentage(Enum):
    VAT_25_5 = Decimal("25.50")
    VAT_14 = Decimal("14.00")
    VAT_13_5 = Decimal("13.50")
    VAT_10 = Decimal("10.00")
    VAT_0 = Decimal("0.00")
