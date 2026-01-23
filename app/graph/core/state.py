from typing import TypedDict, Annotated
import datetime
from app.graph.core.model import LlmCallItem

class State(TypedDict):
    """对话状态"""
    SessionId: str
    SessionMessgeId: str
    UserQuery: str
    LlmModelName: str
    LlmTemperature: float
    Messages: list  # 直接使用 list，让 LangGraph 默认处理（替换而不是累加）
    CurrentDatetime: datetime.datetime
    LlmCalls: list[LlmCallItem]
    ForceEnd: bool
    IsBlocked: bool
    BlockReason: str
    # Understand 节点相关字段
    RephraseResult: str
    UnderstandResult: dict[str, str]
    # DataQuery 节点相关字段
    DataQueryTask: str
    DataQueryTable: str
    SqlGenResult: dict
    DataQueryResult: dict
    # PostProcess 节点相关字段
    PostProcessTask: str
    PostProcessDatasetId: str
    PostProcessResult: dict
    # Summarize 节点相关字段
    SummarizeDatasetId: str
    SummarizeResult: str
    # 数据集管理
    Datasets: dict[str, dict]  # dataset_id -> dataset_data
    # DataQuery 重新思考次数
    DataQueryRethinkTimes: int
    # PostProcess 重新思考次数
    PostprocessRethinkTimes: int