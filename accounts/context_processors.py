from .models import Profile


def profile_processor(request):
    profile = None
    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).first()
    return {"profile": profile}
