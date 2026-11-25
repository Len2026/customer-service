from datetime import timedelta
from typing import Any, cast

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from cs.app.models.enums import MessageRole, ConversationMode, TurnStatus
from cs.app.models.models import Message, Conversation, ConversationTurn
from cs.app.schemas import ChatMessageRequest
from cs.app.services.admin import HandoffService
from cs.app.services.realtime import RealtimeService
from cs.common.settings import get_settings
from cs.common.utils import get_utcnow, get_uid


class ChatService:

    def __init__(self, session: AsyncSession):
        self._session = session
        self._realtime_service = RealtimeService(session)
        self._settings = get_settings()
        self._handoff_service = HandoffService(session)

    async def process_chat_message(self, payload: ChatMessageRequest, user_id: str):
        print(f"聊天message接口的业务层...session:{self._session}")

        # 0 去重消息
        stmt = select(Message).where(Message.message_id == payload.message_id)
        message = await self._session.scalar(stmt)
        if message:
            return

        # 1 处理会话信息
        conversation = await self._get_or_create_conversation(user_id)

        # 2 处理消息
        message = Message(
            message_id=payload.message_id,
            conversation_id=conversation.id,
            role=MessageRole.USER,
            message_type=payload.type,
            content=payload.content,
        )
        self._session.add(message)
        conversation.last_active_at = get_utcnow()  # 刷新会话过期时间

        # 3 处理轮次
        if conversation.mode == ConversationMode.AI:
            # a 轮次分支
            await self._get_or_create_turn(conversation)
        else:
            # b 发件箱分支
            self._realtime_service.add_event(message, conversation, notify_user=False, notify_staff=True)  # 此时还不确定

        # 4 统一提交
        await self._session.commit()
        print("chat/message...运行顺利...")
        # return {"conversation_id": "con_123", "mod": "AI"}

    # 处理会话，如果没有对应用户会话则创建，如果有用户会话则获得
    async def _get_or_create_conversation(self, user_id):
        print("_get_or_create_conversation获得/创建当前会话...")
        stmt = select(Conversation).where(Conversation.user_id == user_id, Conversation.mode != ConversationMode.CLOSED)
        conversation = await self._session.scalar(stmt)

        # 获得会话
        if conversation:
            timeout = timedelta(minutes=self._settings.conversation_idle_timeout_minutes)
            if conversation.mode == ConversationMode.AI and get_utcnow() - conversation.last_active_at > timeout:
                conversation.mode = ConversationMode.CLOSED
            else:
                return conversation

        # 创建会话
        conversation = Conversation(id=get_uid("con"), user_id=user_id, mode=ConversationMode.AI)
        self._session.add(conversation)

        return conversation

    # 处理轮次，该用户有一个collectin的轮次则该消息数据该轮次，如果没有对应轮次则创建轮次
    async def _get_or_create_turn(self, conversation):
        print("_get_or_create_turn获得/创建当前轮次...")
        # 获得轮次
        stmt = select(ConversationTurn).where(ConversationTurn.conversation_id == conversation.id,
                                              ConversationTurn.status == TurnStatus.COLLECTING)
        conversation_turn = await self._session.scalar(stmt)

        # 创建轮次
        if conversation_turn is None:
            conversation_turn = ConversationTurn(
                conversation_id=conversation.id,
                status=TurnStatus.COLLECTING,
                collect_until=get_utcnow() + timedelta(milliseconds=self._settings.message_merge_delay_ms),
            )
            self._session.add(conversation_turn)

        return conversation_turn

    # 获得聊天的历史消息
    async def get_chat_history(self, user_id):
        # 当前会话
        current_conversation = await self._get_or_create_conversation(user_id)

        # 当前用户的所有会话消息
        stmt = (select(Message).join(Conversation, Conversation.id == Message.conversation_id)
                .where(Conversation.user_id == user_id).order_by(Message.id))
        records = (await self._session.scalars(stmt)).all()  # 所有当前用户会话的所有message内容

        # 封装前端json
        messages = [
            {
                "conversation_id": record.conversation_id,
                "role": record.role,
                "content": record.content,
            }
            for record in records
        ]
        await self._session.commit()  # 归还会话

        # 响应结果
        return {
            "conversation_id": current_conversation.id,
            "conversation_mode": current_conversation.mode,
            "messages": messages
        }

    # 领取轮次
    async def claim_turn(self) -> tuple[ConversationTurn, dict[str, Any], str]:
        # print("claim_turn，worker从系统领取轮次...")

        # 查询collecting状态轮次
        stmt = select(ConversationTurn).where(ConversationTurn.status == TurnStatus.COLLECTING,
                                              ConversationTurn.collect_until <= get_utcnow())
        claimed_turn = await self._session.scalar(stmt)  # 一个一个领轮次
        if claimed_turn is None:
            return None

        # 查询当前轮次对应的当前会话
        conversation = await self._session.scalar(
            select(Conversation).where(Conversation.id == claimed_turn.conversation_id).with_for_update())

        # 根据conversation_id查询最新的message
        latest_user_message_id = await self._get_latest_user_message_id(str(conversation.id))  # 此刻当前会话最新的消息id

        # 修改状态
        claimed_turn.status = TurnStatus.RUNNING
        claimed_turn.snapshot_message_id = latest_user_message_id  # 此刻当前会话最新的消息id
        claimed_turn.attempts += 1  # 每执行一次轮次，次数+1，限制重试次数

        # 组装模型参数payload(载荷)
        payload: dict[str, Any] = await self._build_request_payload(claimed_turn, conversation)  # 组装参数

        # 提交所有修改
        await self._session.commit()
        return claimed_turn, payload, cast(str, conversation.user_id)

    # 此刻当前会话最新的消息id
    async def _get_latest_user_message_id(self, conversation_id):
        # print("_get_latest_user_message_id，此刻当前会话最新的消息id...")
        stmt = select(func.max(Message.id)).where(Message.conversation_id == conversation_id,
                                                  Message.role == MessageRole.USER)
        return await self._session.scalar(stmt)

    # 组装模型参数
    async def _build_request_payload(self, claimed_turn, conversation):
        # print("_build_request_payload，组装模型参数...")

        # 从上一条不是用户的消息开始到当前的snapshot_message_id，是当前轮次的消息
        current_stmt = select(func.max(Message.id)).where(Message.conversation_id == conversation.id,
                                                          Message.role != MessageRole.USER
                                                          )
        latest_reply_id = await self._session.scalar(current_stmt) or 0  # 上一条不是用户的消息id，如果是用户的第一个会话的第一个轮次的话默认从0开始

        messages_stmt = select(Message).where(Message.conversation_id == conversation.id,
                                              Message.id > latest_reply_id,
                                              Message.id <= claimed_turn.snapshot_message_id
                                              ).order_by(Message.id)  # 默认升序排列
        current_messages = (await self._session.scalars(messages_stmt)).all()  # 当前会话当前轮次的所有消息

        # 查询历史的最近的30条对话记录
        history_stmt = select(Message).where(
            Message.conversation_id == conversation.id,
            Message.id < current_messages[0].id
        ).order_by(Message.id.desc()).limit(30)

        history_messages = reversed((await self._session.scalars(history_stmt)).all())  # 当前会话历史轮次的消息

        # 传递给ai的载荷数据结构
        return {
            "conversation_id": conversation.id,
            "messages": [
                {"role": message.role, "type": message.message_type, "content": message.content}
                for message in current_messages
            ],
            "history": [
                {"role": history.role, "type": history.message_type, "content": history.content}
                for history in history_messages
            ]
        }

    # 结算轮次(发件箱)
    async def finish_turn(self, claimed_turn, run_result, error):
        print("finish_turn，轮次结算，处理发件箱....")
        # 1 判断是否作废
        conversation = await self._session.scalar(select(Conversation).where(
            Conversation.id == claimed_turn.conversation_id
        ).with_for_update())
        latest_user_message_id = await self._get_latest_user_message_id(conversation.id)  # 当前会话的最新的一条信息的id
        if claimed_turn.snapshot_message_id != latest_user_message_id:
            claimed_turn.status = TurnStatus.SUPERSEDED
            await self._session.commit()  # 释放锁
            return

        # 2 判断是否异常
        if error is not None:
            if claimed_turn.attempts < self._settings.ai_worker_max_attempts:
                claimed_turn.status = TurnStatus.COLLECTING
                claimed_turn.collect_until = get_utcnow() + timedelta(
                    seconds=self._settings.ai_worker_retry_delay_seconds)  # 异常状态延长轮次窗口期
            else:
                claimed_turn.status = TurnStatus.FAILED
                await self._save_ai_reply(conversation, {"kind": "error", "text": "AI 客服不可用，请稍后再试"})
            await self._session.commit()  # 释放锁
            return

        # 3 正常回复
        # print("正常回复，保存message和发件箱...")
        claimed_turn.status = TurnStatus.COMPLETED

        # 4 判断是否转人工
        # print("判断是否转人工服务处理，保存工单和发件箱...")
        if run_result["reply_type"] == "REQUEST_HANDOFF":
            handoff_summary = run_result["handoff_summary"]
            self._handoff_service.create_handoff(conversation, handoff_summary)  # 插入一个工单
            conversation.mode = ConversationMode.QUEUED  # 会话模式=QUEUED

        # 正常+工单，保存message和发件箱
        await self._save_ai_reply(conversation, run_result)

        await self._session.commit()  # 释放锁

    #  保存ai回复信息
    async def _save_ai_reply(self, conversation, run_result):
        print("_save_ai_reply，保存ai回复信息...")
        # 保存message
        message = Message(
            message_id=get_uid("msg"),
            conversation_id=conversation.id,
            role=MessageRole.AI,
            message_type="text",  # 也可能是object,
            content=run_result
        )
        # 每每有一个新消息入库，会话的过期时间要更新
        conversation.last_active_at = get_utcnow()
        self._session.add(message)

        # 保存发件箱
        self._realtime_service.add_event(
            message, conversation, notify_user = True,
            notify_staff = conversation.mode == ConversationMode.QUEUED
        )
