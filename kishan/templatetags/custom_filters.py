from django import template

register = template.Library()


@register.filter
def get_rating_count(reviews, star):
    """Return the number of reviews with a given star rating (as string or int)."""
    return reviews.filter(rating=int(star)).count()


@register.filter
def percentage(value, total):
    """Return percentage as integer."""
    try:
        return round((value / total) * 100)
    except (ZeroDivisionError, TypeError):
        return 0
