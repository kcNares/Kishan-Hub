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
from .models import ToolReview

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()


# 1. Bayesian Average Rating
# def compute_bayesian_average(tool, m=5):
#     """
#     Computes a smoothed rating using Bayesian average to avoid bias from low review counts.

#     Args:
#         tool: Tool instance
#         m: minimum reviews threshold weight

#     Returns:
#         Float: Bayesian average rating
#     """
#     all_reviews = ToolReview.objects.all()
#     C = all_reviews.aggregate(avg=Avg("rating"))["avg"] or 0  # Global average
#     v = tool.reviews.count()  # Number of reviews for this tool
#     R = tool.reviews.aggregate(avg=Avg("rating"))["avg"] or 0  # Tool's average

#     if v == 0:
#         return round(C, 1)

#     bayesian = (v / (v + m)) * R + (m / (v + m)) * C
#     return round(bayesian, 1)


# 2. Sentiment Mismatch Checker
def is_sentiment_mismatch(rating, comment):
    """
    Detects if the sentiment of the comment does not match the numeric rating.

    Returns:
        bool: True if mismatch found, else False
    """
    if not isinstance(comment, str) or not comment.strip():
        return False

    sentiment = sia.polarity_scores(comment)
    compound = sentiment["compound"]

    # Example thresholds (tune as needed)
    if rating >= 4 and compound < -0.3:
        return True
    if rating <= 2 and compound > 0.3:
        return True
    return False


# 3. Fake Review Detector (Per tool or globally)
def detect_fake_reviews(tool=None):
    reviews = (
        ToolReview.objects.filter(tool=tool) if tool else ToolReview.objects.all()
    ).order_by("pk")

    data = []
    valid_reviews = []

    for review in reviews:
        if review.rating is not None and review.comment:
            comment = review.comment.strip()
            sentiment = TextBlob(comment).sentiment.polarity  # -1 to 1
            length = len(comment)
            stars = review.rating

            # Collect data for ML model
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

        # Detect rating-sentiment mismatch:
        rating_sentiment_conflict = (
            stars <= 2 and sentiment > 0.5
        ) or (  # Low star, very positive sentiment
            stars >= 4 and sentiment < -0.3
        )  # High star, very negative sentiment

        # Flag if either model or heuristics detect suspicious:
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


# haversine formula
def haversine_distance(lat1, lon1, lat2, lon2):
    """
        Calculate the great-circle distance between two points on Earth.
        Returns distance in kilometers.
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    km = 6371 * c
    return km
