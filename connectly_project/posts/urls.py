from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.get_users, name='get_users'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/update/<int:id>/', views.update_user, name='update_user'),
    path('users/delete/<int:id>/', views.delete_user, name='delete_user'),
]