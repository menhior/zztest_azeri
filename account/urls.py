from django.urls import path
from . import views

urlpatterns = [
    path('register', views.register, name='register'),
    path('profile/<str:username>', views.profile, name='profile'),
    path('settings', views.editProfile, name='edit_profile'),
    path('delete', views.deleteProfile, name='delete_profile'),
    path('login', views.login, name='login'),
    path('logout', views.logout, name='logout'),
    path('connect/request/', views.send_connection_request, name='connection_request'),
    path('connect/approve/<str:relation_type>/<int:pk>/', 
        views.approve_connection, name='approve_connection'),
    path('connect/reject/<str:relation_type>/<int:pk>/', 
        views.reject_connection, name='reject_connection'),
]