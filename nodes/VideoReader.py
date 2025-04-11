import os
import json
import time
import logging
from typing import Generator
import cv2
from elements.FrameElement import FrameElement
from elements.VideoEndBreakElement import VideoEndBreakElement

logger = logging.getLogger(__name__)

def check_video_file(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Error: Unable to open video file at {video_path}")
        return False
    logger.info("Video opened successfully")
    cap.release()
    return True

class VideoReader:
    def __init__(self, config: dict) -> None:
        self.video_pth = config["src"]
        self.video_source = f"Processing of {self.video_pth}"
        
        # Проверка существования файла или камеры
        if not (
            os.path.isfile(self.video_pth)
            or isinstance(self.video_pth, int)
            or "://" in self.video_pth
        ):
            raise FileNotFoundError(f"VideoReader| Файл {self.video_pth} не найден")

        # Инициализация видеопотока
        self.stream = cv2.VideoCapture(self.video_pth)

        # Параметры пропуска кадров
        self.skip_secs = config.get("skip_secs", 0)
        self.last_frame_timestamp = -1  # Отрицательное значение для инициализации
        self.first_timestamp = 0  # Время первого кадра

        self.break_element_sent = False  # Флаг отправки элемента завершения потока

        # Настройка разрешения для камеры
        if isinstance(self.video_pth, int):
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        # Загрузка данных о дорогах из JSON-файла
        try:
            with open(config["roads_info"], "r") as file:
                data_json = json.load(file)
            self.roads_info = {
                key: [int(value) for value in values] for key, values in data_json.items()
            }
        except Exception as e:
            logger.error(f"Failed to load roads info from {config['roads_info']}: {e}")
            self.roads_info = {}

    def process(self) -> Generator[FrameElement, None, None]:
        frame_number = 0

        # Создание объекта FrameElement
        frame_element = FrameElement(
            source="video.mp4",
            frame=np.zeros((1080, 1920, 3)),
            timestamp=123.45,
            frame_num=1,
            roads_info={},
            file_id="test_file_id",
            data={"key": "value"},
        )

        # Проверка сериализации
        try:
            serialized_data = json.dumps(frame_element.__dict__)
            logger.debug(f"Serialized data: {serialized_data}")
        except Exception as e:
            logger.error(f"Serialization error: {e}")

        # Десериализация
        try:
            deserialized_data = json.loads(serialized_data)
            logger.debug(f"Deserialized data: {deserialized_data}")
        except Exception as e:
            logger.error(f"Deserialization error: {e}")

        while True:
            ret, frame = self.stream.read()
            if not ret:
                logger.warning("Can't receive frame (stream end?). Exiting ...")
                if not self.break_element_sent:
                    self.break_element_sent = True

                    if not self.video_pth:
                        logger.error("Video path is not set. Cannot create VideoEndBreakElement.")
                        break
            if not ret:
                logger.warning("Can't receive frame (stream end?). Exiting ...")
                if not self.break_element_sent:
                    self.break_element_sent = True
                    yield VideoEndBreakElement(
                        video_source=self.video_pth,
                        timestamp=self.last_frame_timestamp,
                        file_id=str(self.video_pth),  # Преобразуем file_id в строку
                    )
                break

            # Вычисление временной метки
            if isinstance(self.video_pth, int) or "://" in self.video_pth:
                # Для камеры
                if frame_number == 0:
                    self.first_timestamp = time.time()
                timestamp = time.time() - self.first_timestamp
            else:
                # Для видеофайла
                timestamp = self.stream.get(cv2.CAP_PROP_POS_MSEC) / 1000
                timestamp = (
                    timestamp
                    if timestamp > self.last_frame_timestamp
                    else self.last_frame_timestamp + 0.1
                )

            # Пропуск кадров при необходимости
            if abs(self.last_frame_timestamp - timestamp) < self.skip_secs:
                continue

            self.last_frame_timestamp = timestamp
            frame_number += 1

            file_id = str(self.video_pth) if isinstance(self.video_pth, (str, int)) else "unknown"
            yield FrameElement(
                source=self.video_source,
                frame=frame,
                timestamp=timestamp,
                frame_num=frame_number,
                roads_info=self.roads_info,
                file_id=str(self.video_pth),  # Преобразуем file_id в строку
                data={"file_id": str(self.video_pth), "key": "value"},  # Пример данных
            )