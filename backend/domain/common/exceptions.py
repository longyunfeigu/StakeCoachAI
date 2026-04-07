"""领域层业务异常定义，供领域与基础设施使用。

核心（core）层仅负责全局映射与异常处理，尽量避免领域层反向依赖核心层。
"""

from __future__ import annotations

from typing import Optional
from shared.codes import BusinessCode


class BusinessException(Exception):
    """业务异常基类"""

    def __init__(
        self,
        code: int,
        message: str,
        error_type: str = "BusinessError",
        details: Optional[dict] = None,
        field: Optional[str] = None,
        message_key: Optional[str] = None,
        format_params: Optional[dict] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.error_type = error_type
        self.details = details
        self.field = field
        self.message_key = message_key
        self.format_params = format_params
        super().__init__(self.message)


class UserNotFoundException(BusinessException):
    def __init__(self, user_id: Optional[str] = None):
        details = {"user_id": user_id} if user_id else None
        super().__init__(
            code=BusinessCode.USER_NOT_FOUND,
            message="User not found",
            error_type="UserNotFound",
            details=details,
            message_key="user.not_found",
        )


class UserAlreadyExistsException(BusinessException):
    def __init__(self, email: str):
        super().__init__(
            code=BusinessCode.USER_ALREADY_EXISTS,
            message=f"Email {email} already registered",
            error_type="UserAlreadyExists",
            details={"email": email},
            field="email",
            message_key="user.email.exists",
        )


class UsernameAlreadyExistsException(BusinessException):
    def __init__(self, username: str):
        super().__init__(
            code=BusinessCode.USER_ALREADY_EXISTS,
            message=f"Username {username} already exists",
            error_type="UsernameAlreadyExists",
            details={"username": username},
            field="username",
            message_key="user.username.exists",
        )


class PasswordErrorException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.PASSWORD_ERROR,
            message="Invalid username or password",
            error_type="PasswordError",
            message_key="auth.password.invalid",
        )


class UserInactiveException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.FORBIDDEN,
            message="User account is inactive",
            error_type="UserInactive",
            message_key="user.inactive",
        )


class NewPasswordSameAsOldException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.BUSINESS_ERROR,
            message="New password must differ from old password",
            error_type="NewPasswordSameAsOld",
            field="new_password",
            message_key="auth.password.same_as_old",
        )


class DomainValidationException(BusinessException):
    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: dict | None = None,
        message_key: str | None = None,
        format_params: dict | None = None,
    ):
        super().__init__(
            code=BusinessCode.PARAM_VALIDATION_ERROR,
            message=message,
            error_type="DomainValidationError",
            details=details,
            field=field,
            message_key=message_key or "validation.domain",
            format_params=format_params,
        )


class SuperuserDeactivationForbiddenException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.FORBIDDEN,
            message="Cannot deactivate a superuser",
            error_type="SuperuserDeactivationForbidden",
            message_key="user.superuser.deactivation.forbidden",
        )


class UserAlreadyActiveException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.BUSINESS_ERROR,
            message="User already active",
            error_type="UserAlreadyActive",
            message_key="user.already_active",
        )


class UserAlreadyInactiveException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.BUSINESS_ERROR,
            message="User already inactive",
            error_type="UserAlreadyInactive",
            message_key="user.already_inactive",
        )


class FileAssetNotFoundException(BusinessException):
    def __init__(self, asset_id: Optional[int] = None, *, key: Optional[str] = None):
        details = {}
        if asset_id is not None:
            details["asset_id"] = asset_id
        if key is not None:
            details["key"] = key
        super().__init__(
            code=BusinessCode.NOT_FOUND,
            message="File asset not found",
            error_type="FileAssetNotFound",
            details=details or None,
            message_key="file.not_found",
        )


class FileAssetAlreadyDeletedException(BusinessException):
    def __init__(self, asset_id: Optional[int] = None):
        details = {"asset_id": asset_id} if asset_id is not None else None
        super().__init__(
            code=BusinessCode.BUSINESS_ERROR,
            message="File already deleted",
            error_type="FileAssetAlreadyDeleted",
            details=details,
            message_key="file.already_deleted",
        )


class UnsupportedMimeTypeException(BusinessException):
    def __init__(self, mime_type: str):
        super().__init__(
            code=BusinessCode.PARAM_VALIDATION_ERROR,
            message="Unsupported MIME type",
            error_type="UnsupportedMimeType",
            details={"mime_type": mime_type},
            field="mime_type",
            message_key="storage.mime_type.unsupported",
            format_params={"mime_type": mime_type},
        )


class FileTooLargeException(BusinessException):
    def __init__(self, size: int, max_size: int):
        super().__init__(
            code=BusinessCode.PARAM_VALIDATION_ERROR,
            message="File too large",
            error_type="FileTooLarge",
            details={"size": size, "max_size": max_size},
            field="size_bytes",
            message_key="file.size.too_large",
            format_params={"size": size, "max_size": max_size},
        )


class InvalidFileNameException(BusinessException):
    def __init__(self, filename: str, *, max_len: int):
        super().__init__(
            code=BusinessCode.PARAM_VALIDATION_ERROR,
            message="Filename too long",
            error_type="InvalidFileName",
            details={"filename": filename, "max": max_len},
            field="filename",
            message_key="file.name.too_long",
            format_params={"max": max_len},
        )
