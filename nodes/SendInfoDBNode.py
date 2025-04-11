import time
import logging
import psycopg2
import json

from elements.FrameElement import FrameElement
from elements.VideoEndBreakElement import VideoEndBreakElement
from utils_local.utils import profile_time

logger = logging.getLogger(__name__)


class SendInfoDBNode:
    def __init__(self, config: dict) -> None:
        config_db = config["send_info_db_node"]
        self.drop_table = config_db["drop_table"]
        self.how_often_add_info = config_db["how_often_add_info"]
        self.table_name = config_db["table_name"]
        self.last_db_update = time.time()

        # Логирование имени таблицы
        logger.debug(f"Using table name: {self.table_name}")

        self.last_db_update = time.time()

        # Параметры подключения к базе данных
        db_connection = config_db["connection_info"]
        conn_params = {
            "user": db_connection["user"],
            "password": db_connection["password"],
            "host": db_connection["host"],
            "port": "5432",
            "database": db_connection["database"],
        }

        # Время буферизации данных
        self.buffer_analytics_sec = (
            config["general"]["buffer_analytics"] * 60
            + config["general"]["min_time_life_track"]
        )

        # Подключение к базе данных
        try:
            self.connection = psycopg2.connect(**conn_params)
            logger.info("Successfully connected to PostgreSQL")
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while connecting to PostgreSQL: {error}")
            raise  # Прерываем выполнение, если не удалось подключиться

        # Создание курсора для выполнения SQL-запросов
        self.cursor = self.connection.cursor()

        # Удаление таблицы, если требуется
        if self.drop_table:
            drop_table_query = f"DROP TABLE IF EXISTS {self.table_name};"
            try:
                self.cursor.execute(drop_table_query)
                self.connection.commit()
                logger.info(f"The table {self.table_name} has been deleted")
            except (Exception, psycopg2.Error) as error:
                logger.error(f"Error while dropping table: {error}")

        # Создание таблицы
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id SERIAL PRIMARY KEY,
            file_id VARCHAR(255),
            timestamp FLOAT,
            data JSONB  -- Используем тип JSONB для хранения словарей
        );
        """
        try:
            self.cursor.execute(create_table_query)
            self.connection.commit()
            logger.info(f"Table {self.table_name} created successfully")
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while creating table: {error}")
            raise  # Прерываем выполнение, если не удалось создать таблицу

    @profile_time
    def process(self, frame_element) -> FrameElement:
        # Обработка VideoEndBreakElement
        if isinstance(frame_element, VideoEndBreakElement):
            logger.info("Received VideoEndBreakElement. Skipping database save.")
            return frame_element

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

        # Проверка типа входного элемента
        assert isinstance(
            frame_element, FrameElement
        ), f"SendInfoDBNode | Неправильный формат входного элемента {type(frame_element)}"

        # Проверка наличия обязательных атрибутов
        if not all([hasattr(frame_element, "file_id"), hasattr(frame_element, "timestamp"), hasattr(frame_element, "data")]):
            logger.error("Missing required attributes in FrameElement")
            raise ValueError("FrameElement is missing required attributes")

        # Получение значений для записи в базу данных
        info_dictionary = getattr(frame_element, "data", {})
        timestamp = getattr(frame_element, "timestamp", None)

        # Проверка наличия обязательных ключей в info_dictionary
        file_id = info_dictionary.get("file_id")
        if not file_id:
            logger.error("Missing 'file_id' in info_dictionary")
            return frame_element

        # Проверка, нужно ли отправлять информацию в базу данных
        current_time = time.time()
        if current_time - self.last_db_update >= self.how_often_add_info:
            self._insert_in_db(info_dictionary, timestamp)
            frame_element.send_info_of_frame_to_db = True
            self.last_db_update = current_time  # Обновление времени последнего обновления

        return frame_element

    def _insert_in_db(self, info_dictionary: dict, timestamp: float) -> None:
        insert_query = f"""
        INSERT INTO {self.table_name} (file_id, timestamp, data)
        VALUES (%s, %s, %s);
        """
        try:
            file_id = info_dictionary.get("file_id")
            if not file_id:
                raise ValueError("Missing 'file_id' in info_dictionary")
            data_json = json.dumps(info_dictionary)  # Преобразование словаря в JSON
            logger.debug(f"Inserting data into DB: file_id={file_id}, timestamp={timestamp}, data={info_dictionary}")
            logger.debug(f"Data to be saved in DB: {data_json}")
            self.cursor.execute(insert_query, (file_id, timestamp, data_json))
            self.connection.commit()
            logger.info("Successfully inserted data into PostgreSQL")
            self.cursor.execute(
                insert_query,
                (
                    info_dictionary.get("file_id"),
                    info_dictionary.get("timestamp"),
                    data_json,  # Преобразованный словарь
                ),
            )
            self.connection.commit()
            logger.info("Successfully inserted data into PostgreSQL")
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while inserting data into PostgreSQL: {error}")
            self.connection.rollback()  # Откат транзакции
            raise

    def save_to_db(self, file_id, timestamp, data_dict):
        insert_query = f"""
        INSERT INTO {self.table_name} (file_id, timestamp, data)
        VALUES (%s, %s, %s);
        """
        try:
            data_json = json.dumps(data_dict)  # Преобразование словаря в JSON
            self.cursor.execute(insert_query, (file_id, timestamp, data_json))
            self.connection.commit()
            logger.info("Successfully inserted data into PostgreSQL")
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while inserting data into PostgreSQL: {error}")
            self.connection.rollback()
            raise
