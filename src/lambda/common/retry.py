"""Exponential backoff with jitter decorator."""

import functools
import random
import time
from typing import Callable, Tuple, Type

from common.exceptions import NonRetryableError, RetryableError
from common.logger import get_logger

logger = get_logger(__name__)


def exponential_backoff_with_jitter(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (RetryableError,),
) -> Callable:
    """Decorator implementing exponential backoff with full jitter.

    sleep = random(0, min(max_delay, base_delay * 2^attempt))
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        logger.error(
                            "All %d retry attempts exhausted for %s",
                            max_attempts,
                            func.__name__,
                            exc_info=True,
                        )
                        raise
                    delay = random.uniform(
                        0, min(max_delay, base_delay * (2**attempt))
                    )
                    logger.warning(
                        "Attempt %d/%d for %s failed: %s. Retrying in %.2fs",
                        attempt + 1,
                        max_attempts,
                        func.__name__,
                        str(e),
                        delay,
                    )
                    time.sleep(delay)
                except NonRetryableError:
                    raise
            raise last_exception  # pragma: no cover

        return wrapper

    return decorator
