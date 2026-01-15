"""霊媒師のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent


class Medium(Agent):
    """霊媒師のエージェントクラス."""

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        """霊媒師のエージェントを初期化する."""
        super().__init__(config, name, game_id, Role.MEDIUM)

    def talk(self) -> str:
        """トークリクエストに対する応答を返す."""
        return super().talk()

    def vote(self) -> str:
        """投票リクエストに対する応答を返す."""
        return super().vote()
