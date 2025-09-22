import os
import yaml
from typing import Any, Dict

_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "congfig", "config.yaml"))

class AppConfig:
    def __init__(self, data: Dict[str, Any]):
        self.raw = data
        self.milvus = data.get("milvus", {})
        self.mysql = data.get("mysql", {})
        self.qwen = data.get("qwen", {})
        self.generation = data.get("generation", {})
        self.data = data.get("data", {})


def load_config() -> AppConfig:
    path = os.getenv("FA_CONFIG_PATH", _CONFIG_PATH)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AppConfig(data)
