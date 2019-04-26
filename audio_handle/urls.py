from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('task', views.get_task, name='task'),
    path('flush_list', views.flush_list, name='flush_list'),
    path('list', views.list, name='list')
]