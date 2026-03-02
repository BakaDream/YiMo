from enum import Enum
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel

from yimo.utils.yaml_utils import dump_yaml, load_yaml

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class TranslationTask(BaseModel):
    source_path: Path
    dest_path: Path
    status: TaskStatus = TaskStatus.PENDING
    error_message: Optional[str] = None
    is_resource: bool = False
    retries: int = 0

    @property
    def name(self) -> str:
        return self.source_path.name

    def mark_processing(self):
        self.status = TaskStatus.PROCESSING
        self.error_message = None

    def mark_completed(self):
        self.status = TaskStatus.COMPLETED
        self.error_message = None

    def mark_failed(self, error: str):
        self.status = TaskStatus.FAILED
        self.error_message = error

    def mark_skipped(self):
        self.status = TaskStatus.SKIPPED
        
    def reset(self):
        self.status = TaskStatus.PENDING
        self.error_message = None
        self.retries = 0
        
    def mark_pending_retry(self, error: str):
        """Mark as pending but keep error message for visibility of retry reason."""
        self.status = TaskStatus.PENDING
        self.error_message = error

class ProjectState(BaseModel):
    source_dir: Path
    dest_dir: Path
    tasks: List[TranslationTask]
    source_language: str = "English"
    target_language: str = "简体中文"

    def save_to_file(self, path: Path):
        dump_yaml(Path(path), self.model_dump(mode="json"))

    @classmethod
    def load_from_file(cls, path: Path) -> 'ProjectState':
        data = load_yaml(Path(path))
        return cls.model_validate(data)
