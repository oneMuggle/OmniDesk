from abc import ABC, abstractmethod
from typing import Any

from .types import NotifyResult


class NotifyChannel(ABC):
    name = ""

    @abstractmethod
    def send(
        self,
        *,
        user: Any,
        type: str,
        title: str,
        content: str,
        link: str = "",
        dedupe_key: str = "",
    ) -> NotifyResult:
        raise NotImplementedError
