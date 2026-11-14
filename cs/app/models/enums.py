from enum import StrEnum, Enum  # 导入枚举基类：StrEnum 表示值与字符串等价（可直接序列化为 JSON 字符串），Enum 为普通枚举


class ConversationMode(StrEnum):  # 会话模式枚举，继承 StrEnum 使其成员可直接当字符串使用
    """
    会话模式
    """
    AI = "AI"   # AI客服接待：会话由 AI 自动应答，没有人工介入
    QUEUED = "QUEUED"   # 等待人工客服接入：已转人工但还没有客服领取
    HUMAN = "HUMAN" # 人工客服接待：已被人工客服接管
    CLOSED = "CLOSED"   # 会话结束：会话已关闭，不再接受新消息


class MessageRole(StrEnum):  # 消息发送方角色枚举
    """
    消息角色
    """

    USER = "USER"  # 消息由用户（客户）发出
    AI = "AI"  # 消息由 AI 客服生成
    HUMAN = "HUMAN"  # 消息由人工客服发出


class TurnStatus(StrEnum):  # 对话轮次状态枚举，用于控制一次 AI 处理流程的生命周期
    """
    轮次状态
    只存在AI对话中
    """
    COLLECTING = "COLLECTING"  # 收集中：正在等待用户把话说完（防抖/合并连发消息）
    RUNNING = "RUNNING"  # 执行中：AI 正在生成回复，该轮次已被 Worker 领取执行
    COMPLETED = "COMPLETED"  # 已完成：AI 正常产出并发送了回复
    FAILED = "FAILED"  # 已失败：执行过程中出现异常，未产出有效回复
    SUPERSEDED = "SUPERSEDED"  # 已被取代：因用户又发了新消息，该轮次作废不再执行


class HandoffStatus(StrEnum):  # 人工转接工单状态枚举
    """
    工单状态描述
    """
    WAITING = "WAITING"  # 等待中：工单已创建，尚未有人工客服接单
    ACTIVE = "ACTIVE"  # 处理中：人工客服已接单并在服务中
    RESOLVED = "RESOLVED"  # 已解决：工单处理完毕（会话可回到 AI 模式）
