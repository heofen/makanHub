# core/utils.py
import torch
import torchaudio # Оставляем для Resample, если понадобится
from transformers import ClapModel, ClapProcessor
import logging
import os
from django.conf import settings
import numpy as np # librosa возвращает numpy
import librosa # Импортируем librosa

logger = logging.getLogger(__name__)

# --- CLAP Embedding Generation ---

# Загружаем модель и процессор CLAP один раз при старте
# Используем предобученную модель от LAION
CLAP_MODEL_NAME = "laion/clap-htsat-unfused"
try:
    logger.info(f"Loading CLAP model: {CLAP_MODEL_NAME}...")
    clap_model = ClapModel.from_pretrained(CLAP_MODEL_NAME)
    clap_processor = ClapProcessor.from_pretrained(CLAP_MODEL_NAME)
    logger.info("CLAP model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load CLAP model: {e}", exc_info=True)
    clap_model = None
    clap_processor = None

def generate_clap_embedding(audio_path):
    """
    Генерирует эмбеддинг для аудиофайла с использованием CLAP.
    :param audio_path: Путь к аудиофайлу.
    :return: Список float (эмбеддинг) или None при ошибке.
    """
    if not clap_model or not clap_processor:
        logger.error("CLAP model or processor not loaded. Cannot generate embedding.")
        return None

    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return None

    try:
        target_sample_rate = clap_processor.feature_extractor.sampling_rate
        logger.info(f"Processing audio file: {audio_path} with target SR: {target_sample_rate}")

        # Загрузка аудио с помощью librosa
        # sr=None -> сохраняет исходную частоту дискретизации
        # mono=True -> преобразует в моно
        waveform_np, original_sample_rate = librosa.load(audio_path, sr=None, mono=True)

        # Ресемплинг, если необходимо (librosa может делать это при загрузке, но сделаем явно для контроля)
        if original_sample_rate != target_sample_rate:
            logger.warning(f"Resampling audio from {original_sample_rate} Hz to {target_sample_rate} Hz using librosa")
            waveform_np = librosa.resample(y=waveform_np, orig_sr=original_sample_rate, target_sr=target_sample_rate)

        # Используем процессор для подготовки данных
        # Передаем numpy array, sampling_rate обязателен
        inputs = clap_processor(audios=waveform_np, sampling_rate=target_sample_rate, return_tensors="pt", padding=True)

        # Получение эмбеддинга аудио
        with torch.no_grad():
            audio_features = clap_model.get_audio_features(**inputs)

        # Нормализация эмбеддинга
        audio_features = audio_features / torch.linalg.norm(audio_features, dim=-1, keepdim=True)

        embedding_list = audio_features.squeeze().tolist()
        logger.info(f"Embedding generated successfully for {audio_path}. Dimension: {len(embedding_list)}")
        return embedding_list

    except Exception as e:
        logger.error(f"Error generating CLAP embedding for {audio_path}: {e}", exc_info=True)
        return None

# --- Вспомогательные функции (если нужны) ---
# ... можно добавить другие утилиты ...
