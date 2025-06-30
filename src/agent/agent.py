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

        self.prev_day_summary = ""

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
        persona = self.info.profile if self.info and self.info.profile else ""
        display_name = self.info.agent if self.info and self.info.agent else self.agent_name
        persona_profile = ""
        if self.info and self.info.profile:
            persona_profile = (
                f"あなたの性格・背景情報は以下の通りです：\n{self.info.profile}\n"
                "必ずこの性格・口調・話し方を守って発言してください。\n"
            )

        prev_summary = ""
        if self.prev_day_summary:
            prev_summary = (
                "【前日の議論まとめ】\n"
                f"{self.prev_day_summary}\n"
                "この内容をよく読み、あなたの役職として今日どのような戦略・推理・発言をすべきか考えてください。\n"
                "・誰が怪しいか、なぜそう思うか\n"
                "・どんな情報が新たに出てきたか\n"
                "・今日の議論で注目すべきポイント\n"
                "・他のプレイヤーに質問したいことや、議論を深めるための提案\n"
                "などを意識して、自然な日本語で一言発言してください。\n"
                "※同じ内容の繰り返しや曖昧な発言は避け、できるだけ具体的な推理や意見を述べてください。\n"
                "本当に何も言うことがなければ「SKIP」とだけ答えてください。\n"
            )

        last_executed = getattr(self.info, "executed_agent", None)
        if not last_executed:
            last_executed = "なし"
        last_attacked = getattr(self.info, "attacked_agent", None)
        if not last_attacked:
            last_attacked = "なし"
            

        if self.day == 0:
            base_setting = (
                f"これは5人プレイのAI人狼ゲームです。今日は{self.day}日目です。"
                "配役は以下の通りです：【村人2人、占い師1人、人狼1人、狂人1人】。\n"
                "今日は最初の議論日です。"
            )
        else:
            base_setting = (
                f"これは5人プレイのAI人狼ゲームです。今日は{self.day}日目です。昨日は{last_executed}が処刑され、{last_attacked}が襲撃されました。"
                "配役は以下の通りです：【村人2人、占い師1人、人狼1人、狂人1人】。\n"
                "他のプレイヤーの正体はわかりません。あなたは自分の役職と過去の発言から、他者の正体を推理し、"
                "村人陣営または人狼陣営として勝利を目指してください。"
                "同じ内容を繰り返さず、新しい視点や推理を述べてください。気になる点について他の人に質問してもいいです。"
                "もし本当に何も言うことがなければ、SKIPとだけ答えてください。"
            )
        
        if self.role == Role.VILLAGER:
            prompt = (
                f"{base_setting}\n"
                f"{prev_summary}"
                f"{persona_profile}"
                f"あなたはAI人狼ゲームの村人（プレイヤー名：{display_name}）です。"
                "特殊能力はありませんが、村人陣営として人狼を見つけ出し、投票で排除することが目的です。発言では他のプレイヤーの矛盾や態度に注目し、占い師の情報を正しく活用してください。冷静に議論を進め、狂人や人狼の偽情報に惑わされず、村人が多数派であるうちに人狼を見抜きましょう。村人であることを自然に伝える発言を心がけ、周囲の信頼を得ることが大切です。"
                "村人として自然な日本語で一言発言してください。"
                "以下はこれまでの発言履歴です：\n"
                f"{talk_history}\n"
                "今、あなたが自然な日本語で一言発言してください。"
            )
        elif self.role == Role.SEER:
            prompt = (
                f"{base_setting}\n"
                f"{prev_summary}"
                f"{persona_profile}"
                f"あなたはAI人狼ゲームの占い師（プレイヤー名：{display_name}）です。"
                "村人陣営で、毎晩1人の陣営（村人 or 人狼）を知ることができます。初日はCOするか慎重に判断してください。自分が人狼に襲撃されないように、【潜伏】を選ぶこともあります。COのタイミングは、確実な情報が得られて信頼されると思ったとき、または他の偽占い師が出たときに対抗する形が有効です。議論では信用を得るために論理的かつ慎重に行動し、真の情報で村人を導いてください。"
                "以下はこれまでの発言履歴です：\n"
                f"{talk_history}\n"
                "今、あなたが自然な日本語で一言発言してください。"
            )
        elif self.role == Role.WEREWOLF:
            prompt = (
                f"{base_setting}\n"
                f"{prev_summary}"
                f"{persona_profile}"
                f"あなたはAI人狼ゲームの人狼（プレイヤー名：{display_name}）です。"
                "あなたは『人狼』です。夜に1人を襲撃し、ゲームから除外できます。目的は村人陣営の人数を自分たち以下にすることです。日中は村人のふりをして、冷静かつ自然に発言してください。占い師がCOした場合は、偽占いを装って村人を混乱させるのも一つの戦略です。仲間の狂人がサポートしてくれることもあります。疑われないように村人と同じ目線で発言し、状況を見て投票を誘導しましょう。"
                "以下はこれまでの発言履歴です：\n"
                f"{talk_history}\n"
                "今、あなたが自然な日本語で一言発言してください。"
            )
        elif self.role == Role.POSSESSED:
            prompt = (
                f"{base_setting}\n"
                f"{prev_summary}"
                f"{persona_profile}"
                f"あなたはAI人狼ゲームの狂人（プレイヤー名：{display_name}）です。"
                "人狼陣営に属しますが、襲撃はできません。あなたの役目は、【人狼をサポートしつつ村人を混乱させる】ことです。CO戦略としては『偽の占い師』を名乗るか、あるいは自然な『村人』を装うことが可能です。ただし、言動に矛盾があるとすぐに疑われるため、発言は常に村人として論理的に見えるよう注意しましょう。あくまで正論に見える嘘で議論を誘導し、人狼の勝利に貢献してください。"
                "以下はこれまでの発言履歴です：\n"
                f"{talk_history}\n"
                "今、あなたが自然な日本語で一言発言してください。"
            )
        else:
            prompt = (
                f"{base_setting}\n"
                f"{prev_summary}"
                f"{persona_profile}"
                f"あなたはAI人狼ゲームの{role}（プレイヤー名：{display_name}）です。"
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
        # 整理当天发言
        talks = [f"{t.agent}: {t.text}" for t in self.talk_history if t.text not in ("OVER", "SKIP")]
        talk_history = "\n".join(talks)
        if talk_history:
            prompt = (
                "以下はAI人狼ゲームの1日の全発言履歴です。\n"
                "重要な出来事・主な議論ポイント・怪しい発言・CO状況などを日本語で簡潔にまとめてください。\n"
                f"{talk_history}\n"
                "まとめ："
            )
            summary = call_deepseek_llm(prompt, temperature=0.3, max_tokens=128)
            self.prev_day_summary = summary
        else:
            self.prev_day_summary = ""

    def divine(self) -> str:
        """占いリクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def guard(self) -> str:
        """護衛リクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def vote(self) -> str:
        """用LLM生成投票目标和理由，并详细记录日志，返回值只返回玩家名。"""
        role = self.role.value if hasattr(self.role, "value") else str(self.role)
        all_talks = self.talk_history + self.whisper_history
        filtered_talks = [t for t in all_talks if t.text not in ("OVER", "SKIP")]
        talk_history = "\n".join([f"{t.agent}: {t.text}" for t in filtered_talks])
        alive_agents = [a for a in self.get_alive_agents() if a != self.agent_name]
        
        if not alive_agents:
            print("No alive agents, voting for self.")
            return self.agent_name  # 如果没有其他存活玩家，投给自己
        
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
            print(f"LLM输出: {result}")
            import re
            # 先匹配 Agent[xx]
            m = re.search(r"(Agent\\[\\d+\\])", result)
            if m and m.group(1) in agent_map:
                target_name = agent_map[m.group(1)]
                print(f"匹配到编号: {m.group(1)}，实际投票对象: {target_name}")
                return target_name
            # 再匹配具体名字
            for name in alive_agents:
                if name in result:
                    print(f"匹配到名字: {name}")
                    return name
            # fallback
            target = random.choice(alive_agents)
            print(f"未匹配到，随机投票: {target}")
            return target
        except Exception as e:
            target = random.choice(alive_agents)
            print(f"LLM异常: {e}，随机投票: {target}")
            return target

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
