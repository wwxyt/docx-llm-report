"""docx-llm-report：用大模型撰写并填充 Word 报告的最小可用框架。"""

__version__ = "0.1.0"

from .config import ReportConfig, load_config  # noqa: F401
from .pipeline import generate  # noqa: F401

__all__ = ["__version__", "ReportConfig", "load_config", "generate"]
