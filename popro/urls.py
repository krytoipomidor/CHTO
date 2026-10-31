from django.urls import path

from . import views

app_name = 'popro'

urlpatterns = [
    path('', views.room_list, name='room_list'),
    path('book/', views.create_booking, name='create_booking'),
    path('availability/', views.availability, name='availability'),
    path('confirm/<str:token>/', views.confirm_booking, name='confirm_booking'),
]
