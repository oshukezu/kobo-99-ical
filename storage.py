import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List
from datetime import date, datetime

from .models import BookItem

logger = logging.getLogger(__name__)


class DateEncoder(json.JSONEncoder):
    """JSON encoder that converts date/datetime to ISO format"""
    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)


class Storage:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[BookItem]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return [BookItem.from_dict(item) for item in data]
        except Exception as exc:
            logger.warning("Failed to load storage %s: %s", self.path, exc)
            return []

    def save(self, items: Iterable[BookItem]) -> None:
        try:
            serialized = [asdict(item) for item in items]
            logger.info("Saving %d items to %s", len(serialized), self.path)
            
            # 確保目錄存在
            self.path.parent.mkdir(parents=True, exist_ok=True)
            
            with self.path.open("w", encoding="utf-8") as f:
                # 使用 DateEncoder 來處理 date/datetime
                json.dump(serialized, f, ensure_ascii=False, indent=2, cls=DateEncoder)
            
            # 驗證檔案是否成功寫入
            if self.path.exists():
                file_size = self.path.stat().st_size
                logger.info("Successfully saved %d items to %s (file size: %d bytes)", 
                           len(serialized), self.path, file_size)
            else:
                logger.error("Failed to save: file %s does not exist after write", self.path)
                raise IOError(f"File {self.path} was not created")
        except Exception as e:
            logger.error("Failed to save items to %s: %s", self.path, e, exc_info=True)
            raise


# 以下是原程式碼
    # def save(self, items: Iterable[BookItem]) -> None:
        # serialized = [asdict(item) for item in items]
        # with self.path.open("w", encoding="utf-8") as f:
            # json.dump(serialized, f, ensure_ascii=False, indent=2)

