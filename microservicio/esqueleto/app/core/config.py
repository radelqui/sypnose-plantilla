import os

SERVICE_NAME = os.getenv("SERVICE_NAME", "{{SERVICE_NAME}}")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "{{SERVICE_PORT}}"))
USE_FAKE_ENGINE = os.getenv("USE_FAKE_ENGINE", "0") == "1"
