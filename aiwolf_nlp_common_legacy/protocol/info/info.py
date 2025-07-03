from __future__ import annotations

from aiwolf_nlp_common_legacy.protocol.info.result import DivineResult, MediumResult

from .list import AttackVoteList, VoteList
from .map.role_map import RoleMap
from .map.status_map import StatusMap


class Info:
    day: int
    agent: str
    medium_result: MediumResult
    divine_result: DivineResult
    executed_agent: str | None
    attacked_agent: str | None
    vote_list: VoteList
    attack_vote_list: AttackVoteList
    status_map: StatusMap
    role_map: RoleMap

    def __str__(self) -> str:
        executed_text = (
            self.executed_agent if self.has_executed_agent() else "No Result Available"
        )
        attacked_text = (
            self.attacked_agent if self.has_attacked_agent() else "No Result Available"
        )

        return (
            f"Day: {self.day}\n"
            f"Agent: {self.agent}\n\n"
            f"{self.medium_result}\n\n"
            f"{self.divine_result}\n\n"
            f"Executed Agent: {executed_text}\n"
            f"Attacked Agent: {attacked_text}\n\n"
            f"{self.status_map}\n\n"
            f"{self.role_map}\n\n"
        )

    def __init__(self, value: dict | None = None) -> None:
        if value is not None:
            self.day = value["day"]
            self.agent = (
                str(value["agent"]) if value["agent"] is not None else ""
            )  # Agentオブジェクトを文字列に変換
            self.medium_result = MediumResult(
                value.get("medium_result")
            )  # スネークケースに変更
            self.divine_result = DivineResult(
                value.get("divine_result")
            )  # スネークケースに変更

            # executed_agent と attacked_agent は Agent オブジェクトなので文字列に変換
            executed = value.get("executed_agent")
            self.executed_agent = str(executed) if executed is not None else None

            attacked = value.get("attacked_agent")
            self.attacked_agent = str(attacked) if attacked is not None else None

            self.vote_list = VoteList(value.get("vote_list"))  # スネークケースに変更
            self.attack_vote_list = AttackVoteList(
                value.get("attack_vote_list")
            )  # スネークケースに変更
            self.status_map = StatusMap(value["status_map"])  # スネークケースに変更
            self.role_map = RoleMap(value["role_map"])  # スネークケースに変更

    def update(self, value: dict | None) -> None:
        self.__init__(value)

    def has_executed_agent(self) -> bool:
        return self.executed_agent is not None

    def has_attacked_agent(self) -> bool:
        return self.attacked_agent is not None
