import sys
import os
from datetime import datetime

class DualLogger:
    def __init__(self, log_path="scraper_debug.log"):
        self.terminal = sys.stdout
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True) if os.path.dirname(log_path) else None
        self.log = open(log_path, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# Replace sys.stdout only if DEBUG mode is active
def enable_serialized_logging(DEBUG: bool = False, log_filename: str = None):
    if DEBUG:
        log_filename = log_filename or f"logs/scraper_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        sys.stdout = DualLogger(log_filename)