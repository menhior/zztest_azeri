from django.urls import path
from . import views

urlpatterns = [
    path('all_quiz', views.all_quiz_view, name='all_quiz'),
    path('search/<str:category>', views.search_view, name='search'),
    path('<int:quiz_id>', views.quiz_view, name='quiz'),
    path('user_dashboard/', views.user_dashboard_view, name='user_dashboard'),
    path('user_dashboard/filter/<int:category_id>/', views.filter_quiz_results, name='filter_quiz_results'),
    path('quiz_history/', views.quiz_history_view, name='quiz_history'),
    path('<int:submission_id>/result/', views.quiz_result_view, name='quiz_result'),
    path('stats/<int:user_pk>/', views.stats_page, name='stats_page'),
] 