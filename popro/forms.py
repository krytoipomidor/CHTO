from django import forms
from django.utils import timezone

from .models import Booking, Room, RoomType


DATETIME_INPUT_FORMATS = ('%Y-%m-%dT%H:%M',)


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ('customer_name', 'customer_email', 'room', 'start_at', 'end_at')
        widgets = {
            'start_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['room'].queryset = Room.objects.filter(is_active=True).select_related('room_type')
        self.fields['start_at'].input_formats = DATETIME_INPUT_FORMATS
        self.fields['end_at'].input_formats = DATETIME_INPUT_FORMATS

    def clean_start_at(self):
        start_at = self.cleaned_data['start_at']
        if start_at <= timezone.now():
            raise forms.ValidationError('Початок бронювання має бути в майбутньому.')
        return start_at


class AvailabilityForm(forms.Form):
    room_type = forms.ModelChoiceField(
        queryset=RoomType.objects.all(),
        required=False,
        label='Тип кімнати',
    )
    start_at = forms.DateTimeField(
        required=False,
        input_formats=DATETIME_INPUT_FORMATS,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Початок',
    )
    end_at = forms.DateTimeField(
        required=False,
        input_formats=DATETIME_INPUT_FORMATS,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Завершення',
    )

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get('start_at')
        end_at = cleaned_data.get('end_at')
        if bool(start_at) != bool(end_at):
            raise forms.ValidationError('Вкажіть і початок, і завершення періоду.')
        if start_at and end_at and end_at <= start_at:
            raise forms.ValidationError('Завершення має бути пізніше за початок.')
        return cleaned_data
