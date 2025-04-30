# core/annoy_service.py
import logging
import os
from annoy import AnnoyIndex
from django.conf import settings
from .models import Track

logger = logging.getLogger(__name__)

class AnnoyService:
    def __init__(self, dimension=settings.ANNOY_EMBEDDING_DIM, metric=settings.ANNOY_METRIC, index_path=settings.ANNOY_INDEX_PATH):
        self.dimension = dimension
        self.metric = metric
        self.index_path = str(index_path) # Annoy ожидает строку
        self.index = AnnoyIndex(self.dimension, self.metric)
        self.is_loaded = False
        self.item_map = {} # Сопоставление индекса Annoy (0, 1, 2...) с ID трека в БД
        self._load_index()

    def _load_index(self):
        """Пытается загрузить индекс из файла, если он существует."""
        if os.path.exists(self.index_path):
            try:
                self.index.load(self.index_path)
                # TODO: Загрузить item_map вместе с индексом (например, из отдельного файла)
                # Пока что item_map будет пуст при загрузке, нужно доработать сохранение/загрузку
                self.is_loaded = True
                logger.info(f"Annoy index loaded successfully from {self.index_path}. Items: {self.index.get_n_items()}")
            except Exception as e:
                logger.error(f"Failed to load Annoy index from {self.index_path}: {e}", exc_info=True)
                # Если загрузка не удалась, начинаем с пустого индекса
                self.index = AnnoyIndex(self.dimension, self.metric)
                self.is_loaded = False
        else:
            logger.warning(f"Annoy index file not found at {self.index_path}. Starting with an empty index.")
            self.is_loaded = False

    def build_index_from_db(self, num_trees=settings.ANNOY_NUM_TREES):
        """Строит индекс Annoy на основе треков из базы данных."""
        logger.info("Starting to build Annoy index from database...")
        self.index = AnnoyIndex(self.dimension, self.metric)
        self.item_map = {}
        annoy_idx_counter = 0

        # Получаем все треки с непустыми эмбеддингами
        tracks_with_embeddings = Track.objects.exclude(embedding__isnull=True).exclude(embedding__exact='null') # JSON 'null'

        if not tracks_with_embeddings.exists():
            logger.warning("No tracks with embeddings found in the database. Annoy index will be empty.")
            # Сохраняем пустой индекс, если нужно
            # self.index.save(self.index_path)
            return

        for track in tracks_with_embeddings:
            embedding = track.embedding
            if isinstance(embedding, list) and len(embedding) == self.dimension:
                self.index.add_item(annoy_idx_counter, embedding)
                self.item_map[annoy_idx_counter] = track.pk # Сохраняем ID трека
                annoy_idx_counter += 1
            else:
                logger.warning(f"Track ID {track.pk} has invalid or missing embedding (type: {type(embedding)}, len: {len(embedding) if isinstance(embedding, list) else 'N/A'}). Skipping.")

        if annoy_idx_counter > 0:
            logger.info(f"Added {annoy_idx_counter} items to the index. Building {num_trees} trees...")
            self.index.build(num_trees)
            logger.info("Annoy index building complete.")
            # Сохраняем индекс в файл
            try:
                self.index.save(self.index_path)
                logger.info(f"Annoy index saved successfully to {self.index_path}")
                # TODO: Сохранить item_map рядом (например, в JSON-файл)
                self.is_loaded = True
            except Exception as e:
                logger.error(f"Failed to save Annoy index to {self.index_path}: {e}", exc_info=True)
        else:
            logger.warning("No valid embeddings found to build the index.")

    def find_nearest_neighbors(self, track_id, n=10):
        """
        Находит n ближайших соседей для заданного ID трека.
        Возвращает список ID треков.
        """
        if not self.is_loaded:
            logger.warning("Annoy index is not loaded. Cannot find neighbors.")
            return []

        # Находим внутренний индекс Annoy по ID трека
        annoy_idx = None
        for idx, pk in self.item_map.items():
            if pk == track_id:
                annoy_idx = idx
                break

        if annoy_idx is None:
            # Возможно, трек еще не в индексе или self.item_map не загружен
            # Попробуем найти трек в БД и его эмбеддинг
            try:
                track = Track.objects.get(pk=track_id)
                if track.embedding and isinstance(track.embedding, list) and len(track.embedding) == self.dimension:
                    vector = track.embedding
                    logger.info(f"Track ID {track_id} not found directly in item_map, searching by vector.")
                    neighbor_indices = self.index.get_nns_by_vector(vector, n + 1, include_distances=False) # +1 чтобы исключить сам трек
                else:
                    logger.warning(f"Track ID {track_id} not found in item_map and has no valid embedding in DB.")
                    return []
            except Track.DoesNotExist:
                logger.warning(f"Track ID {track_id} not found in database.")
                return []
            except Exception as e:
                 logger.error(f"Error searching by vector for track ID {track_id}: {e}")
                 return []
        else:
             # Ищем по внутреннему индексу Annoy
            logger.info(f"Searching neighbors for Annoy index {annoy_idx} (Track ID: {track_id})")
            neighbor_indices = self.index.get_nns_by_item(annoy_idx, n + 1, include_distances=False) # +1 чтобы исключить сам трек

        # Преобразуем индексы Annoy обратно в ID треков, исключая сам исходный трек
        neighbor_track_ids = []
        for neighbor_idx in neighbor_indices:
            neighbor_track_id = self.item_map.get(neighbor_idx)
            if neighbor_track_id is not None and neighbor_track_id != track_id:
                neighbor_track_ids.append(neighbor_track_id)
            # Если поиск шел по вектору, а не по item, то self.item_map может быть неполным
            # В этом случае просто возвращаем ID, которые нашлись в карте
            elif annoy_idx is None and neighbor_track_id is not None:
                 neighbor_track_ids.append(neighbor_track_id)

        return neighbor_track_ids[:n] # Возвращаем не более n соседей

# Создаем один экземпляр сервиса для использования в приложении
# Он будет инициализирован и попытается загрузить индекс при старте Django
annoy_service = AnnoyService() 