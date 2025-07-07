"""人狼のエージェントクラスを定義するモジュール."""

from __future__ import annotations

import random
from collections import defaultdict

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

    def get_best_attack_target(self) -> str:
        """最適な襲撃対象を選択する."""
        alive_agents = self.get_alive_agents()
        
        # 自分以外のプレイヤーから選択
        candidates = [agent for agent in alive_agents if agent != self.agent_name]
        
        if not candidates:
            return random.choice(alive_agents)
        
        # 占い師候補を優先的に襲撃
        for agent in candidates:
            # 简单的占い師检测逻辑
            for talk in self.talk_history:
                if talk.agent == agent and "占い師" in talk.text:
                    return agent
        
        # 発言が多くて影響力がありそうなプレイヤーを襲撃
        talk_counts = defaultdict(int)
        for talk in self.talk_history:
            talk_counts[talk.agent] += 1
        
        # 発言回数が多い順にソート
        candidates.sort(key=lambda x: talk_counts[x], reverse=True)
        return candidates[0]

    def whisper(self) -> str:
        """囁きリクエストに対する応答を返す."""
        # 构造 prompt
        role = self.role.value if hasattr(self.role, "value") else str(self.role)
        talk_history = "\n".join([f"{t.agent}: {t.text}" for t in self.talk_history[-10:]])
        alive_agents = [a for a in self.get_alive_agents() if a != self.agent_name]
        prompt = (
            f"あなたはAI人狼ゲームの{role}（囁き）です。以下はこれまでの発言履歴です：\n"
            f"{talk_history}\n"
            f"現在生存しているプレイヤーは{', '.join(alive_agents)}です。\n"
            "今夜、仲間の人狼や狂人に向けて日本語で一言囁いてください。"
        )
        from utils.llm_api import call_deepseek_llm, call_openai_llm
        model = "gpt-3.5-turbo" # OpenAI LLM API
        #return call_deepseek_llm(prompt, temperature=0.7, max_tokens=64)
        return call_openai_llm(prompt, temperature=0.7, max_tokens=256, model=model)

    def attack(self) -> str:
        """襲撃リクエストに対する応答を返す."""
        target = self.get_best_attack_target()
        self.agent_logger.logger.info(f"襲撃対象: {target}")
        return target
