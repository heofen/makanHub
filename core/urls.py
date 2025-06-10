from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'), # Главная страница
    path('new_track/', views.new_track_view, name='new_track'),
    path('track/<int:track_id>/', views.track_detail_view, name='track_detail'), # Страница трека
    path('track/<int:track_id>/recommendations/', views.track_recommendations_view, name='track_recommendations'),

    # Аутентификация
    path('register/', views.register_view, name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),

    # Лайки/Дизлайки (API)
    path('track/<int:track_id>/vote/', views.vote_track_view, name='vote_track'),

    # Персональные рекомендации
    path('my_vibe/', views.my_vibe_view, name='my_vibe'),

    # Статистика (только для staff)
    path('stats/', views.stats_view, name='stats'),
    
    # Дэшборд (только для staff)
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Другие URL приложения core здесь
] 