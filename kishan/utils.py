from math import radians, cos, sin, asin, sqrt
import pandas as pd
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import re
import time
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from django.db.models import Avg

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()


def is_tool_available(tool, start_date, end_date):
    """
    Check if the tool is available for a date range.
    """
    has_conflict = (
        tool.rentals.filter(
            is_active=True,
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).exists()
        or tool.bookings.filter(
            status="confirmed",
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).exists()
    )
    return not has_conflict


# 1. Bayesian Average Rating
# def compute_bayesian_average(tool, m=5):
#     """
#     Computes a smoothed rating using Bayesian average to avoid bias from low review counts.
#     """
#     from kishan.models import ToolReview
#     all_reviews = ToolReview.objects.all()
#     C = all_reviews.aggregate(avg=Avg("rating"))["avg"] or 0  # Global average
#     v = tool.reviews.count()
#     R = tool.reviews.aggregate(avg=Avg("rating"))["avg"] or 0

#     if v == 0:
#         return round(C, 1)

#     bayesian = (v / (v + m)) * R + (m / (v + m)) * C
#     return round(bayesian, 1)


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


def do_geocode(location_name, geolocator, retries=3):
    for i in range(retries):
        try:
            return geolocator.geocode(location_name, timeout=5)
        except (GeocoderTimedOut, GeocoderUnavailable):
            time.sleep(1)
    return None


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
