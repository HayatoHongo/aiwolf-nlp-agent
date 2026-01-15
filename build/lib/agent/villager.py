"""村人のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent


class Villager(Agent):
    """村人のエージェントクラス."""

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        """村人のエージェントを初期化する."""
        super().__init__(config, name, game_id, Role.VILLAGER)

    def talk(self) -> str:
        """トークリクエストに対する応答を返す."""
        return super().talk()

    def vote(self) -> str:
        """投票リクエストに対する応答を返す."""
        return super().vote()
