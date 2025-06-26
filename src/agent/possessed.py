"""狂人のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent


class Possessed(Agent):
    """狂人のエージェントクラス."""

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        """狂人のエージェントを初期化する。"""
        super().__init__(config, name, game_id, Role.POSSESSED)
        # 狂人特有的初始化逻辑可以在这里添加
