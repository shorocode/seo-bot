import logging.config
import json
from pathlib import Path

def setup_logging():
    config_path = Path(__file__).parent / "logging.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    logging.config.dictConfig(config)

# فایل logging.json
"""
{
  "version": 1,
  "formatters": {
    "detailed": {
      "format": "%(asctime)s %(name)-15s %(levelname)-8s %(processName)-10s %(message)s"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "level": "INFO",
      "formatter": "detailed"
    },
    "file": {
      "class": "logging.handlers.RotatingFileHandler",
      "filename": "logs/seobot.log",
      "maxBytes": 10485760,
      "backupCount": 5,
      "formatter": "detailed"
    }
  },
  "root": {
    "level": "DEBUG",
    "handlers": ["console", "file"]
  }
}
"""
