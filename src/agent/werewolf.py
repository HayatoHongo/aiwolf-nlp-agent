"""人狼のエージェントクラスを定義するモジュール."""

from __future__ import annotations

import random
from collections import defaultdict

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent

from utils.llm_api import call_deepseek_llm, call_openai_llm, call_o4mini_http  


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
        """最適な襲撃対象を選択する（LLM＋ルールベースフォールバック）。"""
        alive_agents = self.get_alive_agents()
        # 自分以外のプレイヤーから選択
        candidates = [agent for agent in alive_agents if agent != self.agent_name]
        if not candidates:
            return random.choice(alive_agents)
        
        # 1) LLMに投げるための発言履歴文字列を作成
        filtered = [t for t in self.talk_history if t.text not in ("OVER", "SKIP")]
        talk_history = "\n".join(f"{t.agent}: {t.text}" for t in filtered)
        
        # 2) エージェント番号マッピングを作成
        agent_map = {f"Agent[{i+1:02d}]": name for i, name in enumerate(candidates)}
        agent_list_str = "\n".join(f"{v}（{k}）" for k, v in agent_map.items())
        
        # 3) プロンプトを組み立て
        prompt = (
            f"あなたは人狼ゲームの人狼役です。以下はこれまでの発言履歴です：\n"
            f"{talk_history}\n"
            f"現在襲撃可能なプレイヤーは以下の通りです：\n{agent_list_str}\n"
            "この中から最適な襲撃対象を一人選び、その理由も日本語で非常に簡潔に説明してください。\n"
            "出力は「Agent[xx]」または名前（例：ベンジャミン）のみでお願いします。"
            "例: Agent[03]を攻撃します。理由は占い師であり危険だからです。"
            "例: ベンジャミンに投票します。理由は彼は私が人狼であることを疑っているからです。"
        )
        
        try:
            # o4-miniモデルで問い合わせ
            #result = call_o4mini_http(user_prompt=prompt,system_prompt="256文字以内で簡潔に回答してください。")
            model = "gpt-4.1"
            result = call_openai_llm(prompt, temperature=1.0, max_tokens=256, model=model)
            print(f"LLM出力: {result}")  # ← ここで結果をログ出力

            # Agent[xx]形式を優先
            import re
            m = re.search(r"(Agent\[\d+\])", result)
            if m and m.group(1) in agent_map:
                return agent_map[m.group(1)]
            # 名前が直接出ていればそれを
            for name in candidates:
                if name in result:
                    return name
            print("LLMから有効な襲撃対象が取れず")
        except Exception as e:
            print(f"LLM呼び出しが失敗したか、または有効なエージェント名もしくは番号を含む回答を得ることができませんでした。: {e} ")


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
        #result = call_o4mini_http(user_prompt=prompt, system_prompt="256文字以内で簡潔に回答してください。")
        model = "gpt-4.1"  
        result = call_openai_llm(prompt, temperature=1.0, max_tokens=256, model=model)
        return result
    

    def attack(self) -> str:
        """襲撃リクエストに対する応答を返す."""
        target = self.get_best_attack_target()
        self.agent_logger.logger.info(f"襲撃対象: {target}")
        return target
