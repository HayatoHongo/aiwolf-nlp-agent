from __future__ import annotations

from aiwolf_nlp_common.protocol import Packet
from .talkHistory import talkHistoryConverter


class whisperHistoryConverter(talkHistoryConverter):
    @classmethod
    def get_whisper_history_list(cls, protocol: Packet) -> list:
        if protocol.whisper_history is None or protocol.whisper_history.is_empty():
            return None

        return cls.get_communication_history(
            communication_history=protocol.talk_history
        )
