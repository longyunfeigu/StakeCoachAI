class MessagingError(Exception):
    pass


class SerializationError(MessagingError):
    pass


class PublishError(MessagingError):
    pass


class ConsumeError(MessagingError):
    pass


class RetryableError(MessagingError):
    pass


class NonRetryableError(MessagingError):
    pass
