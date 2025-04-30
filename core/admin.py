from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Genre, Track, Album, Playlist, Recommendation, TrainingJob, AuditLog, LikeDislike, AnnoyIndexStatus
from django.utils.translation import gettext_lazy as _
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import BulkTrackUploadForm
import librosa
import math
import os
from django.core.files.uploadedfile import TemporaryUploadedFile

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
    list_filter = ('genre',)
    search_fields = ('title', 'artist')
    change_list_template = "admin/core/track/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk_upload/', self.admin_site.admin_view(self.bulk_upload_view), name='core_track_bulk_upload'),
        ]
        return custom_urls + urls

    def bulk_upload_view(self, request):
        if request.method == 'POST':
            form = BulkTrackUploadForm(request.POST, request.FILES)
            if form.is_valid():
                artist = form.cleaned_data['artist']
                audio_files = request.FILES.getlist('audio_files')
                success_count = 0
                error_files = []

                for audio_file in audio_files:
                    try:
                        # Определяем название из имени файла (убираем расширение)
                        file_name, _ = os.path.splitext(audio_file.name)
                        title = file_name.replace('_', ' ') # Заменяем подчеркивания на пробелы

                        # Определяем длительность
                        duration_seconds = 0
                        audio_path_for_librosa = None
                        if isinstance(audio_file, TemporaryUploadedFile):
                            audio_path_for_librosa = audio_file.temporary_file_path()
                        else:
                            # Попробуем передать сам объект, если не временный файл
                            audio_path_for_librosa = audio_file

                        if audio_path_for_librosa:
                             duration_seconds = math.ceil(librosa.get_duration(path=audio_path_for_librosa))
                        audio_file.seek(0) # Возвращаем указатель

                        # Создаем и сохраняем трек
                        track = Track(
                            title=title,
                            artist=artist,
                            duration=duration_seconds,
                            filepath=audio_file # Передаем UploadedFile
                        )
                        track.save() # Вызовет генерацию эмбеддинга в модели
                        success_count += 1

                    except Exception as e:
                        error_files.append(f"{audio_file.name} ({e})")
                        # Логируем ошибку
                        admin.ModelAdmin.message_user(request, f"Ошибка обработки файла {audio_file.name}: {e}", messages.ERROR)

                if success_count > 0:
                    self.message_user(request, f"Успешно загружено и обработано {success_count} треков.", messages.SUCCESS)
                if error_files:
                    self.message_user(request, f"Не удалось обработать следующие файлы: {', '.join(error_files)}", messages.WARNING)

                return redirect('../') # Возвращаемся к списку треков (на уровень выше)
        else:
            form = BulkTrackUploadForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Массовая загрузка треков',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/core/track/bulk_upload.html', context)

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

@admin.register(AnnoyIndexStatus)
class AnnoyIndexStatusAdmin(admin.ModelAdmin):
    list_display = ('needs_rebuild', 'last_build_time')
    # Запрещаем добавление/удаление, т.к. запись должна быть одна
    def has_add_permission(self, request):
        return AnnoyIndexStatus.objects.count() == 0
    def has_delete_permission(self, request, obj=None):
        return False

# Регистрируем кастомную модель User с кастомным админ-классом
admin.site.register(User, UserAdmin)
