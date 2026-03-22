from fastapi import APIRouter
import time

router = APIRouter(prefix="/health", tags=["Health Checks"])

START_TIME = time.time()

@router.get("/live")
async def liveness_check():
    """Liveness probe for Kubernetes / Docker."""
    return {"status": "alive", "uptime_seconds": int(time.time() - START_TIME)}

@router.get("/ready")
async def readiness_check():
    """Readiness probe. Can be expanded to check DB/Firebase latency."""
    start = time.time()
    # In a full setup, ping Firestore here. For now, simulate readiness.
    latency_ms = int((time.time() - start) * 1000)
    return {
        "status": "ready",
        "latency_ms": latency_ms,
        "uptime_seconds": int(time.time() - START_TIME)
    }
