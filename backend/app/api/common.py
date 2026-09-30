from fastapi import HTTPException

from ..config import get_settings


def validate_service(service: str | None):
    if service is not None and service not in get_settings().service_urls:
        raise HTTPException(422, "Unknown service identifier")
    return service
