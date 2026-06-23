import logging
import sys
from logging.config import dictConfig

from backend.app.core.config import settings


def setup_logging() -> None:
    """
    初始化日志配置。

    当前阶段先输出到控制台。
    后续可以扩展：
    1. 输出到文件
    2. 输出到数据库
    3. 增加 trace_id / run_id
    4. 区分系统日志、Agent 日志、工具调用日志
    """

    log_level = settings.LOG_LEVEL.upper()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s | %(levelname)s | "
                        "%(name)s:%(lineno)d | %(message)s"
                    )
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "default",
                }
            },
            "root": {
                "level": log_level,
                "handlers": ["console"],
            },
            "loggers": {
                "uvicorn": {
                    "level": log_level,
                    "handlers": ["console"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": log_level,
                    "handlers": ["console"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": log_level,
                    "handlers": ["console"],
                    "propagate": False,
                },
                "open_agent_studio": {
                    "level": log_level,
                    "handlers": ["console"],
                    "propagate": False,
                },
            },
        }
    )


logger = logging.getLogger("open_agent_studio")