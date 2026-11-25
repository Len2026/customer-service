from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from cs.app.models.enums import HandoffStatus, ConversationMode, MessageRole
from cs.app.models.models import Handoff, Message, Conversation
from cs.app.services.realtime import RealtimeService
from cs.common.utils import get_uid, get_utcnow


class HandoffService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._realtime_service = RealtimeService(session)

    # 创建工单
    def create_handoff(self, conversation, handoff_summary):
        # 保存工单信息
        handoff = Handoff(conversation_id=conversation.id, user_id=conversation.user_id,
                          summary=handoff_summary, status=HandoffStatus.WAITING)
        self._session.add(handoff)

    # 查询工单列表
    async def get_open_handoff(self):
        stmt = select(Handoff).where(Handoff.status.in_([HandoffStatus.WAITING, HandoffStatus.ACTIVE])).order_by(
            Handoff.created_at)
        return list((await self._session.scalars(stmt)).all())

    # 查询工单对应的messages
    async def get_handoff_messages(self, handoff_id):
        # 查工单，message
        stmt = select(Message).join(Handoff, Handoff.conversation_id == Message.conversation_id).where(
            Handoff.id == handoff_id
        ).order_by(Message.id)
        return {"messages": (await self._session.scalars(stmt)).all()}

    # 接单
    async def accept_handoff(self, handoff_id, staff_id):
        # 1 查询当前会话和工单
        handoff, conversation = await self._get_handoff_and_conversation(handoff_id)

        # 2 修改工单状态
        if handoff.status == HandoffStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="Handoff already active")
        handoff.status = HandoffStatus.ACTIVE
        handoff.staff_id = staff_id

        # 3 修改会话状态
        conversation.mode = ConversationMode.HUMAN

        # 4 发件箱(staff->user)
        self._save_human_reply(conversation, f"客服{staff_id}已经接入：请问有什么可以帮助您？")  # todo

        # 5 统一提交
        await self._session.commit()

    # 查询工单和对应的会话
    async def _get_handoff_and_conversation(self, handoff_id):
        # 查询工单
        handoff_stmt = select(Handoff).where(Handoff.id == handoff_id).with_for_update()  # 防止抢单
        handoff = await self._session.scalar(handoff_stmt)

        # 查询会话
        conversation_stmt = select(Conversation).where(
            handoff.conversation_id == Conversation.id).with_for_update()  # 防止抢单
        conversation = await self._session.scalar(conversation_stmt)

        return handoff, conversation

    # 保存客服回复
    def _save_human_reply(self, conversation, text: str):
        print("_save_human_reply，保存客服回复信息...")
        # 保存message
        message = Message(
            message_id=get_uid("msg"),
            conversation_id=conversation.id,
            role=MessageRole.HUMAN,
            message_type="text",  # 也可能是object,
            content={"text": text}
        )
        conversation.last_active_at = get_utcnow()
        self._session.add(message)

        # 保存发件箱
        self._realtime_service.add_event(
            message, conversation, notify_user=True,
            notify_staff=False
        )

    # 客服回复
    async def reply_handoff_endpoint(self, handoff_id, payload):
        # 获得conversation
        _, conversation = await self._get_handoff_and_conversation(handoff_id)
        self._save_human_reply(conversation, payload.text)
        await self._session.commit()

    # 结单
    async def resolve_handoff(self, handoff_id):
        handoff, conversation = await self._get_handoff_and_conversation(handoff_id)

        # 工单：RESOLVED
        handoff.status = HandoffStatus.RESOLVED

        # 会话：AI
        conversation.mode = ConversationMode.AI

        # 发件箱：人工结束，转为ai服务
        self._save_human_reply(conversation, f"人工客服服务结束，转为AI智能客服为您服务。")

        # 统一提交
        await self._session.commit()

    # 统计监控
    async def get_admin_metrics(self):
        return {
            "conversations": await self._get_count(Conversation.id),  # 所有会话数量
            "handoffs": await self._get_count(Handoff.id),  # 所有会话数量
            "queued": await self._get_count(Conversation.id, Conversation.mode == ConversationMode.QUEUED),
            # 所有排队人工客服的会话数量
            "human": await self._get_count(Conversation.id, Conversation.mode == ConversationMode.HUMAN),
        }

    # 统计工具方法
    async def _get_count(self, col, *condition_expr):
        stmt = select(func.count(col)).where(*condition_expr)
        return await self._session.scalar(stmt)
