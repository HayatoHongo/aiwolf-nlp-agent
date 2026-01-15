"""人狼のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent


class Werewolf(Agent):
    """人狼のエージェントクラス."""

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        """人狼のエージェントを初期化する."""
        super().__init__(config, name, game_id, Role.WEREWOLF)

    def whisper(self) -> str:
        """囁きリクエストに対する応答を返す."""
        return super().whisper()

    def talk(self) -> str:
        """トークリクエストに対する応答を返す."""
        return super().talk()

    def vote(self) -> str:
        """投票リクエストに対する応答を返す."""
        return super().vote()

    def attack(self) -> str:
        """襲撃リクエストに対する応答を返す."""
        return super().attack()
