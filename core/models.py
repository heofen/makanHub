from django.db import models
from django.contrib.auth.models import AbstractUser, Group, BaseUserManager
from .utils import generate_clap_embedding # Импортируем нашу функцию
from django.conf import settings
import os
import logging # Добавим логирование
from django.utils.translation import gettext_lazy as _ # Для сообщений об ошибках
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# --- Custom User Manager ---
class CustomUserManager(BaseUserManager):
    """Кастомный менеджер для модели User с email в качестве идентификатора."""

    def create_user(self, email, password=None, **extra_fields):
        """Создает и сохраняет User с email и паролем."""
        if not email:
            raise ValueError(_('Поле Email должно быть установлено'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Создает и сохраняет SuperUser с email и паролем."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser должен иметь is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser должен иметь is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)

# Модель пользователя (расширяем стандартную модель Django)
class User(AbstractUser):
    # Убираем username как обязательное поле, оно остается от AbstractUser
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=False, # Делаем НЕ уникальным
        null=True, blank=True, # Разрешаем быть пустым
        help_text=_( "Необязательно. 150 символов или меньше. Только буквы, цифры и @/./+/-/_." ),
        # validators=[username_validator],
        error_messages={
            # "unique": _("A user with that username already exists."),
        },
    )
    email = models.EmailField(_('email address'), unique=True) # Email должен быть уникальным

    USERNAME_FIELD = 'email' # Используем email для входа
    REQUIRED_FIELDS = [] # Не требуем никаких доп. полей при создании superuser (кроме email и пароля)

    objects = CustomUserManager() # Указываем кастомный менеджер

    # Добавляем связь с группами Django для управления правами
    groups = models.ManyToManyField(
        Group,
        verbose_name=('groups'),
        blank=True,
        help_text=(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name="core_user_set", # Изменено для избежания конфликта
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=('user permissions'),
        blank=True,
        help_text=('Specific permissions for this user.'),
        related_name="core_user_set", # Изменено для избежания конфликта
        related_query_name="user",
    )
    # Дополнительные поля при необходимости можно добавить сюда
    # например, avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        return self.email # Отображаем email

# Модель жанра
class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название жанра")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Жанр"
        verbose_name_plural = "Жанры"

# Модель трека
class Track(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название")
    artist = models.CharField(max_length=200, verbose_name="Исполнитель")
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Жанр", related_name="tracks")
    duration = models.PositiveIntegerField(default=0, verbose_name="Длительность (сек)", help_text="Длительность трека в секундах (определяется автоматически)")
    filepath = models.FileField(upload_to='tracks/', verbose_name="Файл трека", help_text="Путь к аудиофайлу")
    embedding = models.JSONField(null=True, blank=True, verbose_name="CLAP Эмбеддинг", help_text="Векторное представление трека (CLAP)")
    # embedding = models.BinaryField(null=True, blank=True, verbose_name="Эмбеддинг") # Вариант хранения в БД

    _original_filepath = None # Для отслеживания изменений файла

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Сохраняем исходный путь к файлу при загрузке объекта из БД
        self._original_filepath = self.filepath.name if self.pk else None

    def save(self, *args, **kwargs):
        """Переопределяем save для генерации эмбеддинга после сохранения файла."""
        is_new = self._state.adding
        super().save(*args, **kwargs) # Сначала сохраняем модель, чтобы получить ID и убедиться, что файл сохранен

        file_changed = self.filepath.name != self._original_filepath
        embedding_needed = (is_new or file_changed) and self.filepath

        if embedding_needed:
            try:
                full_audio_path = os.path.join(settings.MEDIA_ROOT, self.filepath.name)
                logger.info(f"Track saved/updated (ID: {self.pk}). Generating embedding for: {full_audio_path}")
                new_embedding = generate_clap_embedding(full_audio_path)
                if new_embedding:
                    # Обновляем только поле embedding, избегая рекурсивного вызова save
                    Track.objects.filter(pk=self.pk).update(embedding=new_embedding)
                    logger.info(f"Embedding saved successfully for Track ID: {self.pk}")
                    # Обновляем _original_filepath после успешного сохранения
                    self._original_filepath = self.filepath.name
                else:
                    logger.warning(f"Embedding generation failed for Track ID: {self.pk}, file: {self.filepath.name}")
            except Exception as e:
                logger.error(f"Error during embedding generation/update for Track ID {self.pk}: {e}", exc_info=True)
        elif not self.filepath:
             if is_new or file_changed:
                 logger.warning(f"Track ID: {self.pk} saved without a file. Clearing embedding.")
                 Track.objects.filter(pk=self.pk).update(embedding=None)
                 self._original_filepath = None

    def __str__(self):
        return f"{self.artist} - {self.title}"

    class Meta:
        verbose_name = "Трек"
        verbose_name_plural = "Треки"

# Модель альбома
class Album(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название альбома")
    artist = models.CharField(max_length=200, verbose_name="Исполнитель")
    release_date = models.DateField(null=True, blank=True, verbose_name="Дата релиза")
    cover = models.ImageField(upload_to='album_covers/', null=True, blank=True, verbose_name="Обложка")
    tracks = models.ManyToManyField(Track, related_name='albums', blank=True, verbose_name="Треки")

    def __str__(self):
        return f"{self.artist} - {self.title}"

    class Meta:
        verbose_name = "Альбом"
        verbose_name_plural = "Альбомы"

# Модель плейлиста
class Playlist(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название плейлиста")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Владелец", related_name="playlists")
    tracks = models.ManyToManyField(Track, related_name='playlists', blank=True, verbose_name="Треки")
    is_public = models.BooleanField(default=True, verbose_name="Публичный")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return f"{self.name} by {self.owner.email}"

    class Meta:
        verbose_name = "Плейлист"
        verbose_name_plural = "Плейлисты"

# Модель рекомендации
class Recommendation(models.Model):
    source_track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='source_recommendations', verbose_name="Исходный трек")
    recommended_track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='recommended_for', verbose_name="Рекомендованный трек")
    score = models.FloatField(verbose_name="Оценка схожести", help_text="Метрика схожести от Annoy/CLAP")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    def __str__(self):
        return f"Recommendation for {self.source_track.title}: {self.recommended_track.title} ({self.score:.2f})"

    class Meta:
        verbose_name = "Рекомендация"
        verbose_name_plural = "Рекомендации"
        unique_together = ('source_track', 'recommended_track') # Гарантируем уникальность пар

# Модель задачи обучения/обработки (для CLAP)
class TrainingJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидание'),
        ('running', 'Выполняется'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
    ]
    parameters = models.JSONField(verbose_name="Параметры", null=True, blank=True, help_text="Параметры запуска (например, модель, датасет)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Время начала")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Время завершения")
    logs = models.TextField(blank=True, verbose_name="Логи выполнения")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Job {self.id} ({self.status})"

    class Meta:
        verbose_name = "Задача обработки"
        verbose_name_plural = "Задачи обработки"

# Модель лога аудита
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Создание'),
        ('update', 'Обновление'),
        ('delete', 'Удаление'),
        ('login', 'Вход'),
        # Добавить другие действия по необходимости
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Пользователь", related_name="audit_logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Действие")
    model_name = models.CharField(max_length=100, verbose_name="Модель", help_text="Название измененной модели (например, Track, User)")
    object_id = models.PositiveIntegerField(verbose_name="ID объекта", help_text="ID измененного объекта", null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время")
    details = models.TextField(blank=True, verbose_name="Детали", help_text="Дополнительная информация об изменении")

    def __str__(self):
        user_str = self.user.email if self.user else "System"
        return f"{self.timestamp}: {user_str} - {self.action} on {self.model_name} ({self.object_id})"

    class Meta:
        verbose_name = "Лог аудита"
        verbose_name_plural = "Логи аудита"
        ordering = ['-timestamp'] # Сортировка по убыванию времени

# --- Модель Лайков/Дизлайков ---
class LikeDislike(models.Model):
    LIKE = 1
    DISLIKE = -1
    VOTE_CHOICES = (
        (LIKE, 'Нравится'),
        (DISLIKE, 'Не нравится')
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='track_votes')
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='votes')
    vote = models.SmallIntegerField(choices=VOTE_CHOICES, verbose_name="Голос")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'track') # Пользователь может поставить только один голос на трек
        verbose_name = "Оценка трека"
        verbose_name_plural = "Оценки треков"

    def __str__(self):
        return f"{self.user.email} - {self.track.title}: {'Like' if self.vote == self.LIKE else 'Dislike'}"

    def clean(self):
        # Дополнительная валидация, если нужно
        if self.vote not in [self.LIKE, self.DISLIKE]:
            raise ValidationError("Недопустимое значение для голоса.")

# Не забыть добавить 'core.apps.CoreConfig' в INSTALLED_APPS в settings.py
# И указать AUTH_USER_MODEL = 'core.User'
