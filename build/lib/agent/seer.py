"""占い師のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent


class Seer(Agent):
    """占い師のエージェントクラス."""

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        """占い師のエージェントを初期化する."""
        super().__init__(config, name, game_id, Role.SEER)

    def talk(self) -> str:
        """トークリクエストに対する応答を返す."""
        return super().talk()

    def divine(self) -> str:
        """占いリクエストに対する応答を返す."""
        return super().divine()

    def vote(self) -> str:
        """投票リクエストに対する応答を返す."""
        return super().vote()
