# core/annoy_service.py
import logging
import os
import json
from annoy import AnnoyIndex
from django.conf import settings
from .models import Track

logger = logging.getLogger(__name__)

class AnnoyService:
    def __init__(self, dimension=settings.ANNOY_EMBEDDING_DIM, metric=settings.ANNOY_METRIC,
                 index_path=settings.ANNOY_INDEX_PATH, map_path=settings.ANNOY_ITEM_MAP_PATH):
        self.dimension = dimension
        self.metric = metric
        self.index_path = str(index_path)
        self.map_path = str(map_path) # Путь к файлу карты
        self.index = AnnoyIndex(self.dimension, self.metric)
        self.is_loaded = False
        self.item_map = {} # Annoy index -> Track PK
        self._load_index()

    def _load_index(self):
        """Пытается загрузить индекс и карту item_map из файлов."""
        if os.path.exists(self.index_path) and os.path.exists(self.map_path):
            try:
                self.index.load(self.index_path)
                # Загружаем карту из JSON
                with open(self.map_path, 'r') as f:
                    # Ключи в JSON - строки, конвертируем обратно в int
                    loaded_map_str_keys = json.load(f)
                    self.item_map = {int(k): v for k, v in loaded_map_str_keys.items()}
                self.is_loaded = True
                logger.info(f"Annoy index ({self.index.get_n_items()} items) and item map ({len(self.item_map)} items) loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load Annoy index/map: {e}", exc_info=True)
                self.index = AnnoyIndex(self.dimension, self.metric)
                self.item_map = {}
                self.is_loaded = False
        else:
            logger.warning(f"Annoy index file ({self.index_path}) or map file ({self.map_path}) not found. Starting empty.")
            self.is_loaded = False

    def build_index_from_db(self, num_trees=settings.ANNOY_NUM_TREES):
        """Строит индекс Annoy и сохраняет его вместе с картой item_map."""
        logger.info("Starting to build Annoy index from database...")
        self.index = AnnoyIndex(self.dimension, self.metric)
        self.item_map = {}
        annoy_idx_counter = 0

        # Получаем все треки с непустыми эмбеддингами
        tracks_with_embeddings = Track.objects.exclude(embedding__isnull=True).exclude(embedding__exact='null') # JSON 'null'

        if not tracks_with_embeddings.exists():
            logger.warning("No tracks with embeddings found in the database. Annoy index will be empty.")
            # Очищаем старые файлы, если они есть
            if os.path.exists(self.index_path): os.remove(self.index_path)
            if os.path.exists(self.map_path): os.remove(self.map_path)
            return

        # Пересоздаем индекс и карту
        self.index = AnnoyIndex(self.dimension, self.metric)
        self.item_map = {}
        annoy_idx_counter = 0
        
        for track in tracks_with_embeddings:
            embedding = track.embedding
            if isinstance(embedding, list) and len(embedding) == self.dimension:
                self.index.add_item(annoy_idx_counter, embedding)
                self.item_map[annoy_idx_counter] = track.pk # Сохраняем ID трека
                annoy_idx_counter += 1
            else:
                logger.warning(f"Track ID {track.pk} has invalid or missing embedding. Skipping.")

        if annoy_idx_counter > 0:
            logger.info(f"Added {annoy_idx_counter} items to the index. Building {num_trees} trees...")
            self.index.build(num_trees)
            logger.info("Annoy index building complete.")
            try:
                # Сохраняем индекс
                self.index.save(self.index_path)
                logger.info(f"Annoy index saved successfully to {self.index_path}")
                # Сохраняем карту в JSON
                with open(self.map_path, 'w') as f:
                    json.dump(self.item_map, f)
                logger.info(f"Annoy item map saved successfully to {self.map_path}")
                self.is_loaded = True # Считаем загруженным после успешного построения
            except Exception as e:
                logger.error(f"Failed to save Annoy index or map: {e}", exc_info=True)
        else:
            logger.warning("No valid embeddings found to build the index.")
            # Очищаем старые файлы, если они есть
            if os.path.exists(self.index_path): os.remove(self.index_path)
            if os.path.exists(self.map_path): os.remove(self.map_path)

    def find_nearest_neighbors(self, track_id, n=10, threshold=settings.ANNOY_DISTANCE_THRESHOLD, min_results=1):
        """
        Находит ближайших соседей для заданного ID трека.
        Сначала пытается найти до n соседей с расстоянием < threshold.
        Если найдено меньше min_results, возвращает просто n ближайших соседей без порога.
        Возвращает список ID треков.
        """
        if not self.is_loaded:
            logger.warning("Annoy index is not loaded. Cannot find neighbors.")
            return []

        neighbor_indices = []
        neighbor_distances = []

        # Определяем, как искать: по индексу или по вектору
        annoy_idx = None
        search_vector = None
        # TODO: Загрузка item_map
        for idx, pk in self.item_map.items():
             if pk == track_id:
                 annoy_idx = idx
                 break

        if annoy_idx is None:
            try:
                track = Track.objects.get(pk=track_id)
                if track.embedding and isinstance(track.embedding, list) and len(track.embedding) == self.dimension:
                    search_vector = track.embedding
                else:
                    logger.warning(f"Track ID {track_id} not in item_map/DB or no valid embedding.")
                    return []
            except Track.DoesNotExist:
                logger.warning(f"Track ID {track_id} not found in database.")
                return []
            except Exception as e:
                 logger.error(f"Error getting vector for track ID {track_id}: {e}")
                 return []

        # --- Попытка 1: Поиск с порогом --- 
        logger.debug(f"Attempting search for Track ID {track_id} with threshold {threshold}")
        num_candidates = n * 5 + 1 # Ищем больше кандидатов для фильтрации
        try:
            if annoy_idx is not None:
                neighbor_indices, neighbor_distances = self.index.get_nns_by_item(annoy_idx, num_candidates, include_distances=True, search_k=-1)
            elif search_vector is not None:
                neighbor_indices, neighbor_distances = self.index.get_nns_by_vector(search_vector, num_candidates, include_distances=True, search_k=-1)
            else: # Не должно случиться, но на всякий случай
                return []
        except Exception as e:
            logger.error(f"Error during Annoy search (attempt 1) for track {track_id}: {e}")
            return [] # Возвращаем пустой список при ошибке поиска

        filtered_neighbor_ids = []
        for i, idx in enumerate(neighbor_indices):
            distance = neighbor_distances[i]
            neighbor_track_id = self.item_map.get(idx)
            if neighbor_track_id is not None and neighbor_track_id != track_id and distance < threshold:
                filtered_neighbor_ids.append(neighbor_track_id)
                logger.debug(f"  [Thresh] Found neighbor: ID {neighbor_track_id}, Dist: {distance:.4f}")
                if len(filtered_neighbor_ids) >= n:
                    break

        logger.info(f"Found {len(filtered_neighbor_ids)} neighbors for Track ID {track_id} within threshold {threshold}.")

        # --- Попытка 2: Fallback без порога (если найдено < min_results) --- 
        if len(filtered_neighbor_ids) < min_results:
            logger.warning(f"Found less than {min_results} neighbors within threshold. Performing fallback search (top {n}).")
            neighbor_indices_fb = [] # Инициализируем на случай ошибок
            try:
                # Запрашиваем просто n+1 ближайших
                if annoy_idx is not None:
                    # Исправлено: присваиваем результат одной переменной
                    neighbor_indices_fb = self.index.get_nns_by_item(annoy_idx, n + 1, include_distances=False, search_k=-1)
                elif search_vector is not None:
                    # Исправлено: присваиваем результат одной переменной
                    neighbor_indices_fb = self.index.get_nns_by_vector(search_vector, n + 1, include_distances=False, search_k=-1)
                # else: случай обработан ранее, search_vector/annoy_idx должен быть

            except Exception as e:
                logger.error(f"Error during Annoy search (fallback) for track {track_id}: {e}", exc_info=True) # Добавлено exc_info
                # Возвращаем пустой список при ошибке поиска
                return []

            fallback_neighbor_ids = []
            for idx in neighbor_indices_fb:
                neighbor_track_id = self.item_map.get(idx)
                if neighbor_track_id is not None and neighbor_track_id != track_id:
                     fallback_neighbor_ids.append(neighbor_track_id)
                     logger.debug(f"  [Fallback] Found neighbor: ID {neighbor_track_id}")
                     if len(fallback_neighbor_ids) >= n:
                         break
            logger.info(f"Fallback search returning {len(fallback_neighbor_ids)} nearest neighbors.")
            return fallback_neighbor_ids
        else:
            # Возвращаем результаты, отфильтрованные по порогу
            return filtered_neighbor_ids

# Создаем один экземпляр сервиса для использования в приложении
# Он будет инициализирован и попытается загрузить индекс при старте Django
annoy_service = AnnoyService() 