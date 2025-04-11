from elements.FrameElement import FrameElement
import logging

logger = logging.getLogger(__name__)


class VideoEndBreakElement(FrameElement):
    def __init__(self, video_source: str, timestamp: float, file_id: str) -> None:
        logger.debug(
            f"Creating VideoEndBreakElement with video_source={video_source}, "
            f"timestamp={timestamp}, file_id={file_id}"
        )
        super().__init__(
            source=video_source,
            frame=None,  # У VideoEndBreakElement нет кадра
            timestamp=timestamp,
            frame_num=-1,  # Указываем -1, так как это элемент завершения
            roads_info={},  # Пустой словарь для информации о дорогах
            file_id=file_id,  # Уникальный идентификатор файла
            data={"key": "value"},  # Пример данных (можно сделать опциональным)
        )