import uuid
from decimal import Decimal
from django.conf import settings
from kishan.utils import verify_esewa_payment
from kishan.models import Rental, Tool


class RentalService:
    @staticmethod
    def calculate_rental_cost(start, end, daily_rate):
        diff_hours = (end - start).total_seconds() / 3600
        hourly_rate = daily_rate / Decimal("24")
        if diff_hours <= 24:
            cost = min(daily_rate, Decimal(diff_hours) * hourly_rate)
        else:
            full_days = Decimal(diff_hours) // 24
            rem_hours = Decimal(diff_hours) % 24
            cost = full_days * daily_rate + min(daily_rate, rem_hours * hourly_rate)
        return cost.quantize(Decimal("0.00"))

    @staticmethod
    def prepare_esewa_payload(rental: Rental, amount: Decimal):
        rental.esewa_transaction_uuid = str(uuid.uuid4())
        rental.payment_method = "esewa"
        rental.status = "pending"
        rental.is_active = False
        rental.save()
        return {
            "esewa_url": settings.ESEWA_EPAY_URL,
            "txAmt": str(amount),
            "tAmt": str(amount),
            "psc": "0",
            "pdc": "0",
            "pid": rental.esewa_transaction_uuid,
            "scd": settings.ESEWA_PRODUCT_CODE,
            "su": settings.ESEWA_SUCCESS_URL,
            "fu": settings.ESEWA_FAILURE_URL,
        }

    @staticmethod
    def confirm_esewa_payment(rental: Rental):
        result = verify_esewa_payment(
            rental.esewa_transaction_uuid, str(rental.total_price)
        )
        if result.get("status") == "COMPLETE":
            rental.status = "paid"
            rental.paid_amount = rental.total_price
            rental.esewa_status = "success"
            rental.esewa_ref_id = result.get("ref_id", "")
            rental.is_active = True
            rental.tool.status = "unavailable"
            rental.tool.save()
        else:
            rental.status = "cancelled"
            rental.esewa_status = "failed"
            rental.is_active = False
        rental.save()
        return result
