import os
import uuid
from fastapi import FastAPI, UploadFile, BackgroundTasks, File
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import start_http_server, Counter, generate_latest
import hydra
from hydra.core.config_store import ConfigStore
from hydra.core.global_hydra import GlobalHydra
from nodes.VideoReader import VideoReader
from nodes.DetectionTrackingNodes import DetectionTrackingNodes
from nodes.TrackerInfoUpdateNode import TrackerInfoUpdateNode
from nodes.CalcStatisticsNode import CalcStatisticsNode
from nodes.SendInfoDBNode import SendInfoDBNode
from nodes.FlaskServerVideoNode import VideoServer
from elements.VideoEndBreakElement import VideoEndBreakElement
from dataclasses import dataclass
from some_module.AppConfig import AppConfig
import psycopg2
from contextlib import asynccontextmanager
import time
from elements.FrameElement import FrameElement
import json
import logging

# Настройка логгера
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


logger = logging.getLogger(__name__)

# Функция для проверки конфигурации
def validate_config(config):
    required_params = ["db_name", "db_user", "db_password", "db_host", "db_port"]
    for param in required_params:
        if not hasattr(config, param):
            raise ValueError(f"Missing required configuration parameter: {param}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запуск метрик при старте
    start_http_server(8000)
    yield

app = FastAPI(lifespan=lifespan)

# Добавление CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все источники
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все методы (GET, POST, PUT, DELETE и т.д.)
    allow_headers=["*"],  # Разрешить все заголовки
)

# Метрики Prometheus
REQUEST_COUNT = Counter('processed_videos', 'Total processed videos')
PROCESSING_TIME = Counter('processing_seconds', 'Total processing time')

@app.post("/process")
async def process_frame():
    # Создаем объект FrameElement
    frame_element = FrameElement(
        source="test_source",
        frame=None,
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

    # Отправка данных
    return {"status": "success", "data": serialized_data}

# Маршрут для получения результатов
@app.get("/results")
async def get_results():
    # Логика получения результатов
    return {"status": "success", "data": []}

@app.post("/process")
async def process_video(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    REQUEST_COUNT.inc()
    
    # Сохранение файла
    file_id = uuid.uuid4().hex
    filename = f"{file_id}_{file.filename}"
    save_path = f"/app/uploads/{filename}"
    
    with open(save_path, "wb") as buffer:
        buffer.write(await file.read())

    # Запуск обработки в фоне
    background_tasks.add_task(run_processing, save_path, file_id)
    
    return JSONResponse(
        content={"status": "processing", "id": file_id},
        status_code=202
    )

def run_processing(video_path, file_id):
    try:
        # Очистка состояния Hydra перед каждым вызовом
        if GlobalHydra.instance().is_initialized():
            GlobalHydra.instance().clear()

        @hydra.main(version_base=None, config_path="/app/configs", config_name="app_config")
        def wrapped_main(cfg):
            validate_config(cfg)
            cfg.video_reader.src = video_path
            pipeline = init_pipeline(cfg)
            
            for frame_element in pipeline["video_reader"].process():
                frame_element = pipeline["detection_node"].process(frame_element)
                frame_element = pipeline["tracker_node"].process(frame_element)
                frame_element = pipeline["stats_node"].process(frame_element)
                
                if pipeline["db_node"]:
                    frame_element = pipeline["db_node"].process(frame_element)
                    
                if pipeline["video_server"]:
                    if isinstance(frame_element, VideoEndBreakElement):
                        break
                    pipeline["video_server"].update_image(frame_element.frame_result)
        
        wrapped_main()
        print(f"Processing completed for video: {file_id}")
        save_to_db(file_id, os.path.basename(video_path), "completed", {"objects_detected": 10})

    except Exception as e:
        print(f"Error processing video {file_id}: {e}")
        save_to_db(file_id, os.path.basename(video_path), "failed")

def init_pipeline(config):
    """Инициализация всех узлов обработки"""
    return {
        "video_reader": VideoReader(config.video_reader),
        "detection_node": DetectionTrackingNodes(config),
        "tracker_node": TrackerInfoUpdateNode(config),
        "stats_node": CalcStatisticsNode(config),
        "db_node": SendInfoDBNode(config) if config.pipeline.send_info_db else None,
        "video_server": VideoServer(config) if config.pipeline.show_in_web else None
    }

def save_to_db(file_id, filename, status, result=None):
    """Сохранение данных в PostgreSQL"""
    try:
        conn = psycopg2.connect(
            dbname="traffic_analyzer_db",
            user="user",
            password="pwd",
            host="pg_data_wh",
            port=5432
        )
        cursor = conn.cursor()
        query = """
        INSERT INTO processed_videos (file_id, filename, status, result)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (file_id, filename, status, result))
        conn.commit()
        print(f"Saved to DB: file_id={file_id}, status={status}")
    except Exception as e:
        print(f"Error saving to DB: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/")
def read_root():
    return {"message": "API is running"}

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content)
    }

@app.get("/stats")
async def get_stats():
    """Получение статистики по загруженным видео"""
    try:
        conn = psycopg2.connect(
            dbname="traffic_analyzer_db",
            user="user",
            password="pwd",
            host="pg_data_wh"
        )
        cursor = conn.cursor()
        query = """
        SELECT 
            date_trunc('hour', upload_time) AS hour,
            COUNT(*) AS total_videos,
            SUM((result->>'objects_detected')::INT) AS total_objects_detected
        FROM 
            processed_videos
        GROUP BY 
            hour
        ORDER BY 
            hour;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Преобразуем результаты в JSON
        stats = [
            {"hour": row[0].isoformat(), "total_videos": row[1], "total_objects_detected": row[2]}
            for row in rows
        ]
        return JSONResponse(content=stats)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/metrics")
async def metrics():
    """Эндпоинт для Prometheus"""
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )

@app.get("/status/{file_id}")
def get_status(file_id: str):
    try:
        conn = psycopg2.connect(
            dbname="traffic_analyzer_db",
            user="user",
            password="pwd",
            host="pg_data_wh"
        )
        cursor = conn.cursor()
        query = "SELECT * FROM traffic_info WHERE file_id = %s"
        cursor.execute(query, (file_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row is None:
            return {"error": "File ID not found"}, 404

        # Возвращаем данные из базы данных
        return {
            "file_id": row[1],
            "timestamp": row[2],
            "data": row[3]
        }
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)