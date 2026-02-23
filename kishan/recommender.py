from django.db.models import Count, Avg
from django.utils import timezone
from kishan.models import Tool, Rental, ToolReview
from accounts.models import Profile


# -----------------------------
# Popularity (most rented)
# -----------------------------
def get_popularity_scores(days=60):
    recent = timezone.now() - timezone.timedelta(days=days)
    rentals = (
        Rental.objects.filter(created_at__gte=recent)
        .values("tool_id")
        .annotate(cnt=Count("id"))
    )
    return {r["tool_id"]: r["cnt"] for r in rentals}


# -----------------------------
# Rating scores
# -----------------------------
def get_rating_scores():
    reviews = ToolReview.objects.values("tool_id").annotate(
        avg=Avg("rating"), cnt=Count("id")
    )
    scores = {}
    for r in reviews:
        scores[r["tool_id"]] = float(r["avg"] * max(1, r["cnt"]))  # weighted rating
    return scores


# -----------------------------
# Category similarity score
# -----------------------------
def get_category_score(tool, user_tools):
    user_categories = set(t.category_id for t in user_tools)
    return 3 if tool.category_id in user_categories else 0


# -----------------------------
# Main hybrid recommender
# -----------------------------
def recommend_tools(user, limit=4):
    tools = list(Tool.objects.filter(status="available"))
    if not tools:
        return []

    popularity = get_popularity_scores()
    ratings = get_rating_scores()
    final_scores = {}

    user_tools = None
    if user.is_authenticated and hasattr(user, "profile") and user.profile.is_farmer:
        user_tools = Tool.objects.filter(rentals__farmer=user.profile).distinct()

    for tool in tools:
        score = 0

        # Similar category bonus
        if user_tools and user_tools.exists():
            score += get_category_score(tool, user_tools) * 2.0

        # Rating contribution
        score += ratings.get(tool.id, 0) * 1.3

        # Popularity contribution
        score += popularity.get(tool.id, 0) * 1.1

        final_scores[tool.id] = score

    # Sort tools by hybrid score
    ranked_tools = sorted(tools, key=lambda t: final_scores.get(t.id, 0), reverse=True)

    # Decorate for frontend
    for tool in ranked_tools:
        avg_rating = ratings.get(tool.id, 0)
        tool.rating = round(avg_rating, 1)
        tool.rating_int = round(avg_rating)

        tool.reviews_count_runtime = (
            getattr(tool, "num_reviews", 0)
            or ToolReview.objects.filter(tool=tool).count()
        )

        # Star list
        stars = []
        for i in range(1, 6):
            if avg_rating >= i:
                stars.append("full")
            elif avg_rating + 0.5 >= i:
                stars.append("half")
            else:
                stars.append("empty")
        tool.star_list_runtime = stars

    return ranked_tools[:limit]
