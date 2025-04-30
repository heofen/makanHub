from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import TrackForm, UserRegistrationForm, LoginForm # Добавлены UserRegistrationForm, LoginForm
from .models import Track, LikeDislike, User # Добавили User и LikeDislike
from .annoy_service import annoy_service # Импортируем глобальный экземпляр сервиса
from django.http import Http404, JsonResponse, HttpResponseBadRequest
from django.core.paginator import Paginator # Для пагинации
import librosa # Используем librosa для длительности
import math # Для округления
import logging
import os # Добавим os для работы с временным файлом
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.contrib.auth import login, logout # Нужны для login/logout
from django.urls import reverse_lazy # Для редиректа после регистрации
from django.contrib.auth.views import LoginView, LogoutView # Используем встроенные LoginView/LogoutView
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Value, Case, When # Добавили Value, Case, When
from django.db.models.functions import Coalesce # Добавили Coalesce
import random # Для выбора случайного трека

logger = logging.getLogger(__name__)

def new_track_view(request):
    if request.method == 'POST':
        form = TrackForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                track = form.save(commit=False)
                audio_file = request.FILES.get('filepath')

                if audio_file:
                    # Определяем длительность с помощью librosa
                    duration_seconds = 0
                    audio_path_for_librosa = None
                    try:
                        # Librosa лучше работает с путем к файлу, чем с file-like object
                        # Если файл временный, используем его путь
                        if isinstance(audio_file, TemporaryUploadedFile):
                            audio_path_for_librosa = audio_file.temporary_file_path()
                        else:
                            # Для файлов в памяти может потребоваться сохранить во временный файл
                            # Это усложнение, пока предполагаем TemporaryUploadedFile
                            # Если это не так, librosa может не сработать напрямую
                            # logger.warning("Uploaded file is not temporary, duration detection might fail.")
                            # Пробуем передать сам объект, вдруг сработает
                            audio_path_for_librosa = audio_file

                        if audio_path_for_librosa:
                             duration_seconds = math.ceil(librosa.get_duration(path=audio_path_for_librosa))
                             logger.info(f"Determined duration for {audio_file.name} using librosa: {duration_seconds}s")
                        else:
                             logger.warning(f"Could not get a valid path or object for librosa duration detection: {audio_file.name}")
                             messages.warning(request, f'Не удалось получить путь к файлу {audio_file.name} для определения длительности.')

                    except Exception as e:
                        logger.error(f"Librosa error getting duration for {audio_file.name}: {e}", exc_info=True)
                        messages.warning(request, f'Не удалось определить длительность файла {audio_file.name} с помощью librosa.')
                    finally:
                       # Указатель файла мог быть изменен librosa (если передавали объект)
                       # Вернем на всякий случай, хотя при передаче пути это не нужно
                       try:
                           audio_file.seek(0)
                       except: pass

                    track.duration = duration_seconds
                else:
                    track.duration = 0

                track.save()
                form.save_m2m()

                messages.success(request, f'Трек "{track.title}" (длительность: {track.duration} сек.) успешно загружен! Эмбеддинг будет сгенерирован.')
                return redirect('new_track')
            except Exception as e:
                 logger.error(f"Ошибка при сохранении трека: {e}", exc_info=True)
                 messages.error(request, f'Ошибка при сохранении трека: {e}')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = TrackForm()

    return render(request, 'core/new_track.html', {'form': form})

def track_recommendations_view(request, track_id):
    try:
        source_track = Track.objects.get(pk=track_id)
    except Track.DoesNotExist:
        raise Http404("Трек не найден")

    recommended_ids = annoy_service.find_nearest_neighbors(track_id, n=10) # Ищем 10 соседей

    recommended_tracks = list(Track.objects.filter(pk__in=recommended_ids))
    # Сохраняем порядок, возвращенный Annoy (от ближайшего к дальнему)
    recommended_tracks.sort(key=lambda t: recommended_ids.index(t.pk))

    context = {
        'source_track': source_track,
        'recommendations': recommended_tracks,
    }
    return render(request, 'core/recommendations.html', context)

def track_detail_view(request, track_id):
    try:
        # Используем annotate для подсчета лайков/дизлайков прямо в запросе к треку
        track = Track.objects.select_related('genre').annotate(
            likes_count=Coalesce(Count('votes', filter=Q(votes__vote=LikeDislike.LIKE)), Value(0)),
            dislikes_count=Coalesce(Count('votes', filter=Q(votes__vote=LikeDislike.DISLIKE)), Value(0))
        ).get(pk=track_id)
    except Track.DoesNotExist:
        raise Http404("Трек не найден")

    user_votes = {}
    if request.user.is_authenticated:
        # Получаем голос текущего пользователя для этого трека
        user_vote_obj = LikeDislike.objects.filter(user=request.user, track=track).first()
        if user_vote_obj:
             # Используем словарь user_votes, т.к. в шаблоне может быть несколько треков (на других страницах)
             # Здесь ключ - ID трека
            user_votes[track.pk] = user_vote_obj.vote

    context = {
        'track': track, # Теперь содержит likes_count и dislikes_count
        'user_votes': user_votes, # Словарь с голосом текущего пользователя (или пустой)
    }
    return render(request, 'core/track_detail.html', context)

def home_view(request):
    # TODO: Добавить поиск и фильтрацию
    track_list = Track.objects.select_related('genre').order_by('-id') # Последние загруженные сверху
    paginator = Paginator(track_list, 10) # По 10 треков на страницу

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'core/home.html', context)

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home') # Не пускаем зарегистрированных на страницу регистрации

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Автоматически логиним пользователя после регистрации
            messages.success(request, 'Регистрация прошла успешно! Вы вошли в систему.')
            return redirect('home')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме регистрации.')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})

# Используем встроенный LoginView, но с нашей кастомной формой и шаблоном
class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = 'registration/login.html'
    # URL для редиректа после успешного входа (по умолчанию settings.LOGIN_REDIRECT_URL)
    # Мы можем оставить его по умолчанию или переопределить здесь
    # next_page = reverse_lazy('home')

    def form_valid(self, form):
        messages.success(self.request, f"Добро пожаловать, {form.get_user().username}!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Неверное имя пользователя или пароль.")
        return super().form_invalid(form)

# Используем встроенный LogoutView
class CustomLogoutView(LogoutView):
    # URL для редиректа после выхода (по умолчанию settings.LOGOUT_REDIRECT_URL)
    next_page = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        # Добавляем сообщение перед выходом
        if request.user.is_authenticated:
             messages.info(request, "Вы вышли из системы.")
        return super().dispatch(request, *args, **kwargs)

@login_required # Требуем, чтобы пользователь был залогинен
def vote_track_view(request, track_id):
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST method is allowed")

    track = get_object_or_404(Track, pk=track_id)
    vote_type = request.POST.get('vote_type') # Ожидаем 'like' или 'dislike'

    if vote_type not in ['like', 'dislike']:
        return HttpResponseBadRequest("Invalid vote type")

    vote_value = LikeDislike.LIKE if vote_type == 'like' else LikeDislike.DISLIKE
    user = request.user

    try:
        # Пытаемся найти существующий голос
        like_dislike = LikeDislike.objects.get(user=user, track=track)

        # Если голос совпадает с текущим -> удаляем голос (отмена лайка/дизлайка)
        if like_dislike.vote == vote_value:
            like_dislike.delete()
            user_vote = None
            messages.info(request, f"Ваш голос для трека '{track.title}' отменен.")
        else:
            # Если голос другой -> обновляем его
            like_dislike.vote = vote_value
            like_dislike.save()
            user_vote = vote_value
            messages.success(request, f"Ваш голос для трека '{track.title}' изменен.")

    except LikeDislike.DoesNotExist:
        # Если голоса нет -> создаем новый
        LikeDislike.objects.create(user=user, track=track, vote=vote_value)
        user_vote = vote_value
        messages.success(request, f"Ваш голос для трека '{track.title}' учтен.")

    # Считаем общее количество лайков и дизлайков для трека
    likes_count = track.votes.filter(vote=LikeDislike.LIKE).count()
    dislikes_count = track.votes.filter(vote=LikeDislike.DISLIKE).count()

    return JsonResponse({
        'success': True,
        'likes_count': likes_count,
        'dislikes_count': dislikes_count,
        'user_vote': user_vote # None, 1 (LIKE) или -1 (DISLIKE)
    })

@login_required
def my_vibe_view(request):
    user = request.user
    liked_tracks_ids = LikeDislike.objects.filter(user=user, vote=LikeDislike.LIKE).values_list('track_id', flat=True)

    source_track = None
    recommendations = []

    if liked_tracks_ids:
        # Выбираем случайный ID лайкнутого трека
        random_liked_track_id = random.choice(list(liked_tracks_ids))
        try:
            # Получаем сам трек (с аннотациями счетчиков для шаблона)
            source_track = Track.objects.select_related('genre').annotate(
                likes_count=Coalesce(Count('votes', filter=Q(votes__vote=LikeDislike.LIKE)), Value(0)),
                dislikes_count=Coalesce(Count('votes', filter=Q(votes__vote=LikeDislike.DISLIKE)), Value(0))
            ).get(pk=random_liked_track_id)

            # Получаем рекомендации для этого трека
            recommended_ids = annoy_service.find_nearest_neighbors(random_liked_track_id, n=10)
            if recommended_ids:
                recommended_tracks_list = list(Track.objects.filter(pk__in=recommended_ids))
                recommended_tracks_list.sort(key=lambda t: recommended_ids.index(t.pk))
                # Дополнительно аннотируем счетчиками и голосом пользователя для отображения
                recommendations = Track.objects.filter(pk__in=recommended_ids).annotate(
                    likes_count=Coalesce(Count('votes', filter=Q(votes__vote=LikeDislike.LIKE)), Value(0)),
                    dislikes_count=Coalesce(Count('votes', filter=Q(votes__vote=LikeDislike.DISLIKE)), Value(0))
                ).order_by(Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(recommended_ids)]))

        except Track.DoesNotExist:
            # Маловероятно, но возможно, если трек удалили после лайка
            pass

    # Получаем голоса пользователя для рекомендованных треков
    user_votes = {}
    if recommendations:
        user_votes_query = LikeDislike.objects.filter(user=user, track__in=recommendations).values('track_id', 'vote')
        user_votes = {item['track_id']: item['vote'] for item in user_votes_query}

    context = {
        'source_track': source_track, # Трек, на основе которого сгенерирован вайб (или None)
        'recommendations': recommendations, # Список рекомендованных треков
        'user_votes': user_votes, # Голоса пользователя для рекомендованных треков
    }
    return render(request, 'core/my_vibe.html', context)

# Другие view могут быть добавлены здесь
