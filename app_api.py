from flask import Flask, request, jsonify
import os
from werkzeug.utils import secure_filename
from ultralytics import YOLO
import cv2
import uuid

app = Flask(__name__)

# Конфигурация
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB лимит

# Загрузка модели YOLO (при старте API)
model = YOLO('yolov8m.pt')  # Убедитесь, что файл лежит в той же папке

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    # Сохранение файла
    filename = secure_filename(file.filename)
    unique_id = uuid.uuid4().hex
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
    file.save(save_path)

    # Обработка видео
    try:
        results = model.predict(
            source=save_path,
            project=app.config['UPLOAD_FOLDER'],
            name=unique_id,
            save=True,
            conf=0.5  # Порог уверенности
        )
        
        # Путь к результатам
        output_video = os.path.join(app.config['UPLOAD_FOLDER'], unique_id, filename)
        
        return jsonify({
            'message': 'Detection complete',
            'video_path': output_video,
            'results': results[0].tojson()  # JSON с детекциями
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)