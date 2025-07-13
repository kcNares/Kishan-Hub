import re
from django.forms import ValidationError
from django.views import View
from .forms import BookingForm, ToolReviewForm
from django.contrib import messages
from django.http import JsonResponse
from django.db import IntegrityError
from django.db.models import Avg, Count, Q
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView
from accounts.models import Profile
from .utils import haversine_distance, do_geocode, is_tool_available
from geopy.geocoders import Nominatim
from .models import Booking, Rental, Tool, Category, SearchQuery, ToolReview
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .utils import is_sentiment_mismatch, detect_fake_reviews
from django.views.generic import (
    ListView,
    TemplateView,
    CreateView,
    DeleteView
)


# Create your views here.
class HomeView(ListView):
    model = Tool
    template_name = "assets/home.html"
    context_object_name = "tools"

    def get_queryset(self):
        qs = (
            Tool.objects.filter(status="available")
            .annotate(
                reviews_count_annotated=Count("reviews"),
                avg_rating=Avg("reviews__rating"),  # Annotate average rating directly
            )
            .order_by("-created_at")[:6]
        )

        for tool in qs:
            rating = tool.avg_rating or 0  # Use annotated average or 0 if None
            tool.rating = round(rating, 1)
            tool.rating_int = round(rating)
            tool.reviews_count = tool.reviews_count_annotated or 0

            stars = []
            for i in range(1, 6):
                if rating >= i:
                    stars.append("full")
                elif rating + 0.5 >= i:
                    stars.append("half")
                else:
                    stars.append("empty")
            tool.star_list = stars

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        recommended_qs = (
            Tool.objects.filter(status="available")
            .annotate(
                reviews_count_annotated=Count("reviews"),
                avg_rating=Avg("reviews__rating"),
            )
            .order_by("-created_at")[:4]
        )

        for tool in recommended_qs:
            rating = tool.avg_rating or 0
            tool.rating = round(rating, 1)
            tool.rating_int = round(rating)
            tool.reviews_count = tool.reviews_count_annotated or 0

            stars = []
            for i in range(1, 6):
                if rating >= i:
                    stars.append("full")
                elif rating + 0.5 >= i:
                    stars.append("half")
                else:
                    stars.append("empty")
            tool.star_list = stars

        context["recommended_tools"] = recommended_qs
        context["stars_range"] = range(1, 6)
        return context


class AboutView(TemplateView):
    template_name = "assets/about.html"


class AllToolsView(ListView):
    model = Tool
    template_name = "assets/all_tools.html"
    context_object_name = "tools"
    paginate_by = 8

    def get_queryset(self):
        queryset = Tool.objects.filter(status="available").annotate(
            reviews_count_annotated=Count("reviews"),
            avg_rating=Avg("reviews__rating"),
        )

        category_id = self.request.GET.get("category")
        min_price = self.request.GET.get("min_price")
        max_price = self.request.GET.get("max_price")
        sort_by = self.request.GET.get("sort_by")

        # Filter by category using ID
        if category_id:
            queryset = queryset.filter(category__id=category_id)

        if min_price:
            queryset = queryset.filter(daily_rent_price__gte=min_price)

        if max_price:
            queryset = queryset.filter(daily_rent_price__lte=max_price)

        # Convert to list to add custom attributes
        tools = list(queryset)

        for tool in tools:
            rating = tool.avg_rating or 0
            tool.rating = round(rating, 1)
            tool.reviews_count = getattr(tool, "reviews_count_annotated", 0)

            stars = []
            for i in range(1, 6):
                if tool.rating >= i:
                    stars.append("full")
                elif tool.rating + 0.5 >= i:
                    stars.append("half")
                else:
                    stars.append("empty")
            tool.star_list = stars

        # Sorting logic
        if sort_by == "price_asc":
            tools.sort(key=lambda t: t.daily_rent_price)
        elif sort_by == "price_desc":
            tools.sort(key=lambda t: t.daily_rent_price, reverse=True)
        elif sort_by == "rating":
            tools.sort(key=lambda t: t.rating, reverse=True)
        elif sort_by == "newest":
            tools.sort(key=lambda t: t.created_at, reverse=True)

        return tools

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stars_range"] = range(1, 6)
        context["categories"] = Category.objects.all()
        context["selected_category"] = self.request.GET.get("category", "")
        context["min_price"] = self.request.GET.get("min_price", "")
        context["max_price"] = self.request.GET.get("max_price", "")
        context["sort_by"] = self.request.GET.get("sort_by", "")
        return context


# Search
class ToolSearchResultsView(ListView):
    model = Tool
    template_name = "assets/search_result.html"
    context_object_name = "tools"
    paginate_by = 6

    def get_queryset(self):
        query = self.request.GET.get("q", "").strip()

        if not query:
            return Tool.objects.none()

        # Save search query
        SearchQuery.objects.create(query=query)

        user = self.request.user

        # Anonymous users → skip location-based filtering
        if not user.is_authenticated:
            queryset = (
                Tool.objects.filter(name__icontains=query)
                .annotate(
                    reviews_count_annotated=Count("reviews"),
                    avg_rating=Avg("reviews__rating"),
                )
                .select_related("owner", "category")
                .distinct()
            )
            # annotate extra fields:
            for tool in queryset:
                tool.rating = round(tool.avg_rating or 0, 1)
                tool.reviews_count = getattr(tool, "reviews_count_annotated", 0)
                tool.star_list = self.build_star_list(tool.rating)
                seller = tool.owner
                tool.seller_name = seller.shop_name if seller else None
                tool.seller_location = seller.location_name if seller else None
            return queryset

        # Authenticated users:
        profile = Profile.get_or_create_profile(user)

        if not profile.location:
            messages.warning(
                self.request, "Please update your location in your profile first."
            )
            return Tool.objects.none()

        geolocator = Nominatim(user_agent="kishan_app")
        location = do_geocode(profile.location, geolocator)

        if not location:
            messages.error(
                self.request,
                "Could not find coordinates for your location.",
            )
            return Tool.objects.none()

        farmer_lat = location.latitude
        farmer_lon = location.longitude

        queryset = (
            Tool.objects.filter(name__icontains=query)
            .annotate(
                reviews_count_annotated=Count("reviews"),
                avg_rating=Avg("reviews__rating"),
            )
            .select_related("owner", "category")
            .distinct()
        )

        tools_within_radius = []
        for tool in queryset:
            seller = tool.owner
            if seller.latitude is None or seller.longitude is None:
                continue

            distance_km = haversine_distance(
                farmer_lat, farmer_lon, seller.latitude, seller.longitude
            )

            if distance_km <= 50:
                tools_within_radius.append(
                    {
                        "name": tool.name,
                        "seller_name": seller.shop_name,
                        "seller_location": seller.location_name,
                        "seller_lat": seller.latitude,
                        "seller_lon": seller.longitude,
                        "seller_distance": round(distance_km, 2),
                    }
                )

        # add computed fields for display:
        for tool in queryset:
            tool.rating = round(tool.avg_rating or 0, 1)
            tool.reviews_count = getattr(tool, "reviews_count_annotated", 0)
            tool.star_list = self.build_star_list(tool.rating)
            seller = tool.owner
            tool.seller_name = seller.shop_name if seller else None
            tool.seller_location = seller.location_name if seller else None

        # store context:
        self.tools_within_radius = tools_within_radius
        self.farmer_lat = farmer_lat
        self.farmer_lon = farmer_lon

        return queryset

    def build_star_list(self, rating):
        stars = []
        for i in range(1, 6):
            if rating >= i:
                stars.append("full")
            elif rating + 0.5 >= i:
                stars.append("half")
            else:
                stars.append("empty")
        return stars

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["tools_within_radius"] = getattr(self, "tools_within_radius", [])
        context["farmer_lat"] = getattr(self, "farmer_lat", None)
        context["farmer_lon"] = getattr(self, "farmer_lon", None)
        return context


class ToolAutocompleteView(View):
    def get(self, request):
        query = request.GET.get("q", "")
        suggestions = []
        if query:
            suggestions = (
                Tool.objects.filter(name__icontains=query)
                .values_list("name", flat=True)
                .distinct()[:10]
            )
        return JsonResponse(list(suggestions), safe=False)


class ToolDetailView(View):
    template_name = "assets/tool_details/tool_detail.html"

    def get(self, request, pk):
        return self.render_tool_detail(request, pk)

    def render_tool_detail(self, request, pk, form=None, edit_review_id=None):
        tool = get_object_or_404(Tool, pk=pk)
        reviews = ToolReview.objects.filter(tool=tool).order_by("-created_at")
        total_reviews = reviews.count()

        # Calculate average rating
        if total_reviews > 0:
            average_rating = round(reviews.aggregate(avg=Avg("rating"))["avg"], 1)
        else:
            average_rating = 0.0

        average_rating_int = round(average_rating)

        # Star rendering logic
        stars = []
        for i in range(1, 6):
            if average_rating >= i:
                stars.append("full")
            elif average_rating + 0.5 >= i:
                stars.append("half")
            else:
                stars.append("empty")

        # Rating breakdown calculation
        rating_breakdown = {
            i: (
                int((reviews.filter(rating=i).count() / total_reviews) * 100)
                if total_reviews
                else 0
            )
            for i in range(1, 6)
        }

        edit_review = None
        if edit_review_id and request.user.is_authenticated:
            try:
                edit_review = ToolReview.objects.get(
                    pk=edit_review_id, farmer__user=request.user
                )
                form = form or ToolReviewForm(instance=edit_review)
            except ToolReview.DoesNotExist:
                pass

        if not form:
            form = ToolReviewForm()

        context = {
            "tool": tool,
            "reviews": reviews,
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "average_rating_int": average_rating_int,
            "rating_breakdown": rating_breakdown,
            "edit_review": edit_review,
            "form": form,
            "weekly_price": tool.daily_rent_price * 6,
            "monthly_price": tool.daily_rent_price * 29,
            "related_tools": Tool.objects.exclude(pk=tool.pk)[:4],
            "star_list": stars,
        }
        return render(request, self.template_name, context)


class FarmerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return (
            self.request.user.is_authenticated
            and hasattr(self.request.user, "profile")
            and self.request.user.profile.is_farmer
        )


def is_valid_comment(comment):
    if not comment or len(comment.strip()) < 10:
        return False
    if re.fullmatch(r"[a-zA-Z]{3,6}", comment.strip()):
        return False  # Possibly gibberish
    return True


class ToolReviewCreateView(View):
    def post(self, request, pk):
        tool = get_object_or_404(Tool, pk=pk)

        if not request.user.is_authenticated:
            messages.error(request, "You must be logged in to submit a review.")
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        profile = getattr(request.user, "profile", None)
        if not profile or not profile.is_farmer:
            messages.error(request, "Only farmers can submit reviews.")
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        def is_nonsense(text):
            if not text:
                return True
            nonsense_pattern = re.compile(r"lorem ipsum|dolor sit amet|asdf|qwer", re.I)
            return bool(nonsense_pattern.search(text))

        edit_review_id = request.POST.get("edit_review_id")

        # Editing an existing review
        if edit_review_id:
            review = get_object_or_404(
                ToolReview, pk=edit_review_id, tool=tool, farmer=profile
            )
            form = ToolReviewForm(request.POST, instance=review)

            if form.is_valid():
                review = form.save(commit=False)

                # Validate comment
                if not is_valid_comment(review.comment):
                    messages.error(
                        request,
                        "Please provide a more meaningful and detailed comment.",
                    )
                    return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

                # Nonsense check — block saving nonsense review
                if is_nonsense(review.comment):
                    messages.error(
                        request,
                        "Your review looks like nonsense or placeholder text. Please provide a meaningful review.",
                    )
                    return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

                # Sentiment mismatch
                if is_sentiment_mismatch(review.rating, review.comment):
                    messages.error(
                        request,
                        "Your rating and comment don't seem to match in sentiment. Please revise your review.",
                    )
                    return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

                review.is_sentiment_mismatch = False
                review.save()

                detect_fake_reviews(tool=tool)
                review.refresh_from_db()

                if review.is_flagged:
                    review.delete()
                    messages.error(
                        request,
                        "Your review looks suspicious and may be fake. Please revise it.",
                    )
                else:
                    messages.success(
                        request, "Your review has been updated successfully."
                    )
            else:
                messages.error(request, "Please correct the errors in your review.")

            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        # Creating a new review
        else:
            if ToolReview.objects.filter(tool=tool, farmer=profile).exists():
                messages.error(
                    request, "You have already submitted a review for this tool."
                )
                return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

            form = ToolReviewForm(request.POST)

            if form.is_valid():
                review = form.save(commit=False)
                review.tool = tool
                review.farmer = profile

                # Validate comment
                if not is_valid_comment(review.comment):
                    messages.error(
                        request,
                        "Please provide a more meaningful and detailed comment.",
                    )
                    return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

                # Nonsense check — block saving nonsense review
                if is_nonsense(review.comment):
                    messages.error(
                        request,
                        "Your review looks like nonsense or placeholder text. Please provide a meaningful review.",
                    )
                    return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

                # Sentiment mismatch
                if is_sentiment_mismatch(review.rating, review.comment):
                    messages.error(
                        request,
                        "Your rating and comment don't seem to match in sentiment. Please revise your review.",
                    )
                    return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

                review.is_sentiment_mismatch = False

                try:
                    review.save()
                    detect_fake_reviews(tool=tool)
                    review.refresh_from_db()

                    if review.is_flagged:
                        review.delete()
                        messages.error(
                            request,
                            "Your review looks suspicious and may be fake. Please revise it.",
                        )
                    else:
                        messages.success(
                            request, "Thank you for submitting your review!"
                        )
                except IntegrityError:
                    messages.error(
                        request, "You have already submitted a review for this tool."
                    )
            else:
                messages.error(request, "Please provide meaningful review.")

            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))


class UserIsOwnerMixin(UserPassesTestMixin):
    def test_func(self):
        review = self.get_object()
        return self.request.user == review.farmer.user


class DeleteReviewView(LoginRequiredMixin, UserIsOwnerMixin, DeleteView):
    model = ToolReview

    def get_success_url(self):
        return reverse_lazy("tool-detail", kwargs={"pk": self.object.tool.pk})


# Bookings and Rent
class BookingCreateView(LoginRequiredMixin, CreateView):
    model = Booking
    form_class = BookingForm
    template_name = "assets/bookings/booking.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Works for both GET (opening modal) and POST (submitting form)
        tool_id = self.request.GET.get("tool_id") or self.request.POST.get("tool")
        tool = None
        hourly_rate = 0.0

        if tool_id:
            tool = get_object_or_404(Tool, id=tool_id)
            if tool.daily_rent_price:
                hourly_rate = tool.daily_rent_price / 24

            # Check if the user already has a booking for this tool
            existing_booking = Booking.objects.filter(
                farmer=self.request.user.profile, tool=tool
            ).first()

            context["booking"] = existing_booking

        context["tool"] = tool
        context["hourly_rate"] = hourly_rate
        return context

    def form_valid(self, form):
        tool = form.cleaned_data["tool"]
        farmer = self.request.user.profile

        # Check if an existing booking already exists for this user/tool
        existing_booking = Booking.objects.filter(farmer=farmer, tool=tool).first()

        if existing_booking:
            # Optional: show message
            messages.info(
                self.request,
                f"You already have a booking for this tool in '{existing_booking.get_status_display()}' status.",
            )
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        form.instance.farmer = farmer
        form.instance.status = "pending"
        return super().form_valid(form)

    def get_success_url(self):
        tool_id = self.object.tool.id
        return reverse("tool-detail", kwargs={"pk": tool_id})
