import logging
import re
import sys
from typing import Any

# Regex patterns for sensitive PII
AADHAAR_REGEX = re.compile(r'\b(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})\b')
PAN_REGEX = re.compile(r'\b([A-Z]{5})(\d{4})([A-Z])\b')
PASSPORT_REGEX = re.compile(r'\b([A-Z])(\d{7})\b')
AUTH_HEADER_REGEX = re.compile(r'(?i)(bearer\s+[A-Za-z0-9\-_=.]+)|(x-officer-key[:=]\s*[A-Za-z0-9\-_=.]+)')

class PIIRedactingFilter(logging.Filter):
    """
    Log filter that masks sensitive identity and credential data from all log streams.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redact(str(arg)) for arg in record.args)
        return True

    @staticmethod
    def redact(text: str) -> str:
        # Mask Aadhaar numbers: XXXX-XXXX-1234
        text = AADHAAR_REGEX.sub(r'XXXX-XXXX-\3', text)
        # Mask PAN numbers: ABCDE****F
        text = PAN_REGEX.sub(r'\1****\3', text)
        # Mask Passport numbers: P******8
        text = PASSPORT_REGEX.sub(r'\1******', text)
        # Mask authorization credentials
        text = AUTH_HEADER_REGEX.sub('[REDACTED_CREDENTIAL]', text)
        return text

def setup_logger(name: str = "docshield", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        handler.addFilter(PIIRedactingFilter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger

logger = setup_logger("docshield")
