from math import radians, cos, sin, asin, sqrt
import pandas as pd
import re, requests
import time
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from django.db.models import Q
from kishan.models import Booking, Rental
from django.utils import timezone
import hmac, hashlib, base64, requests, json
from django.conf import settings
from decimal import Decimal
from typing import Tuple
from typing import Dict

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()


# Dijkstra's Algorithm" or "Quicksort
# def is_tool_available(
#     tool, start_date, end_date, exclude_booking_id=None, exclude_rental_id=None
# ):
#     """
#     Check whether the given tool is available for the provided start_date and end_date.
#     Excludes a specific booking or rental by ID if provided (useful for updates).

#     Rules:
#     - Bookings with status 'pending' or 'confirmed' block availability.
#     - Rentals block availability if is_active=True, regardless of payment status.
#     - Cancelled bookings or inactive rentals do not block availability.
#     """

#     # Check booking conflicts
#     booking_conflicts = (
#         Booking.objects.filter(tool=tool)
#         .exclude(id=exclude_booking_id)
#         .filter(status__in=["pending", "confirmed"])
#         .filter(Q(start_date__lt=end_date) & Q(end_date__gt=start_date))
#         .exists()
#     )

#     # Check rental conflicts (active rentals only)
#     rental_conflicts = (
#         Rental.objects.filter(tool=tool, is_active=True)
#         .exclude(id=exclude_rental_id)
#         .filter(Q(start_date__lt=end_date) & Q(end_date__gt=start_date))
#         .exists()
#     )

#     # Tool is available if no conflicts exist
#     return not (booking_conflicts or rental_conflicts)


def _aware(dt):
    if dt is None:
        return None
    # Make sure datetimes are timezone-aware
    from django.utils import timezone as tz

    return dt if tz.is_aware(dt) else tz.make_aware(dt)


def _overlap_q(start, end):
    # Overlap if NOT (existing.end <= start OR existing.start >= end)
    return Q(start_date__lt=end) & Q(end_date__gt=start)


def is_tool_available(
    tool, start, end, *, exclude_rental_id=None, exclude_booking_id=None
):
    """
    Returns True if the tool has no blocking rentals/bookings that overlap [start, end].
    """
    start = _aware(start)
    end = _aware(end)
    now = timezone.now()

    # Block by active rentals (COD 'rented' or eSewa 'paid')
    rental_q = tool.rentals.filter(
        is_active=True,
        status__in=["rented", "paid"],
    )
    if exclude_rental_id:
        rental_q = rental_q.exclude(pk=exclude_rental_id)
    rental_conflict = rental_q.filter(_overlap_q(start, end)).exists()

    # Block by (pending or confirmed) bookings in the same window
    booking_q = tool.bookings.filter(
        status__in=["pending", "confirmed"],
    )
    if exclude_booking_id:
        booking_q = booking_q.exclude(pk=exclude_booking_id)
    booking_conflict = booking_q.filter(_overlap_q(start, end)).exists()

    return not (rental_conflict or booking_conflict)




# 2. Sentiment Mismatch Checker
def is_sentiment_mismatch(rating, comment):
    if not isinstance(comment, str) or not comment.strip():
        return False

    sentiment = sia.polarity_scores(comment)
    compound = sentiment["compound"]

    if rating >= 4 and compound < -0.3:
        return True
    if rating <= 2 and compound > 0.3:
        return True
    return False


# 3. Fake Review Detector
def detect_fake_reviews(tool=None):
    from kishan.models import ToolReview

    reviews = (
        ToolReview.objects.filter(tool=tool) if tool else ToolReview.objects.all()
    ).order_by("pk")

    data = []
    valid_reviews = []

    for review in reviews:
        if review.rating is not None and review.comment:
            comment = review.comment.strip()
            sentiment = TextBlob(comment).sentiment.polarity
            length = len(comment)
            stars = review.rating

            data.append(
                {
                    "length": length,
                    "stars": stars,
                    "sentiment": sentiment,
                }
            )
            valid_reviews.append(review)

    if not data:
        return

    df = pd.DataFrame(data)
    scaler = StandardScaler()
    df_scaled = scaler.fit_transform(df[["length", "stars", "sentiment"]])

    clf = IsolationForest(contamination=0.2, random_state=42)
    preds = clf.fit_predict(df_scaled)

    nonsense_pattern = re.compile(r"lorem ipsum|dolor sit amet|asdf|qwer", re.I)

    for i, review in enumerate(valid_reviews):
        comment = review.comment.strip()
        stars = review.rating
        sentiment = data[i]["sentiment"]

        is_nonsense = bool(nonsense_pattern.search(comment))

        rating_sentiment_conflict = (stars <= 2 and sentiment > 0.5) or (
            stars >= 4 and sentiment < -0.3
        )

        review.is_flagged = preds[i] == -1 or is_nonsense or rating_sentiment_conflict

        print(
            f"[DEBUG] Review ID={review.id} | Stars={stars} | Len={len(comment)} "
            f"| Sentiment={sentiment:.2f} | Nonsense={is_nonsense} "
            f"| Rating-Sentiment Conflict={rating_sentiment_conflict} "
            f"| Flagged={review.is_flagged}"
        )

    ToolReview.objects.bulk_update(valid_reviews, ["is_flagged"])


# Haversine formula
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on Earth in kilometers.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    km = 6371 * c
    return km


# For eSewa implementation
def generate_esewa_signature(
    total_amount: str, transaction_uuid: str, product_code: str, secret_key: str
) -> str:
    """
    Generate an eSewa HMAC-SHA256 signature (Base64-encoded).

    According to eSewa docs (v2 API):
      Message format:
        "total_amount=<total_amount>,transaction_uuid=<transaction_uuid>,product_code=<product_code>"

    Args:
        total_amount (str): The total payable amount as string (e.g. "195.00").
        transaction_uuid (str): Unique identifier for this transaction (UUID).
        product_code (str): Your merchant/product code (e.g. "EPAYTEST").
        secret_key (str): Your eSewa secret key.

    Returns:
        str: Base64-encoded HMAC-SHA256 signature.
    """
    message = (
        f"total_amount={total_amount},"
        f"transaction_uuid={transaction_uuid},"
        f"product_code={product_code}"
    )

    digest = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return base64.b64encode(digest).decode("utf-8")


def verify_esewa_response_signature(
    response_dict: Dict[str, str], secret_key: str
) -> bool:
    """
    Verify an eSewa response signature.

    eSewa includes two fields in its response:
      - "signed_field_names": Comma-separated list of fields that were signed.
      - "signature": The Base64 HMAC-SHA256 signature.

    Steps:
      1. Build a message string:
           "<name>=<value>,<name>=<value>,..."
         using the fields in the order specified by signed_field_names.
      2. Compute HMAC-SHA256(secret_key, message).
      3. Compare against the provided "signature".

    Args:
        response_dict (Dict[str, str]): The parsed JSON response from eSewa.
        secret_key (str): Your eSewa secret key.

    Returns:
        bool: True if signature matches, False otherwise.
    """
    signed_field_names = response_dict.get("signed_field_names", "")
    if not signed_field_names:
        return False

    names = [n.strip() for n in signed_field_names.split(",") if n.strip()]
    parts = []

    for n in names:
        v = str(response_dict.get(n, ""))  # ensure string conversion
        parts.append(f"{n}={v}")

    message = ",".join(parts)

    digest = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    expected = base64.b64encode(digest).decode("utf-8")
    actual = response_dict.get("signature", "")

    # Use constant-time comparison to avoid timing attacks
    return hmac.compare_digest(expected, actual)


def verify_esewa_payment(transaction_uuid: str, amount: str) -> dict:
    """
    Verify payment status from eSewa using its status API.

    Args:
        transaction_uuid (str): The UUID (pid) used for the transaction.
        amount (str): The total amount paid.

    Returns:
        dict: The parsed JSON response from eSewa.
              Example:
              {
                "status": "COMPLETE",
                "ref_id": "000ABC123",
                "transaction_uuid": "uuid-123",
                "product_code": "EPAYTEST",
                ...
              }
    """
    from django.conf import settings

    url = settings.ESEWA_STATUS_URL
    payload = {
        "product_code": settings.ESEWA_PRODUCT_CODE,
        "total_amount": amount,
        "transaction_uuid": transaction_uuid,
    }

    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        return {"error": str(e), "status": "FAILED"}
