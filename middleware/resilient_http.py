import random
import threading
import time
from dataclasses import dataclass

import httpx

from middleware.structured_logging import log_json


@dataclass
class ResilientResult:
    payload: dict
    fallback: bool
    source: str


class ResilientFallback(Exception):
    def __init__(self, message: str, payload: dict | None = None, source: str = "none"):
        super().__init__(message)
        self.payload = payload
        self.source = source


class ResilientHttpClient:
    def __init__(
        self,
        service_name: str,
        timeout_seconds: float = 2.0,
        max_retries: int = 3,
        base_backoff: float = 0.5,
        jitter: float = 0.25,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_reset_seconds: int = 30,
    ):
        self.service_name = service_name
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.jitter = jitter
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_seconds = circuit_breaker_reset_seconds
        self._circuit_open_until = 0.0
        self._consecutive_failures = 0
        self._lock = threading.Lock()
        self._cache = {}
        self.client = httpx.Client(timeout=httpx.Timeout(timeout_seconds))

    def close(self):
        self.client.close()

    def _sleep_with_backoff(self, attempt: int):
        delay = min((2 ** attempt) * self.base_backoff, 8.0)
        delay += random.uniform(0, self.jitter)
        time.sleep(delay)

    def _record_failure(self, error, url: str, attempt: int):
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.circuit_breaker_threshold:
                self._circuit_open_until = time.monotonic() + self.circuit_breaker_reset_seconds
                retry_after = max(0, round(self._circuit_open_until - time.monotonic(), 1))
                log_json(
                    "error",
                    self.service_name,
                    "circuit_opened",
                    error,
                    url=url,
                    attempt=attempt + 1,
                    retry_after_seconds=retry_after,
                )
            else:
                log_json(
                    "error",
                    self.service_name,
                    "http_call_failed",
                    error,
                    url=url,
                    attempt=attempt + 1,
                )

    def _record_success(self):
        with self._lock:
            self._consecutive_failures = 0
            self._circuit_open_until = 0.0

    def _get_cached(self, key: str):
        with self._lock:
            return self._cache.get(key)

    def _store_cache(self, key: str, payload: dict):
        with self._lock:
            self._cache[key] = payload

    def get_json(self, url: str, cache_key: str | None = None) -> ResilientResult:
        cache_key = cache_key or url
        now = time.monotonic()

        with self._lock:
            if self._circuit_open_until > now:
                cached_payload = self._cache.get(cache_key)
                if cached_payload is not None:
                    log_json(
                        "warning",
                        self.service_name,
                        "fallback_to_cache",
                        f"Circuit breaker aberto para {url}",
                        url=url,
                        source="cache",
                        retry_after_seconds=max(0, round(self._circuit_open_until - now, 1)),
                    )
                    return ResilientResult(payload=cached_payload, fallback=True, source="cache")
                raise ResilientFallback(
                    f"Circuit breaker aberto para {url}. Sem dados em cache.",
                    source="none",
                )

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.get(url)
                if response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code >= 400:
                    response.raise_for_status()

                payload = response.json()
                self._record_success()
                self._store_cache(cache_key, payload)
                return ResilientResult(payload=payload, fallback=False, source="remote")
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as error:
                last_error = error
                self._record_failure(error, url, attempt)

                if attempt == self.max_retries - 1:
                    cached_payload = self._get_cached(cache_key)
                    if cached_payload is not None:
                        log_json(
                            "warning",
                            self.service_name,
                            "fallback_to_cache",
                            error,
                            url=url,
                            source="cache",
                        )
                        return ResilientResult(payload=cached_payload, fallback=True, source="cache")

                    raise ResilientFallback(
                        f"Falha ao consultar {url}. Operação em modo degradado.",
                        source="none",
                    ) from error

                self._sleep_with_backoff(attempt)
            except httpx.HTTPStatusError as error:
                last_error = error
                if error.response is not None and error.response.status_code < 500:
                    log_json(
                        "warning",
                        self.service_name,
                        "http_call_rejected",
                        error,
                        url=url,
                        status_code=error.response.status_code,
                    )
                    raise

                self._record_failure(error, url, attempt)

                if attempt == self.max_retries - 1:
                    cached_payload = self._get_cached(cache_key)
                    if cached_payload is not None:
                        log_json(
                            "warning",
                            self.service_name,
                            "fallback_to_cache",
                            error,
                            url=url,
                            source="cache",
                        )
                        return ResilientResult(payload=cached_payload, fallback=True, source="cache")

                    raise ResilientFallback(
                        f"Falha ao consultar {url}. Operação em modo degradado.",
                        source="none",
                    ) from error

                self._sleep_with_backoff(attempt)

        if last_error is not None:
            raise ResilientFallback(
                f"Falha ao consultar {url}. Operação em modo degradado.",
                source="none",
            ) from last_error

        raise RuntimeError(f"Falha inesperada ao consultar {url}")
