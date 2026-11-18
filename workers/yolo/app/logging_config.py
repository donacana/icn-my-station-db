"""Console-only logs; scrub configured credentials and suppress remote payloads."""
import logging
import os
import re

class RedactingFormatter(logging.Formatter):
    def format(self, record):
        value = super().format(record)
        for key in ("WS_TOKEN", "YOLO_WORKER_TOKEN", "YOLO_CAMERA_TOKEN"):
            secret = os.getenv(key)
            if secret:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)Bearer\s+[^\s,;]+", "Bearer [REDACTED]", value)
        value = re.sub(r"wss?://[^\s]+", "[WS_URL]", value)
        return value

def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("websockets").setLevel(logging.CRITICAL)
