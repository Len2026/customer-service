from fastapi import APIRouter

from cs.app.dependencies import StaffDep, HandoffServiceDep, AdminDep
from cs.app.schemas import ReplyRequest

router = APIRouter(prefix="/api/v1", tags=["后台人工客服管理系统"])


# 工单列表
@router.get("/handoffs")
async def handoffs_endpoint(
        service: HandoffServiceDep,
        _: StaffDep  # 鉴权
):
    return await service.get_open_handoff()


# 工单详情
@router.get("/handoffs/{handoff_id}/messages")
async def get_handoffs_messages_endpoint(
        handoff_id: str,
        service: HandoffServiceDep,
        _: StaffDep  # 鉴权
):
    return await service.get_handoff_messages(handoff_id)


# 接单
@router.post("/handoffs/{handoff_id}/accept")
async def accept_handoffs_endpoint(
        handoff_id: str,
        service: HandoffServiceDep,
        staff: StaffDep  # 鉴权
):
    await service.accept_handoff(handoff_id, staff.user_id)


# 客服回复
@router.post("/handoffs/{handoff_id}/messages")
async def reply_handoff_endpoint(
        handoff_id: str,
        service: HandoffServiceDep,
        _: StaffDep,  # 鉴权
        payload: ReplyRequest
):
    await service.reply_handoff_endpoint(handoff_id, payload)

# 结单
@router.post("/handoffs/{handoff_id}/resolve")
async def resolve_handoff_endpoint(
        handoff_id: str,
        service: HandoffServiceDep,
        _: StaffDep  # 鉴权
):
    await service.resolve_handoff(handoff_id)

# 监控(统计)
@router.get("/admin/metrics")
async def get_admin_metrics_endpoint(
        service: HandoffServiceDep,
        _: AdminDep
):
    return await service.get_admin_metrics()
