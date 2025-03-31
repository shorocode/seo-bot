import logging.config
import json
from pathlib import Path
from typing import Dict, Any
import os

DEFAULT_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "simple": {
            "format": "[%(levelname)s] %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "verbose",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/seobot.log",
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose"
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/errors.log",
            "level": "ERROR",
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 3,
            "encoding": "utf-8",
            "formatter": "verbose"
        }
    },
    "loggers": {
        "telegram": {
            "level": "WARNING",
            "propagate": True
        },
        "apscheduler": {
            "level": "WARNING",
            "propagate": True
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console", "file", "error_file"]
    }
}

def setup_logging(
    config_path: Path = None,
    default_level: int = logging.INFO,
    env_key: str = "LOG_CFG"
) -> None:
    """Setup logging configuration
    
    Args:
        config_path: Path to logging config file
        default_level: Default logging level
        env_key: Environment variable name for config path
    """
    # Create logs directory if not exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True, parents=True)
    
    config = DEFAULT_CONFIG
    
    # Try to load config from file if provided
    if config_path is None:
        config_path = Path(__file__).parent / "logging.json"
    
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
            config.update(file_config)
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Failed to load logging config: {e}. Using defaults")
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Capture warnings from warnings module
    logging.captureWarnings(True)
    
    # Set specific loggers levels from environment if available
    if "LOG_LEVEL" in os.environ:
        log_level = os.environ["LOG_LEVEL"].upper()
        logging.getLogger().setLevel(log_level)
