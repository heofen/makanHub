# core/forms.py
from django import forms
from .models import Track, User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

class TrackForm(forms.ModelForm):
    class Meta:
        model = Track
        exclude = ('embedding', 'duration')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'artist': forms.TextInput(attrs={'class': 'form-control'}),
            'genre': forms.Select(attrs={'class': 'form-select'}),
            'filepath': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'title': 'Название трека',
            'artist': 'Исполнитель',
            'genre': 'Жанр',
            'filepath': 'Аудиофайл',
        }

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Пароль'})
        self.fields['password1'].label = "Пароль"
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Подтвердите пароль'})
        self.fields['password2'].label = "Подтверждение пароля"

class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'autofocus': True, 'class': 'form-control', 'placeholder': 'Email'})
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'class': 'form-control', 'placeholder':'Пароль'})
    )

class BulkTrackUploadForm(forms.Form):
    artist = forms.CharField(
        label='Исполнитель',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    audio_files = forms.FileField(
        label='Аудиофайлы',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        help_text='Выберите один или несколько аудиофайлов'
    ) 