from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, CreateView, UpdateView, DeleteView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from .models import Seller
from .forms import SellerForm
from django.contrib import messages
from .forms import ToolForm, CategoryForm, TagForm
from kishan.models import Booking, Tool, Category, Tag

class SellerRegisterShopView(LoginRequiredMixin, CreateView):
    model = Seller
    form_class = SellerForm
    template_name = "assets/seller/register/register_shop.html"

    def dispatch(self, request, *args, **kwargs):
        # Redirect if Seller already exists for user
        if hasattr(request.user, "seller"):
            return redirect("seller-dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        seller = form.save(commit=False)
        seller.user = self.request.user
        seller.save()
        return redirect("seller-dashboard")


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
        # Find tools belonging to this seller
        seller_tools = Tool.objects.filter(owner=self.request.user.seller)
        # Return bookings for these tools
        return (
            Booking.objects.filter(tool__in=seller_tools)
            .select_related("tool", "farmer__user")
            .order_by("-created_at")
        )


class BookingConfirmView(View):
    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        booking.status = "confirmed"
        booking.save()
        return redirect(reverse("booking-list"))


class BookingCancelView(View):
    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        booking.status = "cancelled"
        booking.save()
        return redirect(reverse("booking-list"))


class BookingDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        booking.delete()
        messages.success(
            request, f"Booking for {booking.tool.name} deleted successfully."
        )
        return redirect("booking-list")
