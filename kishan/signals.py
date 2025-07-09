from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ToolReview
from .utils import is_sentiment_mismatch


@receiver(post_save, sender=ToolReview)
def flag_review_on_save(sender, instance, created, **kwargs):
    if created:
        mismatch = is_sentiment_mismatch(instance.comment or "", instance.rating)
        if mismatch or len(instance.comment or "") < 20:
            instance.is_flagged = True
            instance.save()
