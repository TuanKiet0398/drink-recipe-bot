from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus scrape endpoint.

    Deliberately unauthenticated — Prometheus cannot send Basic Auth — and
    deliberately unpublished: nginx proxies only /admin/, and the backend
    binds no host port in production, so this is reachable only from inside
    the Docker network.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
