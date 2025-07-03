from __future__ import annotations

from aiwolf_nlp_common.protocol import Packet
from aiwolf_nlp_common.protocol.list import TalkInfo, TalkList, WhisperList


class talkHistoryConverter:
    @classmethod
    def get_talk_history_list(cls, protocol: Packet) -> list:
        if protocol.talk_history is None or protocol.talk_history.is_empty():
            return None

        return cls.get_communication_history(
            communication_history=protocol.talk_history
        )

    @classmethod
    def get_communication_history(
        cls, communication_history: TalkList | WhisperList
    ) -> list:
        result: list = list()

        talk_list_element: TalkInfo
        for talk_list_element in communication_history:
            current_talk_dict: dict = dict()
            current_talk_dict["agent"] = talk_list_element.agent
            current_talk_dict["day"] = talk_list_element.day
            current_talk_dict["idx"] = talk_list_element.idx
            current_talk_dict["text"] = talk_list_element.text
            current_talk_dict["turn"] = talk_list_element.turn

            result.append(current_talk_dict)

        return result
