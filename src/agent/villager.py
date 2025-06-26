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

    def parse_info(self, receive: str) -> None:
        """受信した情報を解析する."""
        return super().parse_info(receive)

    def get_info(self):
        """エージェントの情報を取得する."""
        return super().get_info()

    def initialize(self) -> None:
        """エージェントを初期状態に設定する."""
        return super().initialize()

    def daily_initialize(self) -> None:
        """新しい日が始まるときにエージェントを初期化する."""
        return super().daily_initialize()

    def daily_finish(self) -> None:
        """日が終わるときにエージェントの状態を更新する."""
        return super().daily_finish()

    def talk(self) -> str:
        """トークリクエストに対する応答を返す."""
        return super().talk()

    def vote(self) -> str:
        """投票リクエストに対する応答を返す."""
        return super().vote()

    def whisper(self) -> str:
        """ささやきリクエストに対する応答を返す."""
        return super().whisper()

    def action(self) -> str:
        """アクションリクエストに対する応答を返す."""
        return super().action()
