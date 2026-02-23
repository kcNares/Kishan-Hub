import re
import uuid
import logging
import json, base64, requests
from django.conf import settings
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.forms import ValidationError
from django.views import View
from django.utils.timezone import now
from seller.models import Seller
from .forms import BookingForm, RentalForm, ToolReviewForm, ContactForm
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.db import IntegrityError
from django.db.models import Avg, Count, Q
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView
from accounts.models import Profile
from django.utils.dateparse import parse_datetime
from geopy.geocoders import Nominatim
from .models import Booking, Notification, Rental, Tool, Category, SearchQuery, ToolReview
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .utils import (
    haversine_distance, 
    is_tool_available,
    is_sentiment_mismatch,
    detect_fake_reviews,
    generate_esewa_signature,
    verify_esewa_response_signature,
    verify_esewa_payment,
)
from django.views.generic import (
    ListView,
    TemplateView,
    CreateView,
    DeleteView,
    DetailView,
    FormView,
)
logger = logging.getLogger(__name__)
from .recommender import recommend_tools


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
                avg_rating=Avg("reviews__rating"),
            )
            .order_by("-created_at")[:6]
        )

        for tool in qs:
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

        return qs

    # ---------------------------
    # Context for recommended tools + shops
    # ---------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        recommended_qs = []

        # ---------------------------
        # Popularity (most rented)
        # ---------------------------
        popularity = {
            r["tool_id"]: r["cnt"]
            for r in Rental.objects.values("tool_id").annotate(cnt=Count("id"))
        }

        if (
            user.is_authenticated
            and hasattr(user, "profile")
            and user.profile.is_farmer
        ):
            profile = user.profile
            user_tools = Tool.objects.filter(rentals__farmer=profile).distinct()

            all_tools = Tool.objects.filter(status="available").annotate(
                avg_rating=Avg("reviews__rating"),
                reviews_count_annotated=Count("reviews"),
                popularity=Count("rentals"),
            )

            tool_scores = []
            for tool in all_tools:
                score = 0

                # Similar category
                if tool.category_id in user_tools.values_list("category_id", flat=True):
                    score += 3

                # Rating + review count
                score += (tool.avg_rating or 0) * 2.0
                score += (tool.reviews_count_annotated or 0) * 0.5

                # Popularity
                score += tool.popularity * 1.2

                tool_scores.append((score, tool))

            tool_scores.sort(key=lambda x: x[0], reverse=True)
            recommended_qs = [tool for _, tool in tool_scores[:4]]

        if not recommended_qs:
            rated_tools = list(
                Tool.objects.filter(
                    status="available",
                    reviews__rating__isnull=False,
                )
                .annotate(
                    avg_rating=Avg("reviews__rating"),
                    reviews_count_annotated=Count("reviews"),
                    popularity=Count("rentals"),
                )
                .order_by(
                    "-avg_rating",
                    "-reviews_count_annotated",
                    "-popularity",
                )
                .distinct()[:4]
            )

            if len(rated_tools) < 4:
                remaining = 4 - len(rated_tools)
                extra = list(
                    Tool.objects.filter(status="available")
                    .exclude(id__in=[t.id for t in rated_tools])
                    .annotate(popularity=Count("rentals"))
                    .order_by("-popularity")[:remaining]
                )
                rated_tools.extend(extra)

            recommended_qs = rated_tools

        for tool in recommended_qs:
            rating = getattr(tool, "avg_rating", 0) or 0
            tool.rating = round(rating, 1)
            tool.rating_int = round(rating)

            tool.reviews_count_runtime = (
                getattr(tool, "reviews_count_annotated", 0)
                or ToolReview.objects.filter(tool=tool).count()
            )

            # star icons
            stars = []
            for i in range(1, 6):
                if rating >= i:
                    stars.append("full")
                elif rating + 0.5 >= i:
                    stars.append("half")
                else:
                    stars.append("empty")
            tool.star_list_runtime = stars

            # badges
            badges = []

            # Only show "Similar Category" if farmer has rented tools
            if (
                user.is_authenticated
                and hasattr(user, "profile")
                and user.profile.is_farmer
            ):
                user_tools = Tool.objects.filter(
                    rentals__farmer=user.profile
                ).distinct()

                if user_tools.exists():  # must have rented at least one tool
                    if tool.category_id in user_tools.values_list(
                        "category_id", flat=True
                    ):
                        badges.append("Similar Category")

            # existing unchanged logic
            if rating >= 4.5:
                badges.append("Top Rated")

            if popularity.get(tool.id, 0) >= 5:
                badges.append("Most Rented")

            tool.badges = badges

        context["recommended_tools"] = recommended_qs
        context["stars_range"] = range(1, 6)

        try:
            user_lat = float(self.request.GET.get("lat"))
            user_lon = float(self.request.GET.get("lon"))
        except (TypeError, ValueError):
            user_lat = None
            user_lon = None

        shops = Seller.objects.filter(latitude__isnull=False, longitude__isnull=False)
        shops_with_distance = []

        for shop in shops:
            dist = (
                haversine_distance(user_lat, user_lon, shop.latitude, shop.longitude)
                if user_lat and user_lon
                else None
            )
            shops_with_distance.append(
                {
                    "id": shop.id,
                    "shop_name": shop.shop_name,
                    "location_name": shop.location_name,
                    "latitude": shop.latitude,
                    "longitude": shop.longitude,
                    "distance_km": round(dist, 2) if dist else None,
                }
            )

        if user_lat and user_lon:
            shops_with_distance.sort(key=lambda x: x["distance_km"])

        context["shops"] = shops_with_distance
        context["user_lat"] = user_lat
        context["user_lon"] = user_lon

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
        now = timezone.now()

        # --- Reviews ---
        reviews = ToolReview.objects.filter(tool=tool).order_by("-created_at")
        total_reviews = reviews.count()
        average_rating = round(reviews.aggregate(avg=Avg("rating"))["avg"] or 0.0, 1)

        # Stars
        stars = []
        for i in range(1, 6):
            if average_rating >= i:
                stars.append("full")
            elif average_rating + 0.5 >= i:
                stars.append("half")
            else:
                stars.append("empty")

        # Review form
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

        # --- CURRENT RENTAL: any active/future rental ---
        current_rental = (
            Rental.objects.filter(
                tool=tool,
                end_date__gte=now,
                status__in=["paid", "pending", "rented"],
                is_active=True,
            )
            .order_by("start_date")
            .first()
        )

        # --- BOOKINGS ---
        pending_booking = (
            Booking.objects.filter(tool=tool, status="pending", end_date__gte=now)
            .order_by("start_date")
            .first()
        )
        confirmed_booking = (
            Booking.objects.filter(tool=tool, status="confirmed", end_date__gte=now)
            .order_by("start_date")
            .first()
        )

        # --- TOOL STATUS LIST ---
        tool_status_list = []
        if current_rental:
            tool_status_list.append(
                {
                    "label": "Rented",
                    "badge": "danger",
                    "start_date": current_rental.start_date,
                    "end_date": current_rental.end_date,
                }
            )
        if pending_booking:
            tool_status_list.append(
                {
                    "label": "Pending",
                    "badge": "warning",
                    "start_date": pending_booking.start_date,
                    "end_date": pending_booking.end_date,
                }
            )
        if confirmed_booking:
            tool_status_list.append(
                {
                    "label": "Booked",
                    "badge": "primary",
                    "start_date": confirmed_booking.start_date,
                    "end_date": confirmed_booking.end_date,
                }
            )
        if not tool_status_list:
            tool_status_list.append(
                {
                    "label": "Available",
                    "badge": "success",
                    "start_date": None,
                    "end_date": None,
                }
            )

        context = {
            "tool": tool,
            "reviews": reviews,
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "star_list": stars,
            "form": form,
            "weekly_price": tool.daily_rent_price * 6,
            "monthly_price": tool.daily_rent_price * 29,
            "tool_status_list": tool_status_list,
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
    login_url = "farmer-login"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(self.login_url)

        if not hasattr(request.user, "profile") or not request.user.profile.is_farmer:
            messages.error(request, "You must have a farmer account to book tools.")
            return redirect(self.login_url)

        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if hasattr(self.request.user, "profile") and self.request.user.profile.location:
            form.fields["delivery_address"].initial = self.request.user.profile.location
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tool_id = self.request.GET.get("tool_id") or self.request.POST.get("tool")
        tool = None
        hourly_rate = 0.0

        if tool_id:
            tool = get_object_or_404(Tool, id=tool_id)
            if tool.daily_rent_price:
                hourly_rate = tool.daily_rent_price / 24

            existing_booking = Booking.objects.filter(
                farmer=self.request.user.profile,
                tool=tool,
                status__in=["pending", "confirmed"],
            ).first()
            context["booking"] = existing_booking

        context["tool"] = tool
        context["hourly_rate"] = hourly_rate
        return context

    def form_valid(self, form):
        tool = form.cleaned_data["tool"]
        farmer = self.request.user.profile
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")
        now = timezone.now()

        if start_date < now or end_date < now:
            messages.error(
                self.request, "You cannot book tools for a past date or time."
            )
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        # Prevent booking during a rental period
        overlapping_rental = (
            Rental.objects.filter(
                tool=tool,
                start_date__lt=end_date,
                end_date__gt=start_date,
                is_active=True,
            )
            .exclude(status__in=["cancelled", "returned"])
            .exists()
        )

        if overlapping_rental:
            messages.error(
                self.request,
                "You cannot book this tool during this period because it is already rented.",
            )
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        # Prevent overlapping with existing bookings
        if not is_tool_available(tool, start_date, end_date):
            messages.error(
                self.request,
                "The tool is not available for the selected dates and times.",
            )
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        existing_booking = Booking.objects.filter(
            farmer=farmer, tool=tool, status__in=["pending", "confirmed"]
        ).first()
        if existing_booking:
            messages.info(
                self.request,
                f"You already have a booking for this tool in '{existing_booking.get_status_display()}' status.",
            )
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        form.instance.farmer = farmer
        form.instance.status = "pending"
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tool-detail", kwargs={"pk": self.object.tool.id})


class ToolAvailabilityCheckView(View):
    def get(self, request, *args, **kwargs):
        tool_id = request.GET.get("tool_id")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if not (tool_id and start_date and end_date):
            return JsonResponse({"available": False, "error": "Missing data"}, status=400)

        try:
            tool = Tool.objects.get(id=tool_id)
        except Tool.DoesNotExist:
            return JsonResponse({"available": False, "error": "Tool not found"}, status=404)

        start_dt = parse_datetime(start_date)
        end_dt = parse_datetime(end_date)

        if not (start_dt and end_dt):
            return JsonResponse({"available": False, "error": "Invalid dates"}, status=400)

        # Check for booking conflicts
        conflicts = (
            Booking.objects.filter(tool=tool, status__in=["pending", "confirmed"])
            .filter(Q(start_date__lt=end_dt) & Q(end_date__gt=start_dt))
            .first()
        )

        if conflicts:
            return JsonResponse({"available": False, "status": conflicts.status, "type": "booking"})

        # Check rental conflicts
        rental_conflict = (
            Rental.objects.filter(
                tool=tool,
                is_active=True,
                start_date__lt=end_dt,
                end_date__gt=start_dt,
            )
            .exclude(status__in=["cancelled", "returned"])
            .first()
        )

        if rental_conflict:
            return JsonResponse(
                {
                    "available": False,
                    "status": rental_conflict.status,
                    "type": "rental",
                }
            )

        return JsonResponse({"available": True})


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, notif_id):
        notif = get_object_or_404(Notification, id=notif_id, user=request.user)
        notif.read = True
        notif.save()
        return redirect(notif.url or "/")


class NotificationRedirectView(View):
    def get(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, user=request.user)
        notif.read = True
        notif.save()
        return redirect(notif.url or "/")


class BookingNotifier:
    @classmethod
    def notify_upcoming_bookings(cls):
        now = timezone.now()
        window_start = now
        window_end = now + timedelta(
            minutes=5
        )  # Look for bookings starting within next 5 minutes

        bookings = Booking.objects.filter(
            start_date__gte=window_start,
            start_date__lt=window_end,
            status="confirmed",
            reminder_sent=False,  # Only notify once
        )

        for booking in bookings:
            Notification.objects.create(
                user=booking.farmer.user,
                message=f"Reminder: Your booking for {booking.tool.name} starts in 5 minutes.",
                url=f"/tool/{booking.tool.pk}/",  # Direct link to tool detail page
                booking=booking,
            )
            booking.reminder_sent = True
            booking.save(update_fields=["reminder_sent"])


@shared_task
def notify_upcoming_bookings():
    BookingNotifier.notify_upcoming_bookings()


class RentToolView(LoginRequiredMixin, View):
    login_url = "farmer-login"
    template_name = "assets/bookings/rent.html"

    # -------------------------
    # Calculate cost
    # -------------------------
    def calculate_rental_cost(self, start, end, daily_rate):
        diff_hours = (end - start).total_seconds() / 3600
        hourly_rate = daily_rate / Decimal("24")
        if diff_hours <= 24:
            cost = min(daily_rate, Decimal(diff_hours) * hourly_rate)
        else:
            full_days = Decimal(diff_hours) // 24
            rem_hours = Decimal(diff_hours) % 24
            cost = full_days * daily_rate + min(daily_rate, rem_hours * hourly_rate)
        return cost.quantize(Decimal("0.00"))

    # -------------------------
    # GET
    # -------------------------
    def get(self, request, tool_id):
        tool = get_object_or_404(Tool, id=tool_id)
        form = RentalForm()

        active_rental = (
            Rental.objects.filter(
                tool=tool,
                is_active=True,
            )
            .order_by("-id")
            .first()
        )

        if active_rental:
            tool_status = {
                "label": "Rented",
                "badge": "danger",
                "start_date": active_rental.start_date,
                "end_date": active_rental.end_date,
                "extend_date": active_rental.extend_date,
                "renter_id": active_rental.farmer.user.id,
            }
        else:
            tool_status = {
                "label": "Available",
                "badge": "success",
                "start_date": None,
                "end_date": None,
                "extend_date": None,
                "renter_id": None,
            }

        return render(
            request,
            self.template_name,
            {
                "tool": tool,
                "form": form,
                "tool_status_list": [tool_status],
            },
        )

    # -------------------------
    # POST
    # -------------------------
    def post(self, request, tool_id):
        tool = get_object_or_404(Tool, id=tool_id)

        farmer_profile = Profile.objects.get(user=request.user, is_farmer=True)

        current_rental = (
            Rental.objects.filter(
                tool=tool,
                is_active=True,
                farmer=farmer_profile,
            )
            .order_by("-id")
            .first()
        )

        # -----------------------------
        # EXTEND
        # -----------------------------
        if current_rental and not current_rental.extend_date:

            extend_date_str = request.POST.get("extend_date")
            payment_method = request.POST.get("payment_method")

            if not extend_date_str or not payment_method:
                messages.error(request, "Select extension date and payment method.")
                return redirect(request.path)

            new_end_date = datetime.strptime(extend_date_str, "%Y-%m-%dT%H:%M")

            if timezone.is_naive(new_end_date):
                new_end_date = timezone.make_aware(new_end_date)

            if new_end_date <= current_rental.end_date:
                messages.error(request, "New end date must be after existing end date.")
                return redirect(request.path)

            # Calculate extra cost
            extra_cost = self.calculate_rental_cost(
                current_rental.end_date,
                new_end_date,
                tool.daily_rent_price,
            )

            # Save extension data (no overwrite)
            current_rental.extend_date = new_end_date
            current_rental.total_price += extra_cost
            current_rental.save()

            if payment_method == "cash":
                messages.success(request, "Extension added. Pay on delivery.")
                return redirect("rental-cod-success", pk=current_rental.pk)

            # eSewa
            current_rental.payment_method = "esewa"
            current_rental.status = "pending"
            current_rental.is_active = False
            current_rental.esewa_transaction_uuid = str(uuid.uuid4())
            current_rental.save()

            context = {
                "esewa_url": settings.ESEWA_EPAY_URL,
                "txAmt": str(extra_cost),
                "tAmt": str(extra_cost),
                "psc": "0",
                "pdc": "0",
                "pid": current_rental.esewa_transaction_uuid,
                "scd": settings.ESEWA_PRODUCT_CODE,
                "su": settings.ESEWA_SUCCESS_URL,
                "fu": settings.ESEWA_FAILURE_URL,
            }
            return render(request, "assets/bookings/esewa_redirect.html", context)

        # -----------------------------
        # NEW RENTAL
        # -----------------------------
        form = RentalForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please fix errors.")
            return redirect(request.path)

        start_date = form.cleaned_data["start_date"]
        end_date = form.cleaned_data["end_date"]
        payment_method = form.cleaned_data["payment_method"]

        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        rental_cost = self.calculate_rental_cost(
            start_date, end_date, tool.daily_rent_price
        )

        rental = form.save(commit=False)
        rental.tool = tool
        rental.farmer = farmer_profile
        rental.total_price = rental_cost
        rental.delivery_charge = Decimal("0.00")
        rental.paid_amount = Decimal("0.00")
        rental.extend_date = None
        rental.is_active = payment_method != "esewa"
        rental.status = "pending"
        rental.esewa_transaction_uuid = str(uuid.uuid4())
        rental.save()

        if payment_method == "cash":
            messages.success(request, "Rental created. Pay on delivery.")
            return redirect("rental-cod-success", pk=rental.pk)

        context = {
            "esewa_url": settings.ESEWA_EPAY_URL,
            "txAmt": str(rental_cost),
            "tAmt": str(rental_cost),
            "psc": "0",
            "pdc": "0",
            "pid": rental.esewa_transaction_uuid,
            "scd": settings.ESEWA_PRODUCT_CODE,
            "su": settings.ESEWA_SUCCESS_URL,
            "fu": settings.ESEWA_FAILURE_URL,
        }
        return render(request, "assets/bookings/esewa_redirect.html", context)


# --- eSewa Success / Failure Views ---
class EsewaSuccessView(View):
    def get(self, request):
        pid = request.GET.get("pid")
        refId = request.GET.get("refId")

        try:
            rental = Rental.objects.get(esewa_transaction_uuid=pid)
        except Rental.DoesNotExist:
            messages.error(request, "Rental not found.")
            return redirect("home")

        # Confirm payment only here
        rental.paid_amount = rental.total_price
        rental.esewa_status = "success"
        rental.esewa_ref_id = refId or ""
        rental.status = "rented"
        rental.is_active = True  # Activate the tool only now
        rental.save()

        messages.success(request, "Payment successful. Rental is now active.")
        return redirect("rental-success", pk=rental.pk)


class EsewaFailureView(View):
    def get(self, request):
        pid = request.GET.get("pid")
        try:
            rental = Rental.objects.get(esewa_transaction_uuid=pid)
            # Reset so tool becomes available again
            rental.esewa_status = "failed"
            rental.status = "cancelled"
            rental.is_active = False
            rental.save()
        except Rental.DoesNotExist:
            pass

        messages.error(request, "Payment failed or cancelled.")
        return redirect("tool-list")


# ----------------- COD SUCCESS -----------------
class RentalCODSuccessView(TemplateView):
    template_name = "assets/bookings/rental_success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rental_pk = self.kwargs.get("pk")
        rental = get_object_or_404(Rental, pk=rental_pk)
        context["rental"] = rental
        return context


# ----------------- eSewa SUCCESS -----------------
class RentalEsewaSuccessView(TemplateView):
    template_name = "assets/bookings/rental_success.html"

    def get(self, request, *args, **kwargs):
        rental_pk = self.kwargs.get("pk")
        rental = get_object_or_404(Rental, pk=rental_pk)

        # TODO: add eSewa payment verification here
        with transaction.atomic():
            Tool.objects.select_for_update().get(pk=rental.tool.pk)
            rental.status = "paid"
            rental.paid_amount = rental.total_price
            rental.save()

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rental_pk = self.kwargs.get("pk")
        rental = get_object_or_404(Rental, pk=rental_pk)
        context["rental"] = rental
        return context

    template_name = "assets/bookings/rental_success.html"

    def get(self, request, *args, **kwargs):
        rental_pk = self.kwargs.get("pk")
        rental = get_object_or_404(Rental, pk=rental_pk)

        # TODO: verify eSewa payment here (signature/transaction check)
        with transaction.atomic():
            # Lock tool to avoid races
            Tool.objects.select_for_update().get(pk=rental.tool.pk)

            rental.status = "paid"
            rental.paid_amount = rental.total_price
            rental.save()

            rental.tool.status = "unavailable"
            rental.tool.save()

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rental_pk = self.kwargs.get("pk")
        rental = get_object_or_404(Rental, pk=rental_pk)
        context["rental"] = rental
        return context


class BookAndRentListView(LoginRequiredMixin, TemplateView):
    template_name = "assets/book_and_rent_list.html"
    login_url = "farmer-login"

    def dispatch(self, request, *args, **kwargs):
        # Ensure only farmers can access
        if not hasattr(request.user, "profile") or not request.user.profile.is_farmer:
            messages.error(
                request, "You must be a farmer to view your bookings and rentals."
            )
            return redirect("farmer-login")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        farmer = self.request.user.profile

        # Separate booked and rented tools
        context["booked_tools"] = (
            Booking.objects.filter(farmer=farmer)
            .select_related("tool")
            .order_by("-created_at")
        )
        context["rented_tools"] = (
            Rental.objects.filter(farmer=farmer)
            .select_related("tool")
            .order_by("-created_at")
        )
        return context


class ContactView(FormView):
    template_name = "assets/contact.html"
    form_class = ContactForm
    success_url = reverse_lazy("contact")

    def form_valid(self, form):
        form.save()

        # AJAX request → return JSON success
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        # Normal fallback
        return self.render_to_response(
            self.get_context_data(form=self.form_class(), contact_success=True)
        )

    def form_invalid(self, form):
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)

        return super().form_invalid(form)
