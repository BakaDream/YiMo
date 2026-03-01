import asyncio
import threading
from pathlib import Path
from typing import List, Callable, Optional
from mkdocs_translate.models.config import AppConfig
from mkdocs_translate.models.task import TranslationTask, TaskStatus
from mkdocs_translate.core.translator import Translator
from mkdocs_translate.utils.file_utils import collect_files, classify_file, copy_file, read_file_content, write_file_content
from mkdocs_translate.utils.rate_limiter import RateLimiter

class Processor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.translator = Translator(config)
        self._stop_flag = threading.Event()
        self._loop = None
        
        self.rate_limiter = RateLimiter(config.get_active_provider().rpm_limit)
        
        # To track the main gather task for cancellation
        self._main_task = None
        self._active_tasks = None

    def update_config(self, config: AppConfig):
        self.config = config
        self.translator.update_config(config)
        self.rate_limiter.update_limit(config.get_active_provider().rpm_limit)

    def scan_directory(self, source_dir: Path, output_dir: Path) -> List[TranslationTask]:
        """
        Scan directory and create translation tasks.
        """
        tasks = []
        source_path = Path(source_dir)
        output_path = Path(output_dir)

        # Handle single file input
        if source_path.is_file():
             classification = classify_file(source_path)
             if classification == 'translate':
                 tasks.append(TranslationTask(
                     source_path=source_path,
                     dest_path=output_path,
                     is_resource=False
                 ))
             elif classification == 'resource':
                  tasks.append(TranslationTask(
                     source_path=source_path,
                     dest_path=output_path,
                     is_resource=True
                 ))
             return tasks

        # Handle directory input
        for file_path in collect_files(source_path):
            classification = classify_file(file_path)
            
            # Calculate relative path to preserve structure
            rel_path = file_path.relative_to(source_path)
            dest_file_path = output_path / rel_path

            if classification == 'translate':
                tasks.append(TranslationTask(
                    source_path=file_path,
                    dest_path=dest_file_path,
                    is_resource=False
                ))
            elif classification == 'resource':
                tasks.append(TranslationTask(
                    source_path=file_path,
                    dest_path=dest_file_path,
                    is_resource=True
                ))
        
        return tasks

    async def process_tasks(self, tasks: List[TranslationTask], 
                          on_progress: Optional[Callable[[TranslationTask], None]] = None):
        """
        Process a list of tasks with concurrency control.
        Supports immediate stop by cancelling running tasks and resetting them to PENDING.
        """
        self._stop_flag.clear()
        self._loop = asyncio.get_running_loop()
        self._active_tasks = tasks
        
        max_retries_limit = 1 + self.config.max_retries

        async def worker(task: TranslationTask, semaphore: asyncio.Semaphore, use_rate_limiter: bool):
            # If a task is already processing (e.g. from a previous cancelled run), reset it locally first
            # though the outer loop filter should handle this.
            
            for attempt in range(max_retries_limit):
                try:
                    # Check for stop
                    if self._stop_flag.is_set():
                        if task.status == TaskStatus.PROCESSING:
                            task.reset()
                        return

                    if task.status == TaskStatus.COMPLETED:
                        return

                    async with semaphore:
                        if self._stop_flag.is_set():
                            if task.status == TaskStatus.PROCESSING:
                                task.reset()
                            return

                        task.mark_processing()
                        if on_progress: on_progress(task)

                        if task.is_resource:
                            if self._stop_flag.is_set():
                                task.reset()
                                return
                            await asyncio.to_thread(copy_file, task.source_path, task.dest_path, self._stop_flag)
                            if self._stop_flag.is_set():
                                task.reset()
                                return
                            task.mark_completed()
                            return # Success
                        else:
                            if use_rate_limiter:
                                await self.rate_limiter.acquire()
                            if self._stop_flag.is_set():
                                task.reset()
                                return

                            content = await asyncio.to_thread(read_file_content, task.source_path)
                            if self._stop_flag.is_set():
                                task.reset()
                                return
                            translated_content = await self.translator.translate_markdown(content)
                            if self._stop_flag.is_set():
                                task.reset()
                                return
                            await asyncio.to_thread(write_file_content, task.dest_path, translated_content, self._stop_flag)
                            if self._stop_flag.is_set():
                                task.reset()
                                return
                            task.mark_completed()
                            return # Success

                except asyncio.CancelledError:
                    # IMPORTANT: If cancelled (by stop), revert status to PENDING
                    # so it can be picked up again in the next loop iteration.
                    if task.status == TaskStatus.PROCESSING:
                        task.reset() 
                    raise # Re-raise to ensure gather knows we are cancelled
                except Exception as e:
                    if self._stop_flag.is_set():
                         if task.status == TaskStatus.PROCESSING:
                            task.reset()
                         return

                    task.retries = attempt
                    if attempt == max_retries_limit - 1:
                        task.mark_failed(str(e))
                    else:
                        # Mark as PENDING retry so it doesn't count as active/PROCESSING in UI
                        task.mark_pending_retry(f"Attempt {attempt+1} failed: {str(e)}. Retrying...")
                        if on_progress: on_progress(task)
                        try:
                            await asyncio.sleep(2 * (attempt + 1)) 
                        except asyncio.CancelledError:
                            task.reset()
                            raise
                finally:
                    if on_progress: on_progress(task)

        # Identify tasks that need processing
        pending_tasks = [t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.FAILED)]
        if not pending_tasks:
            self._main_task = None
            self._active_tasks = None
            self._loop = None
            return

        resource_tasks = [t for t in pending_tasks if t.is_resource]
        translation_tasks = [t for t in pending_tasks if not t.is_resource]

        try:
            # Stage 1: Process Resources
            if resource_tasks:
                io_semaphore = asyncio.Semaphore(50)
                self._main_task = asyncio.gather(*(worker(t, io_semaphore, False) for t in resource_tasks))
                await self._main_task

            if self._stop_flag.is_set():
                return

            # Stage 2: Process Translations
            if translation_tasks:
                api_semaphore = asyncio.Semaphore(self.config.max_concurrency)
                self._main_task = asyncio.gather(*(worker(t, api_semaphore, True) for t in translation_tasks))
                await self._main_task

        except asyncio.CancelledError:
            # Stop requested: treat as a clean finish for the worker thread.
            return
        finally:
            self._main_task = None
            self._active_tasks = None
            self._loop = None

    def stop(self):
        """Signal to stop processing immediately."""
        self._stop_flag.set()

        def _cancel_and_reset():
            if self._main_task:
                self._main_task.cancel()
            if self._active_tasks:
                for task in self._active_tasks:
                    if task.status == TaskStatus.PROCESSING:
                        task.reset()

        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(_cancel_and_reset)
        else:
            _cancel_and_reset()
