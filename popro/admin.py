from django.contrib import admin
from .models import Booking, Room, RoomType


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_type', 'capacity', 'price_per_hour', 'is_active')
    list_filter = ('room_type', 'is_active')
    search_fields = ('name', 'features')


@admin.action(description='Підтвердити вибрані бронювання')
def confirm_bookings(modeladmin, request, queryset):
    queryset.filter(status=Booking.Status.PENDING).update(status=Booking.Status.CONFIRMED)


@admin.action(description='Скасувати вибрані бронювання')
def cancel_bookings(modeladmin, request, queryset):
    queryset.exclude(status=Booking.Status.CANCELLED).update(status=Booking.Status.CANCELLED)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('room', 'customer_name', 'customer_email', 'start_at', 'end_at', 'status')
    list_filter = ('status', 'room__room_type', 'start_at')
    search_fields = ('customer_name', 'customer_email', 'room__name')
    date_hierarchy = 'start_at'
    actions = (confirm_bookings, cancel_bookings)
