"""エージェントの基底クラスを定義するモジュール."""

from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING

from aiwolf_nlp_common.packet import Info, Packet, Request, Role, Setting, Status, Talk

from utils.agent_logger import AgentLogger
from utils.stoppable_thread import StoppableThread
from utils.llm_api import call_deepseek_llm

if TYPE_CHECKING:
    from collections.abc import Callable


class Agent:
    """エージェントの基底クラス."""

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,
    ) -> None:
        """エージェントの初期化を行う."""
        self.config = config
        self.agent_name = name
        self.agent_logger = AgentLogger(config, name, game_id)
        self.request: Request | None = None
        self.info: Info | None = None
        self.setting: Setting | None = None
        self.talk_history: list[Talk] = []
        self.whisper_history: list[Talk] = []
        self.role = role

        self.day = 0

        self.comments: list[str] = []
        with Path.open(
            Path(str(self.config["path"]["random_talk"])),
            encoding="utf-8",
        ) as f:
            self.comments = f.read().splitlines()

        self.talk_count = 0
        self.talk_limit = 1  # 或你想要的上限

    @staticmethod
    def timeout(func: Callable) -> Callable:
        """アクションタイムアウトを設定するデコレータ."""

        def _wrapper(self, *args, **kwargs) -> str:  # noqa: ANN001, ANN002, ANN003
            res = ""

            def execute_with_timeout() -> None:
                nonlocal res
                try:
                    res = func(self, *args, **kwargs)
                except Exception as e:  # noqa: BLE001
                    res = e

            thread = StoppableThread(target=execute_with_timeout)
            thread.start()
            timeout_value = (
                self.setting.timeout.action
                if hasattr(self, "setting") and self.setting
                else 0
            ) // 1000
            if timeout_value > 0:
                thread.join(timeout=timeout_value)
                if thread.is_alive():
                    self.agent_logger.logger.warning(
                        "アクションがタイムアウトしました: %s",
                        self.request,
                    )
                    if bool(self.config["agent"]["kill_on_timeout"]):
                        thread.stop()
                        self.agent_logger.logger.warning(
                            "アクションを強制終了しました: %s",
                            self.request,
                        )
            else:
                thread.join()
            if isinstance(res, Exception):
                raise res
            return res

        return _wrapper

    def set_packet(self, packet: Packet) -> None:
        """パケット情報をセットする."""
        self.request = packet.request
        if packet.info:
            self.info = packet.info
        if packet.setting:
            self.setting = packet.setting
        if packet.talk_history:
            self.talk_history.extend(packet.talk_history)
        if packet.whisper_history:
            self.whisper_history.extend(packet.whisper_history)
        if self.request == Request.INITIALIZE:
            self.talk_history: list[Talk] = []
            self.whisper_history: list[Talk] = []
        if hasattr(packet, "day"):
            self.day = packet.day
        elif hasattr(packet, "info") and hasattr(packet.info, "day"):
            self.day = packet.info.day
        self.agent_logger.logger.debug(packet)

    def get_alive_agents(self) -> list[str]:
        """生存しているエージェントのリストを取得する."""
        if not self.info:
            return []
        return [k for k, v in self.info.status_map.items() if v == Status.ALIVE]

    def name(self) -> str:
        """名前リクエストに対する応答を返す."""
        return self.agent_name

    def initialize(self) -> None:
        """ゲーム開始リクエストに対する初期化処理を行う."""

    def daily_initialize(self) -> None:
        """昼開始リクエストに対する処理を行う."""
        self.talk_count = 0

    def whisper(self) -> str:
        """囁きリクエストに対する応答を返す."""
        return random.choice(self.comments)  # noqa: S311

    def talk(self) -> str:
        if hasattr(self, "talk_limit") and self.talk_count >= self.talk_limit:
            return "OVER"
        self.talk_count += 1
        """用LLM生成发言"""
        role = self.role.value if hasattr(self.role, "value") else str(self.role)
        all_talks = self.talk_history + self.whisper_history
        filtered_talks = [t for t in all_talks if t.text not in ("OVER", "SKIP")]
        talk_history = "\n".join([f"{t.agent}: {t.text}" for t in filtered_talks])

        last_executed = getattr(self.info, "executed_agent", None)
        if not last_executed:
            last_executed = "なし"
        last_attacked = getattr(self.info, "attacked_agent", None)
        if not last_attacked:
            last_attacked = "なし"

        if self.day == 0:
            base_setting = (
                f"これは5人プレイのAI人狼ゲームです。今日は{self.day}日目です。"
                "配役は以下の通りです：【村人2人、占い師1人、人狼1人、狂人1人】。"
                "今日は最初の議論日です。"
            )
        else:
            base_setting = (
            f"これは5人プレイのAI人狼ゲームです。今日は{self.day}日目です。昨日は{last_executed}が処刑され、{last_attacked}が襲撃されました。"
            "配役は以下の通りです：【村人2人、占い師1人、人狼1人、狂人1人】。"
            "他のプレイヤーの正体はわかりません。あなたは自分の役職と過去の発言から、他者の正体を推理し、"
            "村人陣営または人狼陣営として勝利を目指してください。"
            "同じ内容を繰り返さず、新しい視点や推理を述べてください。"
            "もし本当に何も言うことがなければ、SKIPとだけ答えてください。"
        )
        
        if self.role == Role.VILLAGER:
            prompt = (
                f"{base_setting}\n\n"
                f"あなたはAI人狼ゲームの村人（プレイヤー名：{self.agent_name}）です。"
                "特殊能力はありませんが、村人陣営として人狼を見つけ出し、投票で排除することが目的です。発言では他のプレイヤーの矛盾や態度に注目し、占い師の情報を正しく活用してください。冷静に議論を進め、狂人や人狼の偽情報に惑わされず、村人が多数派であるうちに人狼を見抜きましょう。村人であることを自然に伝える発言を心がけ、周囲の信頼を得ることが大切です。"
                "村人として自然な日本語で一言発言してください。"
                "以下はこれまでの発言履歴です：\n"
                f"{talk_history}\n"
                "今、あなたが自然な日本語で一言発言してください。"
            )
        elif self.role == Role.SEER:
            prompt = (
                f"{base_setting}\n\n"
                f"あなたはAI人狼ゲームの占い師（プレイヤー名：{self.agent_name}）です。"
                "村人陣営で、毎晩1人の陣営（村人 or 人狼）を知ることができます。初日はCOするか慎重に判断してください。自分が人狼に襲撃されないように、【潜伏】を選ぶこともあります。COのタイミングは、確実な情報が得られて信頼されると思ったとき、または他の偽占い師が出たときに対抗する形が有効です。議論では信用を得るために論理的かつ慎重に行動し、真の情報で村人を導いてください。"
                "以下はこれまでの発言履歴です：\n"
                f"{talk_history}\n"
                "今、あなたが自然な日本語で一言発言してください。"
            )
        elif self.role == Role.WEREWOLF:
            prompt = (
                f"{base_setting}\n\n"
                f"あなたはAI人狼ゲームの人狼（プレイヤー名：{self.agent_name}）です。"
                "あなたは『人狼』です。夜に1人を襲撃し、ゲームから除外できます。目的は村人陣営の人数を自分たち以下にすることです。日中は村人のふりをして、冷静かつ自然に発言してください。占い師がCOした場合は、偽占いを装って村人を混乱させるのも一つの戦略です。仲間の狂人がサポートしてくれることもあります。疑われないように村人と同じ目線で発言し、状況を見て投票を誘導しましょう。"
                "以下はこれまでの発言履歴です：\n"
                f"{talk_history}\n"
                "今、あなたが自然な日本語で一言発言してください。"
            )
        elif self.role == Role.POSSESSED:
            prompt = (
                f"{base_setting}\n\n"
                f"あなたはAI人狼ゲームの狂人（プレイヤー名：{self.agent_name}）です。"
                "人狼陣営に属しますが、襲撃はできません。あなたの役目は、【人狼をサポートしつつ村人を混乱させる】ことです。CO戦略としては『偽の占い師』を名乗るか、あるいは自然な『村人』を装うことが可能です。ただし、言動に矛盾があるとすぐに疑われるため、発言は常に村人として論理的に見えるよう注意しましょう。あくまで正論に見える嘘で議論を誘導し、人狼の勝利に貢献してください。"
                "以下はこれまでの発言履歴です：\n"
                f"{talk_history}\n"
                "今、あなたが自然な日本語で一言発言してください。"
            )
        else:
            prompt = (
                f"{base_setting}\n\n"
                f"あなたはAI人狼ゲームの{role}（プレイヤー名：{self.agent_name}）です。"
                "以下はこれまでの発言履歴です：\n"
                f"{talk_history}\n"
                "今、あなたが自然な日本語で一言発言してください。"
            )
        result = call_deepseek_llm(prompt, temperature=0.7, max_tokens=64)
        if not result or result.strip().upper() == "SKIP":
            return "SKIP"
        return result

    def daily_finish(self) -> None:
        """昼終了リクエストに対する処理を行う."""

    def divine(self) -> str:
        """占いリクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def guard(self) -> str:
        """護衛リクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def vote(self) -> str:
        """用LLM生成投票目标和理由"""
        role = self.role.value if hasattr(self.role, "value") else str(self.role)
        all_talks = self.talk_history + self.whisper_history
        filtered_talks = [t for t in all_talks if t.text not in ("OVER", "SKIP")]
        talk_history = "\n".join([f"{t.agent}: {t.text}" for t in filtered_talks])
        alive_agents = [a for a in self.get_alive_agents() if a != self.agent_name]
        
        if not alive_agents:
            return self.agent_name  # 如果没有其他存活玩家，投给自己
        
        # 假设 alive_agents = ["ベンジャミン", "Agent[01]", "ケンジ", "Agent[02]"]
        # 你可以构造一个映射字典
        agent_map = {f"Agent[{i+1:02d}]": name for i, name in enumerate(alive_agents)}
        agent_list_str = "\n".join([f"{v}（{k}）" for k, v in agent_map.items()])

        prompt = (
            f"あなたはAI人狼ゲームの{role}です。以下はこれまでの発言履歴です：\n"
            f"{talk_history}\n"
            f"現在生存しているプレイヤーは以下の通りです：\n{agent_list_str}\n"
            "この中から一人を投票で選び、その理由も日本語で簡潔に説明してください。"
            "投票先は 'Agent[xx]' または名前（例：ベンジャミン）どちらでも構いません。"
            "例: Agent[03]に投票します。理由は発言が少ないからです。"
            "例: ベンジャミンに投票します。理由は発言が少ないからです。"
        )
        
        try:
            result = call_deepseek_llm(prompt, temperature=0.7, max_tokens=64)
            
            # 先匹配 Agent[xx]
            import re
            m = re.search(r"(Agent\[\d+\])", result)
            if m and m.group(1) in alive_agents:
                return result  # 直接返回

            # 再匹配具体名字
            for name in alive_agents:
                if name in result:
                    return result  # 直接返回

            # fallback
            target = random.choice(alive_agents)
            return f"{target}に投票します。理由はLLMの出力が不明です。!!!!!!!!!!!"
        except Exception as e:
            # 如果LLM调用失败，使用随机投票
            target = random.choice(alive_agents)
            return f"{target}に投票します。理由はAPIエラーのためです。!!!!!!!!!!!!!"

    def attack(self) -> str:
        """襲撃リクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def finish(self) -> None:
        """ゲーム終了リクエストに対する処理を行う."""

    @timeout
    def action(self) -> str | None:  # noqa: C901, PLR0911
        """リクエストの種類に応じたアクションを実行する."""
        match self.request:
            case Request.NAME:
                return self.name()
            case Request.TALK:
                return self.talk()
            case Request.WHISPER:
                return self.whisper()
            case Request.VOTE:
                return self.vote()
            case Request.DIVINE:
                return self.divine()
            case Request.GUARD:
                return self.guard()
            case Request.ATTACK:
                return self.attack()
            case Request.INITIALIZE:
                self.initialize()
            case Request.DAILY_INITIALIZE:
                self.daily_initialize()
            case Request.DAILY_FINISH:
                self.daily_finish()
            case Request.FINISH:
                self.finish()
        return None
