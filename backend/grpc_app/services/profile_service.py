from __future__ import annotations

import grpc
from core.logging_config import get_logger
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from grpc_app.generated.forge.v1 import profile_pb2, profile_pb2_grpc, common_pb2


logger = get_logger(__name__)


class ProfileService(profile_pb2_grpc.ProfileServiceServicer):
    def __init__(self) -> None:
        pass

    async def ListProfiles(
        self,
        request: profile_pb2.ListProfilesRequest,
        context: grpc.aio.ServicerContext,
    ) -> profile_pb2.ListProfilesReply:
        # 从应用层获取用户列表，并映射为 Profile 列表
        page = int(request.page.page or 1)
        size = int(request.page.page_size or 20)

        # Placeholder list logic
        total = 0
        items = []

        pages = (total + size - 1) // size if size > 0 else 0
        meta = common_pb2.PageMeta(total=int(total), page=page, page_size=size, pages=int(pages))
        return profile_pb2.ListProfilesReply(items=items, meta=meta)

    async def GetProfile(
        self,
        request: common_pb2.IdRequest,
        context: grpc.aio.ServicerContext,
    ) -> profile_pb2.Profile:
        # Placeholder: return dummy profile as user service is removed
        return profile_pb2.Profile(
            id=int(request.id), full_name=f"User {request.id}", bio="Demo bio"
        )
