from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx


def with_ai_retry(func):
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, ConnectionError, Exception)),
        reraise=True,
    )(func)
