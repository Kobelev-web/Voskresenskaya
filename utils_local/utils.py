import logging
import time
import numpy as np
from shapely.geometry import Point, Polygon
from typing import Dict, List, Optional, Tuple

logger_profile = logging.getLogger("profile")


def profile_time(func):
    """Декоратор для измерения времени выполнения функции."""
    def exec_and_print_status(*args, **kwargs):
        t_start = time.time()
        out = func(*args, **kwargs)
        t_end = time.time()
        dt_msecs = (t_end - t_start) * 1000

        # Логируем имя класса, имя функции и время выполнения
        self = args[0] if args and hasattr(args[0], "__class__") else None
        class_name = self.__class__.__name__ if self else "UnknownClass"
        logger_profile.debug(
            f"{class_name}.{func.__name__}, time spent {dt_msecs:.2f} msecs, "
            f"args: {args}, kwargs: {kwargs}"
        )
        return out

    return exec_and_print_status


class FPS_Counter:
    def __init__(self, calc_time_perion_N_frames: int) -> None:
        """
        Счетчик FPS по ограниченным участкам видео (скользящему окну).

        Args:
            calc_time_perion_N_frames (int): количество фреймов окна подсчета статистики.
        """
        self.time_buffer: List[float] = []
        self.calc_time_perion_N_frames = calc_time_perion_N_frames

    @profile_time
    def calc_FPS(self) -> float:
        """Производит расчет FPS по нескольким кадрам видео.

        Returns:
            float: значение FPS.
        """
        time_buffer_is_full = len(self.time_buffer) == self.calc_time_perion_N_frames
        t = time.time()
        self.time_buffer.append(t)

        if time_buffer_is_full:
            self.time_buffer.pop(0)
            fps = len(self.time_buffer) / (self.time_buffer[-1] - self.time_buffer[0])
            return np.round(fps, 2)
        else:
            return 0.0


def intersects_central_point(
    tracked_xyxy: List[float], polygons: Dict[str, List[float]]
) -> Optional[int]:
    """
    Функция определяет присутствие центральной точки bbox в области полигонов дорог.

    Args:
        tracked_xyxy (List[float]): координаты bbox в формате [x1, y1, x2, y2].
        polygons (Dict[str, List[float]]): словарь полигонов, где ключ — номер дороги,
            а значение — список координат вершин полигона.

    Returns:
        Optional[int]: либо None, либо значение ключа (номер дороги — int).
    """
    try:
        # Проверка входных данных
        if not isinstance(tracked_xyxy, list) or len(tracked_xyxy) != 4:
            raise ValueError("tracked_xyxy must be a list of 4 floats.")
        if not isinstance(polygons, dict):
            raise ValueError("polygons must be a dictionary.")

        # Центральная точка bbox
        center_point = Point(
            [(tracked_xyxy[0] + tracked_xyxy[2]) / 2, (tracked_xyxy[1] + tracked_xyxy[3]) / 2]
        )

        # Преобразование полигонов в объекты Polygon
        polygon_objects = {
            key: Polygon([(polygon[i], polygon[i + 1]) for i in range(0, len(polygon), 2)])
            for key, polygon in polygons.items()
        }

        # Проверка пересечения центральной точки с полигонами
        for key, polygon in polygon_objects.items():
            if polygon.contains(center_point):
                return int(key)

        return None

    except Exception as e:
        logger_profile.error(f"Error in intersects_central_point: {e}")
        return None