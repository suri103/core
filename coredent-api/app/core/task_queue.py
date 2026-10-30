"""
Task Queue Abstraction Layer
Provides optional Redis/Celery support with in-memory fallback for development/small deployments
"""

import logging
import threading
import queue
from datetime import datetime, timedelta, timezone
from typing import Callable, Any, Optional, Dict
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class TaskQueue:
    """
    Unified task queue that works with or without Redis/Celery

    DEV-ONLY WARNING: memory mode is fire-and-forget (ThreadPoolExecutor,
    no retry/persistence/tenant fairness, unbounded RateLimiter dict). Never
    use in production — pass force_mode='celery' when REDIS_URL is set.

    Usage:
        # Automatic detection - uses Celery if REDIS_URL is set
        task_queue = get_task_queue()

        # Explicit mode
        task_queue = get_task_queue(force_mode='celery')  # or 'memory'
    """

    def __init__(self, mode: str = 'auto'):
        self.mode = mode
        self._celery_app = None
        self._memory_queue = None
        self._memory_executor = None
        self._initialized = False

    def _init_celery(self) -> bool:
        """Try to initialize Celery with Redis"""
        try:
            from app.core.celery_app import celery_app as celery
            from celery import chain, group

            self._celery_app = celery
            self._celery_group = group
            self._celery_chain = chain
            logger.info("Task queue: Celery mode enabled (Redis connected)")
            return True
        except ImportError:
            logger.warning("Task queue: Celery not installed")
            return False
        except Exception as e:
            logger.warning(f"Task queue: Celery init failed - {e}")
            return False

    def _init_memory(self):
        """Initialize in-memory queue for development/small deployments.

        Dev-only: no retry, no persistence, no per-tenant fairness. Production
        must use Celery (force_mode='celery' when REDIS_URL is set).
        """
        from app.core.config_simple import settings as _settings

        if _settings.ENVIRONMENT not in ("development", "dev", "test", "testing", "local"):
            logger.error(
                "TaskQueue memory mode requested in non-local ENVIRONMENT=%r — "
                "refusing silent fallback; use force_mode='celery' with REDIS_URL.",
                _settings.ENVIRONMENT,
            )
            raise RuntimeError("TaskQueue memory mode is dev-only; configure Celery/Redis")
        if self._memory_queue is None:
            self._memory_queue = queue.Queue()
            self._memory_executor = ThreadPoolExecutor(max_workers=4)
            self._memory_running = True
            self._memory_thread = threading.Thread(target=self._process_memory_queue, daemon=True)
            self._memory_thread.start()
            logger.info("Task queue: Memory mode enabled (no Redis required)")

    def _process_memory_queue(self):
        """Background thread to process memory queue tasks"""
        while self._memory_running:
            try:
                task_data = self._memory_queue.get(timeout=1)
                if task_data is None:
                    continue

                func = task_data['func']
                args = task_data.get('args', [])
                kwargs = task_data.get('kwargs', {})
                task_id = task_data.get('id', 'unknown')

                try:
                    result = func(*args, **kwargs)
                    logger.debug(f"Memory task {task_id} completed: {result}")
                except Exception as e:
                    logger.error(f"Memory task {task_id} failed: {e}")

                self._memory_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Memory queue processing error: {e}")

    def initialize(self) -> 'TaskQueue':
        """Initialize the task queue"""
        if self._initialized:
            return self

        if self.mode == 'celery':
            self._init_celery()
        elif self.mode == 'memory':
            self._init_memory()
        else:  # auto mode
            if not self._init_celery():
                self._init_memory()

        self._initialized = True
        return self

    @property
    def is_celery(self) -> bool:
        return self._celery_app is not None

    def delay(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        """
        Queue a task for async execution

        Returns:
            Celery AsyncResult if using Celery, None if using memory queue
        """
        if not self._initialized:
            self.initialize()

        if self._celery_app:
            return func.delay(*args, **kwargs)
        else:
            if self._memory_queue is not None:
                self._memory_queue.put({
                    'func': func,
                    'args': args,
                    'kwargs': kwargs,
                    'id': f"task_{datetime.now(timezone.utc).timestamp()}"
                })
            return None

    def apply_async(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        """Alias for delay"""
        return self.delay(func, *args, **kwargs)

    def apply(self, func: Callable, *args, **kwargs) -> Any:
        """Execute synchronously (blocking)"""
        return func(*args, **kwargs)

    def get_result(self, task_id: Any, timeout: float = 5.0) -> Optional[Any]:
        """
        Get result of a task (Celery only for now)
        """
        if self._celery_app and hasattr(task_id, 'get'):
            try:
                return task_id.get(timeout=timeout)
            except Exception as e:
                logger.error(f"Error getting task result: {e}")
                return None
        return None

    def shutdown(self):
        """Clean shutdown of the task queue"""
        self._memory_running = False
        if self._memory_executor:
            self._memory_executor.shutdown(wait=True)
        logger.info("Task queue shutdown complete")


_task_queue_instance: Optional[TaskQueue] = None
_task_queue_lock = threading.Lock()


def get_task_queue(force_mode: str = 'auto') -> TaskQueue:
    """
    Get singleton task queue instance

    Args:
        force_mode: 'celery', 'memory', or 'auto' (default)

    Returns:
        TaskQueue instance
    """
    global _task_queue_instance

    with _task_queue_lock:
        if _task_queue_instance is None:
            _task_queue_instance = TaskQueue(mode=force_mode)
            _task_queue_instance.initialize()
        return _task_queue_instance


def task(func: Callable) -> Callable:
    """
    Decorator to mark a function as a task

    Usage:
        @task
        def send_email_task(user_id: str):
            # task implementation
            pass

        # Then call it async:
        task_queue = get_task_queue()
        task_queue.delay(send_email_task, "user-123")
    """
    def wrapper(*args, **kwargs):
        task_queue = get_task_queue()
        return task_queue.delay(func, *args, **kwargs)

    wrapper.func = func
    wrapper.delay = lambda *a, **k: get_task_queue().delay(func, *a, **k)
    wrapper.apply = lambda *a, **k: func(*a, **k)
    return wrapper


class RateLimiter:
    """
    Simple rate limiter using in-memory storage
    Falls back to Redis-based limiter if available
    """

    def __init__(self):
        self._redis_client = None
        self._memory_store: Dict[str, list] = {}
        self._init_redis()

    def _init_redis(self):
        try:
            from app.core.config_simple import settings
            if settings.REDIS_URL:
                import redis
                self._redis_client = redis.from_url(settings.REDIS_URL)
                logger.info("Rate limiter: Redis mode enabled")
        except Exception as e:
            logger.debug(f"Rate limiter: Redis not available - {e}")

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Check if request is allowed under rate limit

        Args:
            key: Identifier (e.g., "rate_limit:user:123")
            limit: Max requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            True if allowed, False if rate limited
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)

        if self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start.timestamp())
                pipe.zadd(key, {str(now.timestamp()): now.timestamp()})
                pipe.zcard(key)
                pipe.expire(key, window_seconds)
                count = pipe.execute()[-2]

                return count <= limit
            except Exception as e:
                logger.error(f"Redis rate limit error: {e}")

        # Memory fallback
        if key not in self._memory_store:
            self._memory_store[key] = []

        self._memory_store[key] = [
            ts for ts in self._memory_store[key]
            if ts > window_start
        ]

        if len(self._memory_store[key]) < limit:
            self._memory_store[key].append(now)
            return True

        return False


_rate_limiter_instance: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get singleton rate limiter instance"""
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter()
    return _rate_limiter_instance
