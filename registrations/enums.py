from decimal import Decimal
from enum import Enum


class VatPercentage(Enum):
    VAT_24 = Decimal("24.00")
    VAT_14 = Decimal("14.00")
    VAT_10 = Decimal("10.00")
    VAT_0 = Decimal("0.00")
