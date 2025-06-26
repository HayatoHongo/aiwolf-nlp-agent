"""占い師のエージェントクラスを定義するモジュール."""

from __future__ import annotations

import random
from collections import defaultdict

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
        self.divine_results: dict[str, str] = {}  # 占い結果を保存

    def divine(self) -> str:
        """占いリクエストに対する応答を返す."""
        alive_agents = self.get_alive_agents()
        
        # 既に占ったプレイヤーを除外
        undivined = [agent for agent in alive_agents if agent not in self.divine_results]
        
        if not undivined:
            return random.choice(alive_agents)
        
        # 発言が少ないプレイヤーを優先
        talk_counts = defaultdict(int)
        for talk in self.talk_history:
            talk_counts[talk.agent] += 1
        
        # 発言回数が少ない順にソート
        undivined.sort(key=lambda x: talk_counts[x])
        return undivined[0]

    def daily_initialize(self) -> None:
        """昼開始リクエストに対する処理を行う."""
        super().daily_initialize()
        
        # 占い結果を処理
        if self.info and hasattr(self.info, 'divine_result') and self.info.divine_result:
            target = self.info.divine_result.target
            result = self.info.divine_result.result
            self.divine_results[target] = result
            self.agent_logger.logger.info(f"占い結果: {target} -> {result}")
