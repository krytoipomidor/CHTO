from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Room, RoomType


class BookingFlowTests(TestCase):
    @staticmethod
    def local_input(value):
        return timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')

    def setUp(self):
        self.room_type = RoomType.objects.create(name='Переговорна')
        self.room = Room.objects.create(
            room_type=self.room_type,
            name='Кімната 1',
            capacity=8,
            price_per_hour='250.00',
        )
        self.start_at = (timezone.now() + timedelta(days=2)).replace(second=0, microsecond=0)
        self.end_at = self.start_at + timedelta(hours=2)

    def test_booking_submission_is_pending_and_sends_confirmation_email(self):
        response = self.client.post(reverse('popro:create_booking'), {
            'customer_name': 'Олена',
            'customer_email': 'olena@example.com',
            'room': self.room.pk,
            'start_at': self.local_input(self.start_at),
            'end_at': self.local_input(self.end_at),
        })

        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.get()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/confirm/', mail.outbox[0].body)

    def test_overlapping_booking_is_rejected(self):
        Booking.objects.create(
            room=self.room,
            customer_name='Перше бронювання',
            customer_email='first@example.com',
            start_at=self.start_at,
            end_at=self.end_at,
        )
        response = self.client.post(reverse('popro:create_booking'), {
            'customer_name': 'Друге бронювання',
            'customer_email': 'second@example.com',
            'room': self.room.pk,
            'start_at': self.local_input(self.start_at + timedelta(minutes=30)),
            'end_at': self.local_input(self.end_at + timedelta(minutes=30)),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertContains(response, 'вже зайнята')

    def test_confirmation_requires_post_and_confirms_booking(self):
        self.client.post(reverse('popro:create_booking'), {
            'customer_name': 'Олена',
            'customer_email': 'olena@example.com',
            'room': self.room.pk,
            'start_at': self.local_input(self.start_at),
            'end_at': self.local_input(self.end_at),
        })
        booking = Booking.objects.get()
        confirmation_path = mail.outbox[0].body.split('/confirm', 1)[1].strip().splitlines()[0]
        confirmation_url = f'/confirm{confirmation_path}'

        self.client.get(confirmation_url)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.client.post(confirmation_url)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_availability_endpoint_excludes_booked_rooms(self):
        Booking.objects.create(
            room=self.room,
            customer_name='Олена',
            customer_email='olena@example.com',
            start_at=self.start_at,
            end_at=self.end_at,
        )
        response = self.client.get(reverse('popro:availability'), {
            'start_at': self.local_input(self.start_at),
            'end_at': self.local_input(self.end_at),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['available_rooms'], [])

    def test_room_list_renders(self):
        response = self.client.get(reverse('popro:room_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.room.name)
