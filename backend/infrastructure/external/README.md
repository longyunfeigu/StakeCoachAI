# Infrastructure/External 外部系统集成层

## 目录说明

这个目录用于存放所有与外部系统、第三方服务集成的实现代码。在DDD架构中，这是基础设施层的一部分，负责处理与外部世界的所有交互。

## 典型内容

### 1. 第三方API客户端 (`api_clients/`)
- REST API客户端
- GraphQL客户端
- SOAP服务客户端
- SDK封装

```python
# 示例：第三方API客户端
infrastructure/external/
├── api_clients/
│   ├── __init__.py
│   ├── weather_client.py     # 天气API客户端
│   └── notification_client.py # 通知服务客户端
```

### 2. 消息队列集成 (`messaging/`)
- RabbitMQ生产者/消费者
- Kafka客户端
- Redis Pub/Sub
- AWS SQS/SNS

```python
# 示例：消息队列集成
infrastructure/external/
├── messaging/
│   ├── __init__.py
│   ├── rabbitmq/
│   │   ├── publisher.py
│   │   └── consumer.py
│   ├── kafka/
│   │   ├── producer.py
│   │   └── consumer.py
│   └── redis_pubsub.py
```

### 3. 云服务集成 (`cloud_services/`)
- AWS服务（S3, Lambda, DynamoDB等）
- 阿里云服务（OSS, 函数计算等）
- Azure服务
- Google Cloud服务

```python
# 示例：云存储服务
infrastructure/external/
├── storage/
│   ├── __init__.py
│   ├── aws_s3.py         # AWS S3存储
│   ├── aliyun_oss.py     # 阿里云OSS
│   └── local_storage.py  # 本地存储（开发环境）
```

### 4. 邮件服务 (`email/`)
- SMTP客户端
- SendGrid集成
- AWS SES
- 邮件模板引擎

```python
# 示例：邮件服务
infrastructure/external/
├── email/
│   ├── __init__.py
│   ├── smtp_client.py
│   ├── sendgrid_client.py
│   └── templates/
│       ├── welcome.html
│       └── reset_password.html
```

### 5. 短信服务 (`sms/`)
- 阿里云短信
- 腾讯云短信
- Twilio

```python
# 示例：短信服务
infrastructure/external/
├── sms/
│   ├── __init__.py
│   ├── aliyun_sms.py
│   └── twilio_sms.py
```

### 6. 搜索引擎 (`search/`)
- Elasticsearch客户端
- Algolia集成
- MeiliSearch客户端

```python
# 示例：搜索服务
infrastructure/external/
├── search/
│   ├── __init__.py
│   ├── elasticsearch_client.py
│   └── algolia_client.py
```

### 7. 缓存服务 (`cache/`)
- Redis客户端
- Memcached客户端
- 分布式缓存

```python
# 示例：缓存服务
infrastructure/external/
├── cache/
│   ├── __init__.py
│   ├── redis_cache.py
│   └── memcached_cache.py
```

### 8. 监控和日志 (`monitoring/`)
- APM集成（New Relic, DataDog）
- 日志服务（ELK Stack, CloudWatch）
- 指标收集（Prometheus）

```python
# 示例：监控服务
infrastructure/external/
├── monitoring/
│   ├── __init__.py
│   ├── prometheus_metrics.py
│   └── sentry_client.py
```

### 9. 认证服务 (`auth/`)
- OAuth2提供商（Google, GitHub, Facebook）
- SAML集成
- LDAP/AD集成

```python
# 示例：第三方认证
infrastructure/external/
├── auth/
│   ├── __init__.py
│   ├── oauth/
│   │   ├── google_oauth.py
│   │   └── github_oauth.py
│   └── ldap_client.py
```

### 10. AI/ML服务 (`ai/`)
- OpenAI API
- 百度AI
- 阿里云AI
- 自定义模型服务

```python
# 示例：AI服务集成
infrastructure/external/
├── ai/
│   ├── __init__.py
│   ├── openai_client.py
│   └── image_recognition.py
```

## 实际示例实现

### 示例1：邮件服务客户端

```python
# infrastructure/external/email/email_service.py
from abc import ABC, abstractmethod
from typing import List, Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailService(ABC):
    """邮件服务抽象接口"""
    
    @abstractmethod
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        html: bool = False
    ) -> bool:
        """发送邮件"""
        pass


class SMTPEmailService(EmailService):
    """SMTP邮件服务实现"""
    
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
    
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        html: bool = False
    ) -> bool:
        message = MIMEMultipart()
        message["From"] = self.username
        message["To"] = ", ".join(to)
        message["Subject"] = subject
        
        mime_type = "html" if html else "plain"
        message.attach(MIMEText(body, mime_type))
        
        try:
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=self.use_tls
            )
            return True
        except Exception as e:
            # 记录日志
            print(f"邮件发送失败: {e}")
            return False
```

### 示例2：对象存储服务

```python
# infrastructure/external/storage/storage_service.py
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
import boto3
from botocore.exceptions import ClientError

class StorageService(ABC):
    """存储服务抽象接口"""
    
    @abstractmethod
    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: Optional[str] = None
    ) -> str:
        """上传文件"""
        pass
    
    @abstractmethod
    async def download(self, key: str) -> bytes:
        """下载文件"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除文件"""
        pass
    
    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """获取预签名URL"""
        pass


class S3StorageService(StorageService):
    """AWS S3存储服务实现"""
    
    def __init__(self, bucket: str, region: str):
        self.bucket = bucket
        self.client = boto3.client('s3', region_name=region)
    
    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: Optional[str] = None
    ) -> str:
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.client.upload_fileobj(
                file,
                self.bucket,
                key,
                ExtraArgs=extra_args
            )
            return f"s3://{self.bucket}/{key}"
        except ClientError as e:
            raise Exception(f"上传失败: {e}")
    
    async def download(self, key: str) -> bytes:
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=key
            )
            return response['Body'].read()
        except ClientError as e:
            raise Exception(f"下载失败: {e}")
    
    async def delete(self, key: str) -> bool:
        try:
            self.client.delete_object(
                Bucket=self.bucket,
                Key=key
            )
            return True
        except ClientError:
            return False
    
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        return self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': key},
            ExpiresIn=expires_in
        )
```

### 示例3：缓存服务

```python
# infrastructure/external/cache/cache_service.py
from abc import ABC, abstractmethod
from typing import Any, Optional
import redis.asyncio as redis
import json

class CacheService(ABC):
    """缓存服务抽象接口"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        pass
    
    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """设置缓存"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        pass


class RedisCache(CacheService):
    """Redis缓存服务实现"""
    
    def __init__(self, url: str):
        self.redis = redis.from_url(url)
    
    async def get(self, key: str) -> Optional[Any]:
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        serialized = json.dumps(value)
        return await self.redis.set(
            key,
            serialized,
            ex=expire
        )
    
    async def delete(self, key: str) -> bool:
        return await self.redis.delete(key) > 0
    
    async def exists(self, key: str) -> bool:
        return await self.redis.exists(key) > 0
```

## 最佳实践

1. **使用抽象接口**：定义抽象基类，便于切换不同的实现
2. **配置驱动**：通过配置文件控制使用哪个具体实现
3. **错误处理**：妥善处理外部服务可能出现的各种异常
4. **重试机制**：实现自动重试和熔断机制
5. **异步支持**：尽可能使用异步客户端提高性能
6. **日志记录**：记录所有外部调用的日志便于调试
7. **监控指标**：收集调用延迟、成功率等指标
8. **本地模拟**：提供本地开发环境的模拟实现

## 依赖注入示例

```python
# application/services.py
from dependency_injector import containers, providers
from infrastructure.external.email import SMTPEmailService
from infrastructure.external.storage import S3StorageService
from infrastructure.external.cache import RedisCache

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    
    # 邮件服务
    email_service = providers.Singleton(
        SMTPEmailService,
        host=config.smtp.host,
        port=config.smtp.port,
        username=config.smtp.username,
        password=config.smtp.password
    )
    
    # 存储服务
    storage_service = providers.Singleton(
        S3StorageService,
        bucket=config.s3.bucket,
        region=config.s3.region
    )
    
    # 缓存服务
    cache_service = providers.Singleton(
        RedisCache,
        url=config.redis.url
    )
```

这样的设计让外部服务集成更加清晰、可维护，并且便于测试和替换。