from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('flush_list', views.flush_list, name='flush_list')
]