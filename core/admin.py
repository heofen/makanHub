from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Genre, Track, Album, Playlist, Recommendation, TrainingJob, AuditLog, LikeDislike
from django.utils.translation import gettext_lazy as _

# Расширяем стандартный админ-класс для User
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'username') # Показываем email, username опционально
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('email', 'first_name', 'last_name', 'username') # Ищем по email и username
    ordering = ('email',) # Сортируем по email

    # Обновляем fieldsets, чтобы email был главным, а username - опциональным
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Optional'), {'fields': ('username',)}), # Добавляем username как опциональное поле
    )
    # Обновляем add_fieldsets для формы создания пользователя в админке
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'password2'), # Используем email
        }),
    )

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ('title', 'artist', 'genre', 'duration')
    list_filter = ('genre',) # Фильтр по жанру
    search_fields = ('title', 'artist')

@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('title', 'artist', 'release_date')
    search_fields = ('title', 'artist')
    filter_horizontal = ('tracks',)
    date_hierarchy = 'release_date' # Удобная навигация по дате релиза

@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_public', 'created_at')
    list_filter = ('is_public', 'owner')
    search_fields = ('name', 'owner__username')
    filter_horizontal = ('tracks',)

@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('source_track', 'recommended_track', 'score', 'created_at')
    search_fields = ('source_track__title', 'recommended_track__title')

@admin.register(TrainingJob)
class TrainingJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'started_at', 'finished_at', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('started_at', 'finished_at', 'logs', 'created_at') # Эти поля обычно изменяются программно

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'object_id')
    list_filter = ('action', 'model_name', 'user')
    search_fields = ('user__username', 'details')
    readonly_fields = ('timestamp', 'user', 'action', 'model_name', 'object_id', 'details') # Логи обычно неизменяемы
    date_hierarchy = 'timestamp'

@admin.register(LikeDislike)
class LikeDislikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'track', 'vote', 'timestamp')
    list_filter = ('vote',)
    search_fields = ('user__email', 'track__title')
    # Поля обычно не редактируются вручную
    readonly_fields = ('user', 'track', 'timestamp')
    date_hierarchy = 'timestamp'

# Регистрируем кастомную модель User с кастомным админ-классом
admin.site.register(User, UserAdmin)
