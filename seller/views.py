from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, CreateView, UpdateView, DeleteView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden
from .models import Seller, SellerDocument
from .forms import SellerForm
from django.contrib import messages
from .forms import ToolForm, CategoryForm, TagForm
from kishan.models import Booking, Notification, Rental, Tool, Category, Tag
from django.core.exceptions import ObjectDoesNotExist


class SellerRegisterShopView(CreateView):
    model = Seller
    form_class = SellerForm
    template_name = "assets/seller/register/register_shop.html"
    success_url = reverse_lazy("seller-dashboard")

    def dispatch(self, request, *args, **kwargs):
        seller = getattr(request.user, "seller", None)

        if seller:
            shop = getattr(seller, "shop", None)
            if shop and shop.status != "cancelled":
                return redirect("seller-dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        user = self.request.user
        initial["full_name"] = user.get_full_name()
        initial["email"] = user.email
        if hasattr(user, "profile") and user.profile.phone:
            initial["phone"] = user.profile.phone
        return initial

    def form_valid(self, form):
        seller = form.save(user=self.request.user)

        files = self.request.FILES.getlist("shopDocuments")

        for f in files:
            if f.content_type not in [
                "application/pdf",
                "image/jpeg",
                "image/png",
            ]:
                form.add_error(None, f"{f.name} has an invalid file type.")
                return self.form_invalid(form)

            if f.size > 5 * 1024 * 1024:
                form.add_error(None, f"{f.name} exceeds the 5MB file size limit.")
                return self.form_invalid(form)

            SellerDocument.objects.create(
                seller=seller,
                document=f,
            )

        return super().form_valid(form)


@login_required
def seller_dashboard(request):
    try:
        seller = request.user.seller
    except Seller.DoesNotExist:
        seller = None
    return render(request, "assets/seller/seller_dashboard.html", {"seller": seller})


# CRUD
# For Tool
class ToolListView(LoginRequiredMixin, View):
    template_name = "assets/seller/register/tool_add.html"

    def get(self, request):
        # Get only tools belonging to the current seller
        seller = getattr(request.user, "seller", None)
        if seller is None:
            # Optionally redirect the user to register as a seller
            return redirect("seller-register")

        tools = Tool.objects.filter(owner=seller)
        categories = Category.objects.all()
        tags = Tag.objects.all()
        form = ToolForm()
        return render(
            request,
            self.template_name,
            {
                "tools": tools,
                "categories": categories,
                "tags": tags,
                "form": form,
            },
        )
    
    def post(self, request):
        seller = getattr(request.user, "seller", None)
        if seller is None:
            return redirect("seller-register")

        tool_id = request.POST.get("tool_id")

        if tool_id:
            # Edit existing tool
            tool = get_object_or_404(Tool, pk=tool_id, owner=seller)
            form = ToolForm(request.POST, request.FILES, instance=tool)
        else:
            # New tool
            form = ToolForm(request.POST, request.FILES)

        if form.is_valid():
            tool = form.save(commit=False)
            tool.owner = seller
            tool.save()
            form.save_m2m()  # Save any many-to-many data
            return redirect("tools-list")
        else:
            tools = Tool.objects.filter(owner=seller)
            categories = Category.objects.all()
            tags = Tag.objects.all()
            return render(
                request,
                self.template_name,
                {
                    "tools": tools,
                    "categories": categories,
                    "tags": tags,
                    "form": form,
                },
            )


class ToolDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        tool = get_object_or_404(Tool, pk=pk)
        tool.delete()
        return redirect("tools-list")


# Category
class CategoryListView(LoginRequiredMixin, View):
    template_name = "assets/seller/register/category_add.html"

    def get(self, request):
        categories = Category.objects.all()
        form = CategoryForm()
        return render(
            request, self.template_name, {"categories": categories, "form": form}
        )

    def post(self, request):
        category_id = request.POST.get("category_id")
        instance = get_object_or_404(Category, pk=category_id) if category_id else None
        form = CategoryForm(request.POST, instance=instance)

        if form.is_valid():
            form.save()
            return redirect("categories-list")

        categories = Category.objects.all()
        return render(
            request,
            self.template_name,
            {
                "categories": categories,
                "form": form,
                "form_errors": form.errors,
            },
        )


class CategoryDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        category.delete()
        return redirect("categories-list")


class TagListView(LoginRequiredMixin, View):
    template_name = "assets/seller/register/tag_add.html"

    def get(self, request):
        tags = Tag.objects.all()
        form = TagForm()
        return render(request, self.template_name, {"tags": tags, "form": form})

    def post(self, request):
        tag_id = request.POST.get("tag_id")
        if tag_id:
            tag = get_object_or_404(Tag, pk=tag_id)
            form = TagForm(request.POST, instance=tag)
        else:
            form = TagForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("tags-list")
        else:
            tags = Tag.objects.all()
            return render(
                request,
                self.template_name,
                {"tags": tags, "form": form, "form_errors": form.errors},
            )


class TagDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        tag = get_object_or_404(Tag, pk=pk)
        tag.delete()
        return redirect("tags-list")


class SellerBookingListView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = "assets/seller/register/booking_status.html"
    context_object_name = "bookings"

    def get_queryset(self):
        """
        Return all bookings for tools that belong to the current seller.
        """
        # Check if user has a seller profile
        try:
            seller = self.request.user.seller
        except ObjectDoesNotExist:
            # User has no seller profile → return no bookings
            return Booking.objects.none()

        # Find tools belonging to this seller
        seller_tools = Tool.objects.filter(owner=seller)

        # Return bookings for these tools
        return (
            Booking.objects.filter(tool__in=seller_tools)
            .select_related("tool", "farmer__user")
            .order_by("-created_at")
        )

    def dispatch(self, request, *args, **kwargs):
        """
        Block access if the user is not a seller.
        """
        if not hasattr(request.user, "seller"):
            return HttpResponseForbidden("You are not a seller.")
        return super().dispatch(request, *args, **kwargs)


class BookingConfirmView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)

        # Confirm booking (seller action)
        booking.status = "confirmed"
        booking.save()

        # Notify the farmer user linked to booking
        Notification.objects.create(
            user=booking.farmer.user,
            message=f"Your booking for {booking.tool.name} has been confirmed.",
            url=reverse("tool-detail", kwargs={"pk": booking.tool.pk}),
            booking=booking,
        )

        messages.success(request, "Booking confirmed successfully.")
        return redirect(reverse("booking-list"))


class BookingCancelView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)

        # Cancel booking (seller action)
        booking.status = "cancelled"
        booking.save()

        # Notify the farmer user linked to booking
        Notification.objects.create(
            user=booking.farmer.user,
            message=f"Your booking for {booking.tool.name} has been cancelled.",
            url=reverse("tool-detail", kwargs={"pk": booking.tool.pk}),
            booking=booking,
        )

        messages.success(request, "Booking cancelled successfully.")
        return redirect(reverse("booking-list"))


class BookingDeleteView(View):
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)

        # Delete ALL notifications linked to this booking
        Notification.objects.filter(booking=booking).delete()

        booking.delete()

        messages.success(
            request, f"Booking for {booking.tool.name} deleted successfully."
        )
        return redirect(reverse("booking-list"))


class SellerPaymentListView(LoginRequiredMixin, ListView):
    template_name = "assets/seller/register/payment_method.html"
    context_object_name = "rentals"

    def get_queryset(self):
        seller = get_object_or_404(Seller, user=self.request.user)
        return Rental.objects.filter(tool__owner=seller).order_by("-start_date")


class MarkPaymentPaidView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        seller = get_object_or_404(Seller, user=request.user)
        rental = get_object_or_404(Rental, pk=pk, tool__owner=seller)

        if rental.payment_method == "cash" and rental.status == "pending":
            rental.status = "paid"
            rental.save()
            messages.success(
                request,
                f"Payment for {rental.tool.name} (Rs {rental.total_price}) marked as Paid.",
            )
        else:
            messages.error(request, "Payment cannot be marked as Paid.")

        return redirect("payments-list")


class DeleteRentalView(LoginRequiredMixin, View):
    """
    Deletes a rental if it belongs to a tool owned by the seller.
    """

    def post(self, request, pk, *args, **kwargs):
        seller = get_object_or_404(Seller, user=request.user)
        rental = get_object_or_404(Rental, pk=pk, tool__owner=seller)
        rental.delete()
        messages.success(
            request, f"Rental for {rental.tool.name} has been deleted successfully."
        )
        return redirect("payments-list")
