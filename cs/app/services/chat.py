from cs.app.schemas import ChatMessageRequest

class ChatService:
    async def process_chat_message(self, payload: ChatMessageRequest, user_id: str):
        print("聊天message接口的业务层...")
        return {"conversation_id": "con_123", "mod": "AI"}