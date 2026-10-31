from django.db import models
from django.db.models import Q
from django.utils import timezone


class RoomType(models.Model):
    name = models.CharField('назва типу', max_length=100, unique=True)
    description = models.TextField('опис', blank=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'тип кімнати'
        verbose_name_plural = 'типи кімнат'

    def __str__(self):
        return self.name


class Room(models.Model):
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name='rooms',
        verbose_name='тип',
    )
    name = models.CharField('назва', max_length=120, unique=True)
    capacity = models.PositiveIntegerField('місткість')
    price_per_hour = models.DecimalField('ціна за годину', max_digits=8, decimal_places=2)
    features = models.TextField('особливості', blank=True)
    is_active = models.BooleanField('доступна для бронювання', default=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'кімната'
        verbose_name_plural = 'кімнати'
        constraints = [
            models.CheckConstraint(condition=Q(capacity__gt=0), name='room_capacity_positive'),
            models.CheckConstraint(condition=Q(price_per_hour__gte=0), name='room_price_nonnegative'),
        ]

    def __str__(self):
        return self.name


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Очікує підтвердження'
        CONFIRMED = 'confirmed', 'Підтверджено'
        CANCELLED = 'cancelled', 'Скасовано'

    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='bookings', verbose_name='кімната')
    customer_name = models.CharField('ім’я', max_length=150)
    customer_email = models.EmailField('електронна пошта')
    start_at = models.DateTimeField('початок')
    end_at = models.DateTimeField('завершення')
    status = models.CharField('статус', max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField('створено', default=timezone.now, editable=False)

    class Meta:
        ordering = ('start_at',)
        verbose_name = 'бронювання'
        verbose_name_plural = 'бронювання'
        constraints = [
            models.CheckConstraint(condition=Q(end_at__gt=models.F('start_at')), name='booking_end_after_start'),
        ]
        indexes = [
            models.Index(fields=('room', 'start_at', 'end_at'), name='booking_room_period_idx'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError({'end_at': 'Час завершення має бути пізніше за час початку.'})
        if self.room_id and self.start_at and self.end_at:
            overlaps = Booking.objects.filter(
                room_id=self.room_id,
                start_at__lt=self.end_at,
                end_at__gt=self.start_at,
            ).exclude(status=self.Status.CANCELLED)
            if self.pk:
                overlaps = overlaps.exclude(pk=self.pk)
            if overlaps.exists():
                raise ValidationError('Ця кімната вже зайнята у вибраний період.')

    def __str__(self):
        return f'{self.room} — {self.customer_name} ({self.start_at:%Y-%m-%d %H:%M})'
