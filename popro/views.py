from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AvailabilityForm, BookingForm
from .models import Booking, Room


def room_list(request):
    form = AvailabilityForm(request.GET or None)
    rooms = Room.objects.filter(is_active=True).select_related('room_type')
    occupied_bookings = Booking.objects.none()
    if form.is_valid():
        room_type = form.cleaned_data.get('room_type')
        start_at = form.cleaned_data.get('start_at')
        end_at = form.cleaned_data.get('end_at')
        if room_type:
            rooms = rooms.filter(room_type=room_type)
        if start_at and end_at:
            occupied_bookings = Booking.objects.filter(
                status__in=(Booking.Status.PENDING, Booking.Status.CONFIRMED),
                room__is_active=True,
                start_at__lt=end_at,
                end_at__gt=start_at,
            ).select_related('room', 'room__room_type')
            if room_type:
                occupied_bookings = occupied_bookings.filter(room__room_type=room_type)
            occupied_room_ids = occupied_bookings.values_list('room_id', flat=True)
            rooms = rooms.exclude(pk__in=occupied_room_ids)
    return render(request, 'popro/room_list.html', {
        'form': form,
        'rooms': rooms,
        'occupied_bookings': occupied_bookings,
    })


@require_http_methods(['GET', 'POST'])
def create_booking(request):
    initial = {}
    room_id = request.GET.get('room')
    if room_id:
        initial['room'] = room_id
    form = BookingForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            booking = form.save(commit=False)
            Room.objects.select_for_update().get(pk=booking.room_id, is_active=True)
            booking.full_clean()
            booking.save()
        token = signing.dumps({'booking_id': booking.pk, 'email': booking.customer_email})
        confirmation_url = request.build_absolute_uri(
            reverse('popro:confirm_booking', kwargs={'token': token})
        )
        send_mail(
            'Підтвердження бронювання',
            f'Щоб підтвердити бронювання кімнати «{booking.room}», перейдіть за посиланням:\n{confirmation_url}',
            settings.DEFAULT_FROM_EMAIL,
            [booking.customer_email],
        )
        return render(request, 'popro/booking_submitted.html', {'booking': booking})
    return render(request, 'popro/booking_form.html', {'form': form})


@require_GET
def availability(request):
    form = AvailabilityForm(request.GET)
    if not form.is_valid() or not form.cleaned_data.get('start_at') or not form.cleaned_data.get('end_at'):
        return JsonResponse({'error': 'Вкажіть коректні start_at та end_at.'}, status=400)
    start_at = form.cleaned_data['start_at']
    end_at = form.cleaned_data['end_at']
    if end_at <= start_at:
        return JsonResponse({'error': 'Завершення має бути пізніше за початок.'}, status=400)
    room_type = form.cleaned_data.get('room_type')
    rooms = Room.objects.filter(is_active=True)
    if room_type:
        rooms = rooms.filter(room_type=room_type)
    occupied_room_ids = Booking.objects.filter(
        status__in=(Booking.Status.PENDING, Booking.Status.CONFIRMED),
        start_at__lt=end_at,
        end_at__gt=start_at,
    ).values_list('room_id', flat=True)
    available = rooms.exclude(pk__in=occupied_room_ids).values('id', 'name')
    return JsonResponse({'available_rooms': list(available)})


@require_http_methods(['GET', 'POST'])
def confirm_booking(request, token):
    try:
        payload = signing.loads(token, max_age=60 * 60 * 24)
    except signing.BadSignature:
        return render(request, 'popro/confirmation_result.html', {
            'message': 'Посилання підтвердження недійсне або застаріле.',
        }, status=400)
    booking = get_object_or_404(
        Booking,
        pk=payload.get('booking_id'),
        customer_email=payload.get('email'),
    )
    if request.method == 'POST' and booking.status == Booking.Status.PENDING:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=booking.pk)
            Room.objects.select_for_update().get(pk=booking.room_id)
            if booking.status == Booking.Status.PENDING and booking.end_at <= timezone.now():
                return render(request, 'popro/confirmation_result.html', {
                    'message': 'Час цього бронювання вже минув.',
                }, status=400)
            if booking.status == Booking.Status.PENDING:
                overlapping = Booking.objects.filter(
                    room=booking.room,
                    status__in=(Booking.Status.PENDING, Booking.Status.CONFIRMED),
                    start_at__lt=booking.end_at,
                    end_at__gt=booking.start_at,
                ).exclude(pk=booking.pk).exists()
                if overlapping:
                    return render(request, 'popro/confirmation_result.html', {
                        'message': 'На жаль, кімната вже зайнята у цей період.',
                    }, status=409)
                booking.status = Booking.Status.CONFIRMED
                booking.save(update_fields=('status',))
    return render(request, 'popro/confirm_booking.html', {'booking': booking})
