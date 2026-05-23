import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = structlog.get_logger()


class N8NAPIError(Exception):
    pass


class N8NClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = 30.0

    @property
    def _headers(self) -> dict:
        return {
            "X-N8N-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # Fields n8n 2.x treats as server-managed (read-only on create/update)
    _READONLY_FIELDS = frozenset({"active", "meta", "id", "createdAt", "updatedAt", "versionId", "usedCredentials"})

    def _strip_readonly(self, data: dict) -> dict:
        return {k: v for k, v in data.items() if k not in self._READONLY_FIELDS}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    def create_workflow(self, workflow_data: dict) -> str:
        payload = self._strip_readonly(workflow_data)
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/api/v1/workflows",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            workflow_id = data.get("id") or data.get("data", {}).get("id")
            if not workflow_id:
                raise N8NAPIError(f"n8n did not return workflow ID. Response: {data}")
            logger.info("Workflow created in n8n", workflow_id=workflow_id)
            return str(workflow_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    def update_workflow(self, workflow_id: str, workflow_data: dict) -> None:
        payload = self._strip_readonly(workflow_data)
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.put(
                f"{self.base_url}/api/v1/workflows/{workflow_id}",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            logger.info("Workflow updated in n8n", workflow_id=workflow_id)

    def trigger_ingestion(self, payload: dict) -> None:
        webhook_url = f"{self.base_url}/webhook/content-ingestion"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
            logger.info("Triggered n8n ingestion workflow", content_item_id=payload.get("content_item_id"))

    def list_workflows(self) -> list[dict]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base_url}/api/v1/workflows", headers=self._headers)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("data", [])

    def health_check(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/healthz")
                return resp.status_code < 400
        except Exception:
            return False

    @classmethod
    def from_app_config(cls, config: dict) -> "N8NClient":
        return cls(
            base_url=config.get("N8N_BASE_URL", "http://n8n:5678"),
            api_key=config.get("N8N_API_KEY", ""),
        )
