from .models import Seller


def seller_context(request):
    if request.user.is_authenticated:
        seller = Seller.objects.filter(user=request.user).first()
    else:
        seller = None
    return {"seller": seller}
