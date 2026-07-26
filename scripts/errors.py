"""项目统一异常层级（rules.md §3.1）。

所有管线异常继承 BasketballPipelineError，携带 run_id 便于跨日志回溯；
子类按失败域划分，供各脚本 main() 统一捕获后转为非零退出码。
"""


class BasketballPipelineError(Exception):
    """所有管线异常的基类，携带 run_id 便于回溯。"""

    def __init__(self, message: str, *, run_id: str = "") -> None:
        super().__init__(message)
        self.run_id = run_id


class SchemaError(BasketballPipelineError):
    """goals.json / roster.json / candidates.json 结构损坏（字段缺失/类型错误）。"""


class UnsupportedMediaError(BasketballPipelineError):
    """ffprobe 返回非预期编码或参数（如非 HEVC 原片）。"""


class DanglingReferenceError(BasketballPipelineError):
    """JSON 主键指向的文件已不存在，但仍被有效记录引用。"""


class MediaTimeoutError(BasketballPipelineError):
    """ffprobe / ffmpeg 子进程超时且重试耗尽。"""
