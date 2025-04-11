import numpy as np
import time
import logging

logger = logging.getLogger(__name__)


class FrameElement:
    def __init__(
        self,
        source: str,
        frame: np.ndarray,
        timestamp: float,
        frame_num: int,
        roads_info: dict,
        file_id: str,  # Уникальный идентификатор файла
        data: dict = None,  # Дополнительные данные (по умолчанию пустой словарь)
        frame_result: np.ndarray = None,
        detected_conf: list = None,
        detected_cls: list = None,
        detected_xyxy: list = None,
        tracked_conf: list = None,
        tracked_cls: list = None,
        tracked_xyxy: list = None,
        id_list: list = None,
        buffer_tracks: dict = None,
    ) -> None:
        self.source = source
        self.frame = frame
        self.timestamp = timestamp
        self.frame_num = frame_num
        self.roads_info = roads_info
        self.file_id = file_id  # Уникальный идентификатор файла
        self.data = data if data is not None else {}  # Дополнительные данные

        # Убедимся, что в data есть file_id
        if "file_id" not in self.data:
            self.data["file_id"] = file_id

        self.frame_result = frame_result
        self.timestamp_date = time.time()  # Текущее время создания объекта
        self.detected_conf = detected_conf if detected_conf is not None else []
        self.detected_cls = detected_cls if detected_cls is not None else []
        self.detected_xyxy = detected_xyxy if detected_xyxy is not None else []
        self.tracked_conf = tracked_conf if tracked_conf is not None else []
        self.tracked_cls = tracked_cls if tracked_cls is not None else []
        self.tracked_xyxy = tracked_xyxy if tracked_xyxy is not None else []
        self.id_list = id_list if id_list is not None else []
        self.buffer_tracks = buffer_tracks if buffer_tracks is not None else {}
        self.send_info_of_frame_to_db = True  # Флаг для отправки данных в базу
        logger.debug(f"Created FrameElement with file_id={file_id}, timestamp={timestamp}")

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "frame_num": self.frame_num,
            "roads_info": self.roads_info,
            "file_id": self.file_id,
            "data": self.data,
            "detected_conf": self.detected_conf,
            "detected_cls": self.detected_cls,
            "detected_xyxy": self.detected_xyxy,
            "tracked_conf": self.tracked_conf,
            "tracked_cls": self.tracked_cls,
            "tracked_xyxy": self.tracked_xyxy,
            "id_list": self.id_list,
            "buffer_tracks": self.buffer_tracks,
        }