from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    is_seller = models.BooleanField(default=False)
    is_farmer = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    def role(self):
        if self.is_seller:
            return "Seller"
        elif self.is_farmer:
            return "Farmer"
        return "Unassigned"

    @staticmethod
    def get_or_create_profile(user):
        profile, _ = Profile.objects.get_or_create(user=user)
        return profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
