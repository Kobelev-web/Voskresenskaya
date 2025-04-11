# some_module/AppConfig.py
from dataclasses import dataclass

@dataclass
class AppConfig:
    # Определите поля конфигурации здесь
    param1: str = "default_value"
    param2: int = 42