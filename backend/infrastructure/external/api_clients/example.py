"""API 客户端重试机制示例"""

import asyncio

from .base import BaseAPIClient, APIError


class HttpBinClient(BaseAPIClient):
    """简单的 httpbin 客户端，用于演示内置重试"""

    def __init__(self):
        super().__init__(
            base_url="https://httpbin.org",
            timeout=5.0,
            max_retries=2,  # 总共尝试 3 次
            retry_delay=0.5,
            debug=True,
        )

    async def get_status(self, code: int):
        return await self.get(f"status/{code}")


async def main():
    async with HttpBinClient() as client:
        print("= 成功示例 =")
        response = await client.get_status(200)
        print(f"状态码: {response.status_code}, 耗时: {response.elapsed_ms:.2f}ms")

        print("\n= 重试示例 (请求 500) =")
        try:
            await client.get_status(500)
        except APIError as exc:
            print(f"最终捕获到 APIError: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
