from dataclasses import dataclass
from typing import Literal


@dataclass
class ProtocolMean:
    not_flag: bool
    action: Literal["SUSPECT", "VOTE", "DIVINATION", "AGREE",
                    "ESTIMATE", "CO", "DIVINED"]
    talk_subject: str | None
    talk_object: str | None
    role: Literal["WEREWOLF", "SEER", "VILLAGER", "POSSESSED", "ANY"] | None = None
    team: Literal["BLACK", "WHITE", "ANY"] | None = None
    mention_flag: bool = False
    original_text: str | None = None

    def __str__(self) -> str:
        text = ""
        if self.not_flag:
            text += "NOT "
        if self.talk_subject is not None:
            text += " " + f"Agent[0{self.talk_subject}]"
        text += " " + self.action
        if self.talk_object is not None:
            text += " " + f"Agent[0{self.talk_object}]"
        if self.role is not None:
            text += " " + self.role
        if self.team is not None:
            text += " " + self.team
        return text.strip()
