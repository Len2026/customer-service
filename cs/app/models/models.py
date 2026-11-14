from datetime import datetime  # 导入 datetime 类型，用于定义时间字段的类型注解
from typing import Any  # 导入 Any，用于表示 JSON 内容里任意类型的值

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text, Text  # 导入列类型、外键、索引、原生 SQL 片段等 SQLAlchemy 组件
from sqlalchemy.dialects.postgresql import JSONB  # 导入 PostgreSQL 专有的 JSONB 类型，用于存结构化 JSON 数据
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column  # 导入声明式基类与 2.0 风格的 ORM 列声明工具

from cs.common.utils import get_uid, get_utcnow  # 导入工具函数：生成带前缀的唯一 ID、获取 UTC 当前时间
from cs.app.models.enums import ConversationMode, TurnStatus, HandoffStatus  # 导入各表字段使用的枚举默认值


class Base(DeclarativeBase):  # 所有 ORM 模型的声明式基类，SQLAlchemy 通过它收集元数据
    pass  # 无额外逻辑，仅作为基类占位


class Conversation(Base):  # 会话表模型：一条记录代表一个用户与客服（AI/人工）的一次会话
    __tablename__ = "conversations"  # 指定数据库表名为 conversations
    __table_args__ = (  # 定义表级约束/索引
        Index(  # 创建唯一索引，保证同一用户同一时刻只有一个"未关闭"的会话
            "uq_open_conversation_per_user",  # 索引名称
            "user_id",  # 作用于 user_id 列
            unique=True,  # 唯一约束
            postgresql_where=text("mode IN ('AI', 'QUEUED', 'HUMAN')"),  # 同一个用户会话模式是有效的只能有一个 但是有效的某一个可以和关闭的会话模式共存
        ),  # 部分索引定义结束
    )  # 表参数定义结束

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: get_uid("conv"))  # 主键，形如 conv_xxx 的字符串，默认自动生成
    user_id: Mapped[str] = mapped_column(String(40), index=True)  # 会话所属用户的 ID，建普通索引便于按用户查询
    mode: Mapped[str] = mapped_column(String(20), default=ConversationMode.AI, index=True)  # 会话当前模式，默认 AI 接待，建索引便于筛状态
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utcnow)  # 会话创建时间（带时区），默认当前 UTC 时间
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utcnow, onupdate=get_utcnow)  # 最后活跃时间，创建时写入、每次更新记录时自动刷新


class Message(Base):  # 消息表模型：存储会话中的每一条用户/AI/人工消息
    __tablename__ = "messages"  # 指定数据库表名为 messages

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)  # 自增主键，作为内部存储用的行号（可保证全局顺序）
    message_id: Mapped[str] = mapped_column(String(80), unique=True)  # 业务对外使用的消息 ID，全局唯一
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)  # 所属会话 ID，外键关联 conversations.id
    role: Mapped[str] = mapped_column(String(20))  # 消息发送方角色（USER / AI / HUMAN），对应 MessageRole
    message_type: Mapped[str] = mapped_column(String(20), default="text")  # 消息类型，默认纯文本 text（可扩展 image 等）
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)  # 消息正文，用 JSONB 存放以保证结构化与可查询
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utcnow)  # 消息创建时间（带时区）


class ConversationTurn(Base):  # 对话轮次表模型：一次用户发问 -> AI 处理的完整流程记录
    __tablename__ = "conversation_turns"  # 指定数据库表名为 conversation_turns
    __table_args__ = (  # 定义表级约束/索引
        Index("uq_collecting_turn_per_conversation", "conversation_id", unique=True,  # 同一会话最多只有一个"收集中"的轮次，避免并发重复
              postgresql_where=text("status = 'COLLECTING'")),  # 部分索引条件：仅约束 COLLECTING 状态的行

        Index("uq_executing_turn_per_conversation", "conversation_id", unique=True,  # 同一会话最多只有一个"执行中"的轮次，保证串行执行
              postgresql_where=text("status = 'RUNNING'"))  # 部分索引条件：仅约束 RUNNING 状态的行
    )  # 表参数定义结束
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: get_uid("turn"))  # 主键，形如 turn_xxx 的字符串，默认自动生成
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)  # 所属会话 ID，外键关联 conversations.id
    status: Mapped[str] = mapped_column(String(30), default=TurnStatus.COLLECTING, index=True)  # 轮次状态，默认"收集中"，建索引便于 Worker 扫描
    snapshot_message_id: Mapped[int | None] = mapped_column(Integer)  # 收集中所覆盖消息的截止行号（快照），用于确定本轮处理的消息范围，可为空
    collect_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)  # 收集截止时间，到点后由 Worker 触发执行，建索引便于定时扫描
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # 已重试次数，用于失败重试与死信判定，默认 0
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utcnow)  # 轮次创建时间（带时区）


class RealtimeEvent(Base):  # 实时事件表模型：落库待推送的实时消息事件，保证推送可靠不丢
    """等待实时推送 Worker 发布的实时消息事件。为了持久化"""

    __tablename__ = "realtime_events"  # 指定数据库表名为 realtime_events

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)  # 自增主键，同时也是事件的自然顺序
    target: Mapped[str] = mapped_column(String(80), index=True)  # 推送目标标识（如用户/会话频道），建索引便于按目标拉取
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)  # 待推送的事件负载，用 JSONB 存储结构化内容
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utcnow)  # 事件产生时间（带时区）
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)  # 实际推送成功时间，为 NULL 表示尚未发送，建索引便于扫描待推送事件


class Handoff(Base):  # 人工转接工单表模型：记录一次从 AI 转人工的服务请求
    """记录一次人工客服工单及其处理状态。"""

    __tablename__ = "handoffs"  # 指定数据库表名为 handoffs
    __table_args__ = (  # 定义表级约束/索引
        Index("uq_open_handoff_per_conversation", "conversation_id", unique=True,  # 同一会话最多只有一个"未结束"的工单，防止重复转人工
              postgresql_where=text("status IN ('WAITING', 'ACTIVE')")),  # 部分索引条件：仅约束等待中与处理中的行
    )  # 表参数定义结束

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: get_uid("handoff"))  # 主键，形如 handoff_xxx 的字符串，默认自动生成
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)  # 关联的会话 ID，外键指向 conversations.id
    user_id: Mapped[str] = mapped_column(String(40), index=True)  # 发起转人工的用户 ID，建索引便于按用户查询工单
    summary: Mapped[str] = mapped_column(Text)  # 转人工摘要（如 AI 归纳的问题描述），使用不定长文本类型
    status: Mapped[str] = mapped_column(String(20), default=HandoffStatus.WAITING, index=True)  # 工单状态，默认"等待中"，建索引便于筛排队工单
    staff_id: Mapped[str | None] = mapped_column(String(40), index=True)  # 处理该工单的人工客服 ID，未接单时为空，建索引便于按客服查询
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utcnow)  # 工单创建时间（带时区）
