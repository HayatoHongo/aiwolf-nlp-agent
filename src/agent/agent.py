"""エージェントの基底クラスを定義するモジュール."""

from __future__ import annotations
from aiwolf_nlp_json_converter import AIWolfNLPJsonConverter
import random
from pathlib import Path
from typing import TYPE_CHECKING
from utils.llm_api import call_openai_llm
from dotenv import load_dotenv
load_dotenv()

from aiwolf_nlp_common.packet import Info, Packet, Request, Role, Setting, Status, Talk

from utils.agent_logger import AgentLogger
from utils.stoppable_thread import StoppableThread

if TYPE_CHECKING:
    from collections.abc import Callable

import configparser
import copy
import json
import random
from collections import defaultdict
from typing import DefaultDict

from cls import (
    DivineResult,
    GameInfo,
    GameSetting,
    Judge,
    ProtocolMean,
    Role,
    Status,
    TalkHist,
    Topic,
    VoteHist,
)
from lib.TalkGenerator.TalkGenerator import TalkGenerator
from lib.AIWolf import AIWolfCommand, RolePredictor, ScoreMatrix
from lib.ConvertToProtocol import convert_to_protocol


class Agent:
    """エージェントの基底クラス."""

    index: str  # 自身
    """Myself."""
    vote_candidate: str  # 投票候補
    """Candidate for voting."""
    gameInfo: GameInfo  # ゲーム情報
    """Information about current game."""
    gameSetting: GameSetting  # ゲーム設定
    """Settings of current game."""
    comingout_map: DefaultDict[str, Role]  # CO辞書
    """Mapping between an agent and the role it claims that it is."""
    divination_reports: list[DivineResult]  # 占い結果
    """Time series of divination reports."""
    talk_list_head: int  # talkのインデックス
    """Index of the talk to be analysed next."""
    will_vote_reports: DefaultDict[str, str]  # 投票宣言
    talkHistory: list[TalkHist]  # talk履歴
    protocolHistory: list[ProtocolMean]  # protocol履歴
    talk_list_all: list[TalkHist]  # 全talkリスト
    protocol_list_all: list[ProtocolMean]  # 全protocolリスト
    talk_turn: int  # talkのターン
    role_predictor: RolePredictor  # role_predictor

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,
    ) -> None:
        """エージェントの初期化を行う."""
        self.config = config
        self.name = name
        self.agent_name = name #統合版でのエラー防止
        self.received = []
        self.gameContinue = True
        self.turn = 1
        self.agent_logger = AgentLogger(config, name, game_id)
        self.request: Request | None = None
        self.info: Info | None = None
        self.setting: Setting | None = None
        self.talk_history: list[Talk] = []
        self.whisper_history: list[Talk] = []
        self.role = role

        self.comments: list[str] = []
        with Path.open(
            Path(str(self.config["path"]["random_talk"])),
            encoding="utf-8",
        ) as f:
            self.comments = f.read().splitlines()
        self.talk_count = 0
        self.talk_limit = 1  # 或你想要的上限
        self.prev_day_summary = ""

    def initialize(self) -> None:
        self.index = str(self.gameInfo.agent)
        self.role = self.gameInfo.roleMap[self.index]
        self.divination_reports = []
        self.comingout_map = defaultdict(lambda: None)  # 修正: dict型で初期化
        self.identification_reports = []
        self.vote_candidate = None
        self.talk_list_head = 0
        self.will_vote_reports = defaultdict(lambda: None)
        self.talkHistory = []
        self.protocolHistory = []
        self.whisperHistory = []
        self.talk_list_all = []
        self.protocol_list_all = []
        self.talk_turn = 0
        self.role_predictor = None
        self.N = -1
        self.M = -1
        self.agent_idx_0based = -1
        # フルオープンしたかどうか
        self.doFO = False
        # self.all_talk_history = []
        # self.all_talk_history_protocol = []
        self.score_matrix = ScoreMatrix(
            self.gameInfo, self.gameSetting, self.index, self.role
        )

        self.role_predictor = RolePredictor(
            self.gameInfo, self.gameSetting, self.index, self.score_matrix
        )
        self.talk_generator = TalkGenerator(self.index)
        self.vote_list = []  # 最新の投票リストを保持

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
        # self.agent_logger.logger.debug(packet)

    def convert_json_for_legacy(self, json_str: str) -> dict:
        """新しいJSON形式を旧エージェント用に変換する."""
        try:
            # AIWolfNLPJsonConverterから辞書を取得
            converted_dict = AIWolfNLPJsonConverter.get_json_dict(received_str=json_str)

            # 辞書をJSON文字列に変換してreceivedリストに追加
            json_string = json.dumps(converted_dict)
            self.received.append(json_string)

            return converted_dict
        except Exception as e:
            self.agent_logger.logger.error(f"JSON変換エラー: {e}")
            return {}

    def get_alive_agents(self) -> list[str]:
        """生存しているエージェントのリストを取得する."""
        if not self.info:
            return []
        return [k for k, v in self.info.status_map.items() if v == Status.ALIVE]

    def name(self) -> str:
        """名前リクエストに対する応答を返す."""
        return self.name

    def get_info(self):
        print("[DEBUG] get_infoが呼ばれた")
        data = json.loads(self.received.pop(0))
        if data["gameInfo"] is not None:
            print("[DEBUG] gameInfoがNoneではない")
            self.gameInfo = GameInfo(**data["gameInfo"])
        if data["gameSetting"] is not None:
            self.gameSetting = GameSetting(**data["gameSetting"])
            print("[DEBUG] gameSettingがNoneではない")
        self.request = data["request"]
        self.talkHistory: list[TalkHist] = data["talkHistory"]
        if self.talkHistory is None:
            return
        self.protocolHistory: list[ProtocolMean] = []
        for talk in self.talkHistory:
            protocols = convert_to_protocol(talk["text"], str(talk["agent"]), self.index)
            print(f"[DEBUG] convert_to_protocol output: {protocols}")
            self.protocolHistory.extend(protocols)
            print("[DEBUG] talkHistoryをprotocolHistoryに変換した")

        print(f"[DEBUG] protocolHistory: {self.protocolHistory}")
        self.whisperHistory = data["whisperHistory"]
        self.score_matrix.update(self.gameInfo)
        # score_matrix更新後にrole_predictorの推論値を更新
        # if self.role_predictor is not None:
        self.role_predictor.update(self.gameInfo, self.gameSetting)
        for tk, tkz in zip(self.talkHistory, self.protocolHistory):
            day: int = int(tk["day"])
            turn: int = int(tk["turn"])
            talker: str = tk["agent"]
            self.talk_list_all.append(tk)
            self.protocol_list_all.append(tkz)
            if talker == self.index:  # Skip my talk.
                continue
            # 内容に応じて更新していく
            content: ProtocolMean = copy.deepcopy(tkz)
            print(f"[DEBUG] content.action: {content.action}, content: {content}")

            if content.action == Topic.CO:
                self.comingout_map[talker] = content.role
                self.score_matrix.talk_co(
                    self.gameInfo, self.gameSetting, talker, content.role, day, turn
                )
                print("会話履歴をスコアマトリクスに渡した")
                print("CO:\t", talker, content.role)
                self.role_predictor.update(self.gameInfo, self.gameSetting)  # ←追加
            elif content.action == Topic.DIVINED:
                self.score_matrix.talk_divined(
                    self.gameInfo,
                    self.comingout_map,
                    talker,
                    content.talk_object,
                    content.team,
                    day,
                    turn,
                    self.divination_reports,
                )
                print("占い会話履歴をスコアマトリクスに渡した")
                self.divination_reports.append(
                    Judge(talker, day, content.talk_object, content.team)
                )
                print("DIVINED:\t", talker, content.talk_object, content.team)
                self.role_predictor.update(self.gameInfo, self.gameSetting)  # ←追加
            elif content.action == Topic.VOTE:
                # 古い投票先が上書きされる前にスコアを更新 (2回以上投票宣言している場合に信頼度を下げるため)
                self.score_matrix.talk_will_vote(
                    self.gameInfo,
                    self.gameSetting,
                    talker,
                    content.talk_object,
                    day,
                    turn,
                    self.will_vote_reports,
                )
                print("投票宣言をスコアマトリクスに渡した")
                # 投票先を保存
                self.will_vote_reports[talker] = content.talk_object
                self.role_predictor.update(self.gameInfo, self.gameSetting)  # ←追加
            elif content.action == Topic.ESTIMATE:
                if content.role == Role.WEREWOLF:
                    self.score_matrix.talk_will_vote(
                        self.gameInfo,
                        self.gameSetting,
                        talker,
                        content.talk_object,
                        day,
                        turn,
                        self.will_vote_reports,
                    )
                    print("投票宣言をスコアマトリクスに渡した。人狼パターン")
                    self.will_vote_reports[talker] = content.talk_object
                    self.role_predictor.update(self.gameInfo, self.gameSetting)  # ←追加
                elif content.role == Role.VILLAGER:
                    self.score_matrix.talk_estimate(
                        self.gameInfo,
                        self.gameSetting,
                        talker,
                        content.talk_object,
                        content.role,
                        day,
                        turn,
                    )
                    print("推定会話履歴をスコアマトリクスに渡した")
                    self.role_predictor.update(self.gameInfo, self.gameSetting)  # ←追加
            elif content.action == Topic.SUSPECT:
                self.score_matrix.talk_suspect(
                    self.gameInfo,
                    self.gameSetting,
                    talker,
                    content.talk_object,
                    day,
                    turn,
                )
                print("疑い会話履歴をスコアマトリクスに渡した")
                self.role_predictor.update(self.gameInfo, self.gameSetting)  # ←追加

    def daily_initialize(self) -> None:
        self.talk_list_head = 0
        self.vote_candidate = None
        self.alive = []
        self.turn = 1
        for agent_num in self.gameInfo.statusMap:
            if (self.gameInfo.statusMap[agent_num] == "ALIVE") and (
                agent_num != self.index
            ):
                self.alive.append(agent_num)
        day: int = self.gameInfo.day
        if day >= 2:
            vote_list: list[VoteHist] = self.gameInfo.voteList
            self.vote_list = [
                VoteHist(str(v.agent), str(v.target), v.day) for v in vote_list
            ]  # agent/targetをstrで統一
            print(
                "[DEBUG] vote_list:",
                [(v.agent, v.target, v.day) for v in self.vote_list],
            )
            for v in self.vote_list:
                self.score_matrix.vote(
                    self.gameInfo, self.gameSetting, v.agent, v.target, v.day
                )
        self.will_vote_reports.clear()
        killed: list[Agent] = self.gameInfo.lastDeadAgentList
        if len(killed) > 0:
            self.score_matrix.killed(self.gameInfo, self.gameSetting, str(killed[0]))
            print("Killed:\t", self.gameInfo.lastDeadAgentList[0])
            if len(killed) > 1:
                print("Killed:\t", *self.gameInfo.lastDeadAgentList)
        else:
            print("Killed:\t", None)
        self.score_matrix.Nth_day_start(self.gameInfo, self.gameSetting)
        # role_predictorの状態を出力
        if hasattr(self, "role_predictor") and self.role_predictor is not None:
            try:
                print(
                    f"[DEBUG] role_predictor.prob_all: {getattr(self.role_predictor, 'prob_all', None)}"
                )
            except Exception as e:
                print(f"[DEBUG] role_predictor.prob_all: error: {e}")

    def whisper(self) -> str:
        """囁きリクエストに対する応答を返す."""
        return random.choice(self.comments)  # noqa: S311

    def talk(self) -> str:
        """役職に応じてtalkメソッドを振り分けるデリゲータ。"""
        # if self.role == Role.WEREWOLF or self.role == Role.POSSESSED:
        #     return self.talk_llmbase()
        #     #return self.talk_protocol()
        # else:
        # return self.talk_protocol()
        return self.talk_protocol()

    def talk_protocol(self) -> str:
        day: int = self.gameInfo.day
        self.vote_candidate = self.choose_vote_candidate()
        print(f"[DEBUG] talk: vote_candidate={self.vote_candidate}")
        print(f"[DEBUG] talk: will_vote_reports={dict(self.will_vote_reports)}")
        if hasattr(self, "role_predictor") and self.role_predictor is not None:
            try:
                print(
                    f"[DEBUG] talk: role_predictor.prob_all={getattr(self.role_predictor, 'prob_all', None)}"
                )
            except Exception as e:
                print(f"[DEBUG] talk: role_predictor.prob_all: error: {e}")
        # ...existing code...
        if day == 1:
            if self.turn == 1:
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", None, None),
                    request=True,
                    request_target="ANY",
                )
                #return_text = "だれかCOしましょう"
            elif 2 <= self.turn <= 8:
                rnd = random.randint(0, 2)
                if rnd == 0:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(
                            False, "ESTIMATE", None, self.vote_candidate, "WEREWOLF"
                        )
                    )
                    #return_text = f"私は村人で、{self.vote_candidate}が怪しいんじゃないかな"
                elif rnd == 1:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.vote_candidate)
                    )
                    #return_text = f"私は村人、投票先は{self.vote_candidate}です。"
                else:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.vote_candidate),
                        request=True,
                        request_target="ANY",
                    )
                    #return_text = f"私は村人投票先は{self.vote_candidate}です。投票をお願いします。"
            else:
                return_text = "Over"
        elif day >= 2:
            # 2日目：狂人COを認知→狂人がいるか判定→いる場合、狂人CO
            agent_possessed: Agent = self.role_predictor.chooseMostLikely(
                Role.POSSESSED, self.alive, 0.4
            )
            if agent_possessed is not None:
                alive_possessed = (
                    self.gameInfo.statusMap[agent_possessed] == Status.ALIVE
                )
                if self.turn == 1 and alive_possessed:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "CO", self.index, None, "POSSESSED")
                    )
                    #return_text = "PP宣言します。狂人です。"

            if 1 <= self.turn <= 6:
                rnd = random.randint(0, 2)
                if rnd == 0:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(
                            False, "ESTIMATE", None, self.vote_candidate, "WEREWOLF"
                        )
                    )
                elif rnd == 1:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.vote_candidate)
                    )
                else:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.vote_candidate),
                        request=True,
                        request_target="ANY",
                    )
            else:
                return_text = "Over"
        elif day == 0:
            if self.turn > 1:
                return_text = "Over"
            else:
                return_text = "よろしくお願いします！"
        else:
            return_text = "Over"
        self.turn += 1
        return return_text

    def talk_llmbase(self) -> str:
        # if hasattr(self, "talk_limit") and self.talk_count >= self.talk_limit:
        #     return "OVER"
        self.talk_count += 1
        """用LLM生成发言"""
        role = self.role.value if hasattr(self.role, "value") else str(self.role)
        all_talks = self.talk_history + self.whisper_history
        filtered_talks = [t for t in all_talks if t.text not in ("OVER", "SKIP")]
        talk_history = "\n".join([f"{t.agent}: {t.text}" for t in filtered_talks])
        persona = self.info.profile if self.info and self.info.profile else ""
        display_name = (
            self.info.agent if self.info and self.info.agent else self.agent_name
        )
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
        # 人狼系（人狼・狂人）は deepseek-chat、市民系は deepseek-reasoner を指定する
        if self.role == Role.WEREWOLF or self.role == Role.POSSESSED:
            # model = "deepseek-chat"
            model = "gpt-3.5-turbo"  # OpenAI LLM API
        else:
            # model = "deepseek-reasoner"
            model = "gpt-3.5-turbo"  # "gpt-4.1" # OpenAI LLM API
        # 调用 DeepSeek LLM API 生成发言内容
        # OpenAI LLM API も使用可能
        # result = call_deepseek_llm(prompt, temperature=0.7, max_tokens=128, model=model)
        result = call_openai_llm(prompt, temperature=1.5, max_tokens=256, model=model)
        if not result or result.strip().upper() == "SKIP":
            return "SKIP"
        return result

    def daily_finish(self) -> None:
        """昼終了リクエストに対する処理を行う."""

    def choose_vote_candidate(self) -> str:
        # 投票候補
        vote_candidates = self.alive
        # ---------- 5人村 ----------
        self.vote_candidate = self.role_predictor.chooseMostLikely(
            Role.WEREWOLF, vote_candidates
        )

        # ----- 投票ミスを防ぐ -----
        if self.vote_candidate is None or self.vote_candidate == self.index:
            print("vote_candidates: None or self.me")
            self.vote_candidate = self.role_predictor.chooseMostLikely(
                Role.WEREWOLF, vote_candidates
            )
        vote_target = (
            self.vote_candidate if self.vote_candidate is not None else self.index
        )
        return vote_target

    # 同数投票の時に自分の捨て票を変更する：最大投票以外のエージェントに投票している場合、投票先を変更する
    def changeVote(self, vote_list: list[VoteHist], role: Role, mostlikely=True) -> str:
        count: DefaultDict[Agent, int] = defaultdict(int)
        count_num: DefaultDict[str, int] = defaultdict(int)
        my_target: Agent = None
        new_target: Agent = None
        for vote in vote_list:
            agent = vote.agent
            target = vote.target
            no = str(target)
            if agent == self.index:
                my_target = target
            count[target] += 1
            count_num[no] += 1
        print("count_num:\t", count_num)
        # 最大投票数を取得
        max_vote = max(count_num.values())
        max_voted_agents: list[Agent] = []
        for agent, num in count.items():
            if num == max_vote and agent != self.index:
                max_voted_agents.append(agent)
        max_voted_agents_num = [a for a in max_voted_agents]
        print("max_voted_agents:\t", max_voted_agents_num)
        # 最大投票数のエージェントが複数人の場合
        if max_voted_agents:
            if mostlikely:
                new_target = self.role_predictor.chooseMostLikely(
                    role, max_voted_agents
                )
            else:
                new_target = self.role_predictor.chooseLeastLikely(
                    role, max_voted_agents
                )
        if new_target is None:
            new_target = my_target
        print("vote_candidate:\t", my_target, "→", new_target)
        return new_target if new_target is not None else self.index

    def vote(self) -> str:
        return self.vote_protocol()
        # return self.vote_llmbase()

    def vote_llmbase(self) -> str:
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
            "投票先は 名前（例：ベンジャミン）としてください。"
            "例: ベンジャミンに投票します。理由は発言が少ないからです。"
        )

        try:
            # 人狼系（人狼・狂人）は deepseek-chat、市民系は deepseek-reasoner を指定する
            if self.role == Role.WEREWOLF or self.role == Role.POSSESSED:
                # model = "deepseek-chat"
                model = "gpt-3.5-turbo"
            else:
                # model = "deepseek-reasoner"
                model = "gpt-3.5-turbo"  # "gpt-4.1"
            # 调用 DeepSeek LLM API 生成投票内容
            # result = call_deepseek_llm(prompt, temperature=0.7, max_tokens=128, model=model)
            result = call_openai_llm(
                prompt, temperature=1.5, max_tokens=256, model=model
            )
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

    def vote_protocol(self) -> str:
        self.vote_candidate = self.choose_vote_candidate()
        return self.vote_candidate

    def finish(self) -> str:
        self.gameContinue = False
        """ゲーム終了リクエストに対する処理を行う."""

    def divine(self) -> str:
        """占いリクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def guard(self) -> str:
        """護衛リクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def attack(self) -> str:
        """襲撃リクエストに対する応答を返す（サブクラスでオーバーライドする）."""

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


def hand_over(self, new_agent) -> None:
    # __init__
    new_agent.name = self.name
    new_agent.received = self.received
    new_agent.gameContinue = self.gameContinue
    new_agent.received = self.received
    new_agent.turn = self.turn
    new_agent.vote_candidate = self.vote_candidate
    new_agent.comingout_map = self.comingout_map
    new_agent.divination_reports = self.divination_reports
    new_agent.talk_list_head = self.talk_list_head
    new_agent.will_vote_reports = self.will_vote_reports
    new_agent.talkHistory = self.talkHistory
    new_agent.protocolHistory = self.protocolHistory
    new_agent.talk_list_all = self.talk_list_all
    new_agent.protocol_list_all = self.protocol_list_all
    new_agent.talk_turn = self.talk_turn
    new_agent.role_predictor = self.role_predictor

    # get_info
    new_agent.gameInfo = self.gameInfo
    new_agent.gameSetting = self.gameSetting
    new_agent.request = self.request
    new_agent.whisperHistory = self.whisperHistory

    # initialize
    new_agent.index = self.index
    new_agent.role = self.role
    new_agent.score_matrix = self.score_matrix
    new_agent.role_predictor = self.role_predictor
    new_agent.talk_generator = self.talk_generator

    # daily_initialize
    new_agent.turn = self.turn
