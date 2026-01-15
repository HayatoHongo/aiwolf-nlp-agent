"""騎士のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent


class Bodyguard(Agent):
    """騎士のエージェントクラス."""

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        """騎士のエージェントを初期化する."""
        super().__init__(config, name, game_id, Role.BODYGUARD)

    def talk(self) -> str:
        """トークリクエストに対する応答を返す."""
        return super().talk()

    def guard(self) -> str:
        """護衛リクエストに対する応答を返す."""
        return super().guard()

    def vote(self) -> str:
        """投票リクエストに対する応答を返す."""
        return super().vote()
