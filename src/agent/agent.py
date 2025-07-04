"""エージェントの基底クラスを定義するモジュール."""

from __future__ import annotations
from aiwolf_nlp_json_converter import AIWolfNLPJsonConverter
import random
from pathlib import Path
from typing import TYPE_CHECKING

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
        data = json.loads(self.received.pop(0))
        if data["gameInfo"] is not None:
            self.gameInfo = GameInfo(**data["gameInfo"])
        if data["gameSetting"] is not None:
            self.gameSetting = GameSetting(**data["gameSetting"])
        self.request = data["request"]
        self.talkHistory: list[TalkHist] = data["talkHistory"]
        if self.talkHistory is None:
            return
        self.protocolHistory: list[ProtocolMean] = []
        for talk in self.talkHistory:
            self.protocolHistory.extend(
                convert_to_protocol(talk["text"], str(talk["agent"]), self.index)
            )

        self.whisperHistory = data["whisperHistory"]
        self.score_matrix.update(self.gameInfo)
        for tk, tkz in zip(self.talkHistory, self.protocolHistory):
            day: int = tk["day"]
            turn: int = tk["turn"]
            talker: str = tk["agent"]
            self.talk_list_all.append(tk)
            self.protocol_list_all.append(tkz)
            if talker == self.index:  # Skip my talk.
                continue
            # 内容に応じて更新していく
            content: ProtocolMean = copy.deepcopy(tkz)
            print("content:", content)
            if content.action == Topic.CO:
                if content.role in self.gameInfo.existingRoleList:  # Role.UNC 対策
                    self.comingout_map[talker] = content.role
                    self.score_matrix.talk_co(
                        self.gameInfo, self.gameSetting, talker, content.role, day, turn
                    )
                print("CO:\t", talker, content.role)
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
                self.divination_reports.append(
                    Judge(talker, day, content.talk_object, content.team)
                )
                print("DIVINED:\t", talker, content.talk_object, content.team)
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
                # 投票先を保存
                self.will_vote_reports[talker] = content.talk_object
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
                    self.will_vote_reports[talker] = content.talk_object
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
            elif content.action == Topic.SUSPECT:
                self.score_matrix.talk_suspect(
                    self.gameInfo,
                    self.gameSetting,
                    talker,
                    content.talk_object,
                    day,
                    turn,
                )

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
            self.gameInfo, self.gameSetting, self, self.score_matrix
        )
        self.talk_generator = TalkGenerator(self.name)
        self.vote_list = []  # 最新の投票リストを保持

    def daily_initialize(self) -> None:
        self.talk_list_head = 0
        self.vote_candidate = None
        self.alive = []
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
                    ProtocolMean(False, "CO", "ANY", "ANY")
                )
            elif 2 <= self.turn <= 8:
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
                        ProtocolMean(False, "VOTE", "ANY", self.vote_candidate),
                        request=True,
                        request_target="ANY",
                    )
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
                        ProtocolMean(False, "CO", self.index, self.index, "POSSESSED")
                    )

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
                        ProtocolMean(False, "VOTE", "ANY", self.vote_candidate),
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
