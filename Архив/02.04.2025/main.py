import os
import uuid
from fastapi import FastAPI, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from prometheus_client import start_http_server, Counter
import hydra
from hydra.core.config_store import ConfigStore
from nodes.VideoReader import VideoReader
from nodes.DetectionTrackingNodes import DetectionTrackingNodes
from nodes.TrackerInfoUpdateNode import TrackerInfoUpdateNode
from nodes.CalcStatisticsNode import CalcStatisticsNode
from nodes.SendInfoDBNode import SendInfoDBNode
from nodes.FlaskServerVideoNode import VideoServer
from elements.VideoEndBreakElement import VideoEndBreakElement
import requests
from dataclasses import dataclass
from some_module.AppConfig import AppConfig
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware


# Используйте AppConfig
config = AppConfig()
print(config.param1)

#response = requests.get("http://5.44.45.89:2222/api/status")

# Метрики Prometheus
REQUEST_COUNT = Counter('processed_videos', 'Total processed videos')
PROCESSING_TIME = Counter('processing_seconds', 'Total processing time')

app = FastAPI()

# Добавляем middleware для CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все методы (GET, POST и т.д.)
    allow_headers=["*"],  # Разрешаем все заголовки
)

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

# Инициализация Hydra
cs = ConfigStore.instance()
cs.store(name="app_config", node=AppConfig)

class AppConfig:
    video_reader: dict = {}
    pipeline: dict = {}

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

@app.on_event("startup")
async def startup_event():
    """Запуск метрик при старте"""
    start_http_server(8000)

@app.post("/process")
async def process_video(file: UploadFile, background_tasks: BackgroundTasks):
    """Основной эндпоинт для обработки видео"""
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
    """Фоновая задача обработки видео"""
    @hydra.main(version_base=None, config_path="/app/configs", config_name="app_config")
    def wrapped_main(cfg):
        pipeline = init_pipeline(cfg)
        
        for frame_element in pipeline["video_reader"].process(video_path):
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

@app.get("/metrics")
async def metrics():
    """Эндпоинт для Prometheus"""
    from prometheus_client import generate_latest
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)