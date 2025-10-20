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
from .forms import BookingForm, RentalForm, ToolReviewForm
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
    DetailView
)
logger = logging.getLogger(__name__)


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Recommended tools logic
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

        # Get lat/lon from GET params (sent from browser via JS)
        try:
            user_lat = float(self.request.GET.get("lat"))
            user_lon = float(self.request.GET.get("lon"))
        except (TypeError, ValueError):
            user_lat = None
            user_lon = None

        shops = Seller.objects.filter(latitude__isnull=False, longitude__isnull=False)

        shops_with_distance = []
        if user_lat is not None and user_lon is not None:
            for shop in shops:
                dist = haversine_distance(
                    user_lat, user_lon, shop.latitude, shop.longitude
                )
                shops_with_distance.append(
                    {
                        "id": shop.id,
                        "shop_name": shop.shop_name,
                        "location_name": shop.location_name,
                        "latitude": shop.latitude,
                        "longitude": shop.longitude,
                        "distance_km": round(dist, 2),
                    }
                )
            # Optionally sort by distance
            shops_with_distance.sort(key=lambda x: x["distance_km"])
        else:
            # No user location: distance is None
            for shop in shops:
                shops_with_distance.append(
                    {
                        "id": shop.id,
                        "shop_name": shop.shop_name,
                        "location_name": shop.location_name,
                        "latitude": shop.latitude,
                        "longitude": shop.longitude,
                        "distance_km": None,
                    }
                )

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


# class ToolDetailView(View):
#     template_name = "assets/tool_details/tool_detail.html"

#     def get(self, request, pk):
#         return self.render_tool_detail(request, pk)

#     def render_tool_detail(self, request, pk, form=None, edit_review_id=None):
#         tool = get_object_or_404(Tool, pk=pk)
#         now = timezone.now()

#         # Reviews
#         reviews = ToolReview.objects.filter(tool=tool).order_by("-created_at")
#         total_reviews = reviews.count()
#         average_rating = round(reviews.aggregate(avg=Avg("rating"))["avg"] or 0.0, 1)

#         # Stars
#         stars = []
#         for i in range(1, 6):
#             if average_rating >= i:
#                 stars.append("full")
#             elif average_rating + 0.5 >= i:
#                 stars.append("half")
#             else:
#                 stars.append("empty")

#         # Review form
#         edit_review = None
#         if edit_review_id and request.user.is_authenticated:
#             try:
#                 edit_review = ToolReview.objects.get(
#                     pk=edit_review_id, farmer__user=request.user
#                 )
#                 form = form or ToolReviewForm(instance=edit_review)
#             except ToolReview.DoesNotExist:
#                 pass
#         if not form:
#             form = ToolReviewForm()

#         # --- CURRENT RENTAL ---
#         current_rental = (
#             Rental.objects.filter(
#                 tool=tool,
#                 start_date__lte=now,
#                 end_date__gte=now,
#                 status="paid",
#                 is_active=True,
#             )
#             .order_by("start_date")
#             .first()
#         )

#         # --- BOOKINGS ---
#         pending_booking = (
#             Booking.objects.filter(tool=tool, status="pending", end_date__gte=now)
#             .order_by("start_date")
#             .first()
#         )

#         confirmed_booking = (
#             Booking.objects.filter(tool=tool, status="confirmed", end_date__gte=now)
#             .order_by("start_date")
#             .first()
#         )

#         # --- TOOL STATUS LIST ---
#         tool_status_list = []

#         if current_rental:
#             tool_status_list.append(
#                 {
#                     "label": "Rented",
#                     "badge": "danger",
#                     "start_date": current_rental.start_date,
#                     "end_date": current_rental.end_date,
#                 }
#             )

#         if pending_booking:
#             tool_status_list.append(
#                 {
#                     "label": "Pending",
#                     "badge": "warning",
#                     "start_date": pending_booking.start_date,
#                     "end_date": pending_booking.end_date,
#                 }
#             )

#         if confirmed_booking:
#             tool_status_list.append(
#                 {
#                     "label": "Booked",
#                     "badge": "primary",
#                     "start_date": confirmed_booking.start_date,
#                     "end_date": confirmed_booking.end_date,
#                 }
#             )

#         if not current_rental and not pending_booking and not confirmed_booking:
#             tool_status_list.append(
#                 {
#                     "label": "Available",
#                     "badge": "success",
#                     "start_date": None,
#                     "end_date": None,
#                 }
#             )

#         context = {
#             "tool": tool,
#             "reviews": reviews,
#             "total_reviews": total_reviews,
#             "average_rating": average_rating,
#             "star_list": stars,
#             "form": form,
#             "weekly_price": tool.daily_rent_price * 6,
#             "monthly_price": tool.daily_rent_price * 29,
#             "tool_status_list": tool_status_list,
#         }

#         return render(request, self.template_name, context)


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
# class BookingCreateView(LoginRequiredMixin, CreateView):
#     model = Booking
#     form_class = BookingForm
#     template_name = "assets/bookings/booking.html"
#     login_url = "farmer-login"  # Your farmer login URL name here

#     def dispatch(self, request, *args, **kwargs):
#         # Redirect to login if not authenticated
#         if not request.user.is_authenticated:
#             return redirect(self.login_url)

#         # Check if user has a profile and is a farmer
#         if not hasattr(request.user, "profile") or not request.user.profile.is_farmer:
#             messages.error(request, "You must have a farmer account to book tools.")
#             return redirect(self.login_url)

#         return super().dispatch(request, *args, **kwargs)

#     def get_form(self, form_class=None):
#         form = super().get_form(form_class)
#         # Set initial delivery_address field value from farmer profile location
#         if hasattr(self.request.user, "profile") and self.request.user.profile.location:
#             form.fields["delivery_address"].initial = self.request.user.profile.location
#         return form

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)

#         tool_id = self.request.GET.get("tool_id") or self.request.POST.get("tool")
#         tool = None
#         hourly_rate = 0.0

#         if tool_id:
#             tool = get_object_or_404(Tool, id=tool_id)

#             if tool.daily_rent_price:
#                 hourly_rate = tool.daily_rent_price / 24

#             # Check if farmer has an active booking for this tool (pending or confirmed)
#             existing_booking = Booking.objects.filter(
#                 farmer=self.request.user.profile,
#                 tool=tool,
#                 status__in=["pending", "confirmed"],
#             ).first()

#             context["booking"] = existing_booking

#         context["tool"] = tool
#         context["hourly_rate"] = hourly_rate

#         return context

#     def form_valid(self, form):
#         tool = form.cleaned_data["tool"]
#         farmer = self.request.user.profile

#         # Check for existing active booking (pending or confirmed) for same tool by farmer
#         existing_booking = Booking.objects.filter(
#             farmer=farmer,
#             tool=tool,
#             status__in=["pending", "confirmed"],
#         ).first()

#         if existing_booking:
#             messages.info(
#                 self.request,
#                 f"You already have a booking for this tool in '{existing_booking.get_status_display()}' status.",
#             )
#             return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

#         # Prevent booking in the past
#         start_date = form.cleaned_data.get("start_date")
#         end_date = form.cleaned_data.get("end_date")
#         now = timezone.now()

#         if start_date < now or end_date < now:
#             messages.error(
#                 self.request, "You cannot book tools for a past date or time."
#             )
#             return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

#         # Check if tool is available in the requested time range
#         if not is_tool_available(tool, start_date, end_date):
#             messages.error(
#                 self.request,
#                 "The tool is not available for the selected dates and times.",
#             )
#             return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

#         # Assign farmer and set booking status
#         form.instance.farmer = farmer
#         form.instance.status = "pending"

#         return super().form_valid(form)

#     def get_success_url(self):
#         return reverse("tool-detail", kwargs={"pk": self.object.tool.id})


class BookingCreateView(LoginRequiredMixin, CreateView):
    model = Booking
    form_class = BookingForm
    template_name = "assets/bookings/booking.html"
    login_url = "farmer-login"  # Farmer login URL

    def dispatch(self, request, *args, **kwargs):
        # Redirect to login if not authenticated
        if not request.user.is_authenticated:
            return redirect(self.login_url)

        # Ensure user is a farmer
        if not hasattr(request.user, "profile") or not request.user.profile.is_farmer:
            messages.error(request, "You must have a farmer account to book tools.")
            return redirect(self.login_url)

        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Pre-fill delivery address
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

            # Check if farmer has an active booking for this tool
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

        # Prevent booking in the past
        if start_date < now or end_date < now:
            messages.error(
                self.request, "You cannot book tools for a past date or time."
            )
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        # Prevent overlapping with active rentals
        overlapping_rental = Rental.objects.filter(
            tool=tool,
            start_date__lt=end_date,
            end_date__gt=start_date,
            status="paid",
            is_active=True,
        ).exists()
        if overlapping_rental:
            messages.error(
                self.request,
                "You cannot book this tool during this period because it is already rented.",
            )
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        # Prevent overlapping with existing bookings (pending or confirmed)
        if not is_tool_available(tool, start_date, end_date):
            messages.error(
                self.request,
                "The tool is not available for the selected dates and times.",
            )
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        # Check for existing booking by same farmer
        existing_booking = Booking.objects.filter(
            farmer=farmer, tool=tool, status__in=["pending", "confirmed"]
        ).first()
        if existing_booking:
            messages.info(
                self.request,
                f"You already have a booking for this tool in '{existing_booking.get_status_display()}' status.",
            )
            return redirect(reverse("tool-detail", kwargs={"pk": tool.pk}))

        # Assign farmer and set status
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
            return JsonResponse(
                {"available": False, "error": "Missing data"}, status=400
            )

        try:
            tool = Tool.objects.get(id=tool_id)
        except Tool.DoesNotExist:
            return JsonResponse(
                {"available": False, "error": "Tool not found"}, status=404
            )

        start_dt = parse_datetime(start_date)
        end_dt = parse_datetime(end_date)

        if not (start_dt and end_dt):
            return JsonResponse(
                {"available": False, "error": "Invalid dates"}, status=400
            )

        # Check for conflicts
        conflicts = (
            Booking.objects.filter(tool=tool, status__in=["pending", "confirmed"])
            .filter(Q(start_date__lt=end_dt) & Q(end_date__gt=start_dt))
            .first()
        )

        if conflicts:
            return JsonResponse(
                {
                    "available": False,
                    "status": conflicts.status,
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


# class RentToolView(LoginRequiredMixin, View):
#     login_url = "farmer-login"
#     template_name = "assets/bookings/rent.html"

#     def get(self, request, tool_id):
#         tool = get_object_or_404(Tool, id=tool_id)
#         form = RentalForm()

#         # Check if tool is currently rented
#         active_rentals = Rental.objects.filter(
#             tool=tool,
#             status__in=["pending", "paid", "rented"],
#             end_date__gte=timezone.now(),
#             is_active=True,
#         ).order_by("start_date")

#         can_extend = False
#         tool_status_list = []

#         if active_rentals.exists():
#             rental = active_rentals.first()
#             if request.user == rental.farmer.user:
#                 can_extend = True
#             tool_status_list.append(
#                 {
#                     "label": "Rented",
#                     "badge": "danger",
#                     "start_date": rental.start_date,
#                     "end_date": rental.end_date,
#                     "renter_id": rental.farmer.user.id,
#                     "rental_obj": rental,
#                 }
#             )
#         else:
#             tool_status_list.append(
#                 {
#                     "label": "Available",
#                     "badge": "success",
#                     "start_date": None,
#                     "end_date": None,
#                     "renter_id": None,
#                 }
#             )

#         return render(
#             request,
#             self.template_name,
#             {
#                 "tool": tool,
#                 "form": form,
#                 "tool_status_list": tool_status_list,
#                 "can_extend": can_extend,
#             },
#         )

#     def post(self, request, tool_id):
#         tool = get_object_or_404(Tool, id=tool_id)
#         form = RentalForm(request.POST)

#         if not form.is_valid():
#             messages.error(request, "Please correct the errors below.")
#             return render(request, self.template_name, {"tool": tool, "form": form})

#         # Ensure user is a farmer
#         try:
#             farmer_profile = Profile.objects.get(user=request.user, is_farmer=True)
#         except Profile.DoesNotExist:
#             messages.error(request, "You must be a farmer to rent.")
#             return redirect("farmer-orders")

#         # Check if tool is already rented
#         active_rentals = Rental.objects.filter(
#             tool=tool,
#             status__in=["pending", "paid", "rented"],
#             end_date__gte=timezone.now(),
#             is_active=True,
#         ).exists()

#         if active_rentals:
#             messages.error(request, "This tool is already rented and unavailable.")
#             return redirect("tool-detail", tool_id=tool.id)

#         # Rental data
#         start_date = form.cleaned_data.get("start_date")
#         end_date = form.cleaned_data.get("end_date")
#         delivery_needed = form.cleaned_data.get("delivery_needed")
#         payment_method = form.cleaned_data.get("payment_method")  # 'cash' or 'esewa'

#         if end_date <= start_date:
#             form.add_error("end_date", "End date must be after start date.")
#             return render(request, self.template_name, {"tool": tool, "form": form})

#         daily_rate = tool.daily_rent_price or Decimal("0")
#         hourly_rate = daily_rate / Decimal("24")
#         diff_hours = (end_date - start_date).total_seconds() / 3600

#         if diff_hours <= 24:
#             rental_cost = min(daily_rate, Decimal(diff_hours) * hourly_rate)
#         else:
#             full_days = Decimal(diff_hours) // 24
#             remaining_hours = Decimal(diff_hours) % 24
#             rental_cost = (full_days * daily_rate) + min(
#                 daily_rate, remaining_hours * hourly_rate
#             )

#         delivery_charge = (
#             tool.delivery_charge if delivery_needed == "yes" else Decimal("0")
#         )
#         total_price = rental_cost + delivery_charge

#         # Create rental
#         rental = form.save(commit=False)
#         rental.tool = tool
#         rental.farmer = farmer_profile
#         rental.order_id = str(uuid.uuid4())
#         rental.total_price = total_price
#         rental.delivery_charge = delivery_charge

#         # Set status based on payment method
#         if payment_method == "cash":
#             rental.status = "pending"  # COD pending
#             rental.paid_amount = Decimal("0.00")
#         else:
#             rental.status = "paid"  # eSewa paid
#             rental.paid_amount = total_price

#         rental.payment_method = payment_method
#         rental.is_active = True
#         rental.save()

#         # Mark tool as rented/unavailable immediately
#         tool.is_available = False
#         tool.save()

#         # Redirect to proper success page
#         if payment_method == "cash":
#             messages.success(request, "Rental request submitted. Pay on delivery.")
#             return redirect("rental-cod-success", pk=rental.pk)
#         else:
#             messages.success(request, "Rental payment successful via eSewa.")
#             return redirect("rental-esewa-success", pk=rental.pk)


class RentToolView(LoginRequiredMixin, View):
    login_url = "farmer-login"
    template_name = "assets/bookings/rent.html"

    def get(self, request, tool_id):
        tool = get_object_or_404(Tool, id=tool_id)
        form = RentalForm()

        # Active rentals:
        # - COD: pending/paid/rented should block
        # - eSewa: only rented should block
        active_rentals = (
            Rental.objects.filter(
                tool=tool,
                is_active=True,
                end_date__gte=timezone.now(),
            )
            .filter(
                Q(payment_method="cash", status__in=["pending", "paid", "rented"])
                | Q(payment_method="esewa", status="rented")
            )
            .order_by("start_date")
        )

        can_extend = False
        tool_status_list = []

        if active_rentals.exists():
            rental = active_rentals.first()
            if request.user == rental.farmer.user:
                can_extend = True
            tool_status_list.append(
                {
                    "label": "Rented",
                    "badge": "danger",
                    "start_date": rental.start_date,
                    "end_date": rental.end_date,
                    "renter_id": rental.farmer.user.id,
                    "rental_obj": rental,
                }
            )
        else:
            tool_status_list.append(
                {
                    "label": "Available",
                    "badge": "success",
                    "start_date": None,
                    "end_date": None,
                    "renter_id": None,
                }
            )

        return render(
            request,
            self.template_name,
            {
                "tool": tool,
                "form": form,
                "tool_status_list": tool_status_list,
                "can_extend": can_extend,
            },
        )

    def post(self, request, tool_id):
        tool = get_object_or_404(Tool, id=tool_id)
        form = RentalForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please correct errors.")
            return render(request, self.template_name, {"tool": tool, "form": form})

        try:
            farmer_profile = Profile.objects.get(user=request.user, is_farmer=True)
        except Profile.DoesNotExist:
            messages.error(request, "You must be a farmer to rent.")
            return redirect("farmer-orders")

        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")
        delivery_needed = form.cleaned_data.get("delivery_needed")
        payment_method = form.cleaned_data.get("payment_method")  # 'cash' or 'esewa'

        if end_date <= start_date:
            form.add_error("end_date", "End date must be after start date.")
            return render(request, self.template_name, {"tool": tool, "form": form})

        # --- Rental Cost Calculation ---
        daily_rate = tool.daily_rent_price or Decimal("0")
        hourly_rate = daily_rate / Decimal("24")
        diff_hours = (end_date - start_date).total_seconds() / 3600

        if diff_hours <= 24:
            rental_cost = min(daily_rate, Decimal(diff_hours) * hourly_rate)
        else:
            full_days = Decimal(diff_hours) // 24
            rem_hours = Decimal(diff_hours) % 24
            rental_cost = full_days * daily_rate + min(
                daily_rate, rem_hours * hourly_rate
            )

        delivery_charge = (
            tool.delivery_charge if delivery_needed == "yes" else Decimal("0")
        )
        total_price = (rental_cost + delivery_charge).quantize(Decimal("0.00"))

        # --- Create Rental Object ---
        rental = form.save(commit=False)
        rental.tool = tool
        rental.farmer = farmer_profile
        rental.total_price = total_price
        rental.delivery_charge = delivery_charge
        rental.payment_method = payment_method
        rental.paid_amount = Decimal("0.00")
        rental.esewa_transaction_uuid = str(uuid.uuid4())

        # ✅ Do NOT mark as active or rented yet for eSewa
        if payment_method == "esewa":
            rental.is_active = False
            rental.status = "pending"
        else:
            rental.is_active = True
            rental.status = "pending"

        rental.save()

        # --- Cash Flow (unchanged) ---
        if payment_method == "cash":
            messages.success(request, "Rental submitted. Pay on delivery.")
            return redirect("rental-cod-success", pk=rental.pk)

        # --- eSewa Flow ---
        context = {
            "esewa_url": settings.ESEWA_EPAY_URL,
            "txAmt": str(total_price),
            "tAmt": str(total_price),
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

        # ✅ Confirm payment only here
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
            # ❌ Reset so tool becomes available again
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
