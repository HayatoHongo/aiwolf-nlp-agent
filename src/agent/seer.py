"""占い師のエージェントクラスを定義するモジュール."""

from __future__ import annotations

import random
from collections import defaultdict

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent

from utils.llm_api import call_deepseek_llm, call_openai_llm, call_o4mini_http  


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
        """占いリクエストに対する応答を返す（LLM＋ルールベースフォールバック）。"""
        alive_agents = self.get_alive_agents()
        # まだ占っていない人を抽出
        undivined = [agent for agent in alive_agents if agent not in self.divine_results]
        if not undivined:
            print("未占い候補なし → ランダム選択")
            return random.choice(alive_agents)

        # 発言履歴を文字列化
        filtered = [t for t in self.talk_history if t.text not in ("OVER", "SKIP")]
        talk_history = "\n".join(f"{t.agent}: {t.text}" for t in filtered)

        # エージェント番号マップ作成
        agent_map = {f"Agent[{i+1:02d}]": name for i, name in enumerate(undivined)}
        agent_list_str = "\n".join(f"{v}（{k}）" for k, v in agent_map.items())

        # プロンプト組み立て
        prompt = (
            f"あなたは人狼ゲームの占い師役です。以下はこれまでの発言履歴です：\n"
            f"{talk_history}\n"
            f"まだ占っていないプレイヤーは以下の通りです：\n{agent_list_str}\n"
            "この中から最適な占い対象を一人選び、その理由も日本語で簡潔に説明してください。\n"
            "出力は「Agent[xx]」または名前のみでお願いします。"
            "例: Agent[03]を占います。理由は発言が少ないからです。"
            "例: ベンジャミンに占います。理由は発言が少ないからです。"
        )

        try:
            #result = call_o4mini_http(user_prompt=prompt, system_prompt="256文字以内で簡潔に回答してください。")
            model = "gpt-4.1"  
            result = call_openai_llm(prompt, temperature=1.0, max_tokens=256, model=model)
            print(f"LLM出力（占い候補）: {result}")

            import re
            # Agent[xx]形式があれば優先
            m = re.search(r"(Agent\[\d+\])", result)
            if m and m.group(1) in agent_map:
                chosen = agent_map[m.group(1)]
                print(f"マッチ: {m.group(1)} → {chosen}")
                return chosen

            # 名前直接マッチ
            for name in undivined:
                if name in result:
                    print(f"名前マッチ: {name}")
                    return name

            print("LLMから有効な占い対象が取れず")
        except Exception as e:
            print(f"LLM呼び出し失敗: {e}")


    def daily_initialize(self) -> None:
        """昼開始リクエストに対する処理を行う."""
        super().daily_initialize()
        
        # 占い結果を処理
        if self.info and hasattr(self.info, 'divine_result') and self.info.divine_result:
            target = self.info.divine_result.target
            result = self.info.divine_result.result
            self.divine_results[target] = result
            self.agent_logger.logger.info(f"占い結果: {target} -> {result}")
