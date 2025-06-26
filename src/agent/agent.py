"""エージェントの基底クラスを定義するモジュール."""

from __future__ import annotations

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

import paramiko

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

    # --- 属性定義 ---
    index: str  # 自身
    vote_candidate: str  # 投票候補
    gameInfo: GameInfo  # ゲーム情報
    gameSetting: GameSetting  # ゲーム設定
    comingout_map: DefaultDict[str, Role]  # CO辞書
    divination_reports: list[DivineResult]  # 占い結果
    talk_list_head: int  # talkのインデックス
    will_vote_reports: DefaultDict[str, str]  # 投票宣言
    talkHistory: list[TalkHist]  # talk履歴
    protocolHistory: list[ProtocolMean]  # protocol履歴
    talk_list_all: list[TalkHist]  # 全talkリスト
    protocol_list_all: list[ProtocolMean]  # 全protocolリスト
    talk_turn: int  # talkのターン
    role_predictor: RolePredictor  # role_predictor
    score_matrix: ScoreMatrix  # スコア行列
    N: int  # プレイヤー数
    M: int  # 人狼数
    agent_idx_0based: int  # 0始まりの自分のインデックス
    doFO: bool  # フルオープンしたか
    name: str  # プレイヤー名
    received: list  # サーバーから受信した生データ
    gameContinue: bool  # ゲーム継続フラグ
    turn: int  # 現在のターン
    whisperHistory: list  # 囁き履歴

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,
        ssh_host=None,
        ssh_user=None,
        ssh_key=None,
    ) -> None:
        """エージェントの初期化を行う."""
        self.config = config
        self.agent_name = name
        self.name = name
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
        # --- 追加属性の初期化 ---
        self.index = ""
        self.vote_candidate = None
        self.gameInfo = None
        self.gameSetting = None
        self.comingout_map = defaultdict(lambda: None)
        self.divination_reports = []
        self.talk_list_head = 0
        self.will_vote_reports = defaultdict(lambda: None)
        self.talkHistory = []
        self.protocolHistory = []
        self.talk_list_all = []
        self.protocol_list_all = []
        self.talk_turn = 0
        self.role_predictor = None
        self.score_matrix = None
        self.N = -1
        self.M = -1
        self.agent_idx_0based = -1
        self.doFO = False
        self.received = []
        self.gameContinue = True
        self.turn = 1
        self.whisperHistory = []
        # --- SSH通信の雛形 ---
        self.ssh_client = None
        if ssh_host and ssh_user and ssh_key:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(ssh_host, username=ssh_user, key_filename=ssh_key)

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
        self.index = str(self.gameInfo.agent) if self.gameInfo else ""
        self.role = self.gameInfo.roleMap[self.index] if self.gameInfo else self.role
        self.divination_reports = []
        self.comingout_map = defaultdict(lambda: None)
        self.vote_candidate = None
        self.talk_list_head = 0
        self.will_vote_reports = defaultdict(lambda: None)
        self.talkHistory = []
        self.protocolHistory = []
        self.whisperHistory = []
        self.talk_list_all = []
        self.protocol_list_all = []
        self.talk_turn = 0
        self.N = -1
        self.M = -1
        self.agent_idx_0based = -1
        self.doFO = False
        self.score_matrix = (
            ScoreMatrix(self.gameInfo, self.gameSetting, self.index, self.role)
            if self.gameInfo and self.gameSetting
            else None
        )
        self.role_predictor = (
            RolePredictor(self.gameInfo, self.gameSetting, self, self.score_matrix)
            if self.gameInfo and self.gameSetting
            else None
        )
        self.talk_generator = TalkGenerator(self.name)

    def daily_initialize(self) -> None:
        """昼開始リクエストに対する処理を行う."""
        self.talk_list_head = 0
        self.vote_candidate = None
        self.alive = []
        self.turn = 1
        if self.gameInfo:
            for agent_num in self.gameInfo.statusMap:
                if (self.gameInfo.statusMap[agent_num] == "ALIVE") and (
                    agent_num != self.index
                ):
                    self.alive.append(int(agent_num))
            day: int = self.gameInfo.day
            if day >= 2:
                vote_list: list[VoteHist] = self.gameInfo.voteList
                for v in vote_list:
                    self.score_matrix.vote(
                        self.gameInfo,
                        self.gameSetting,
                        v["agent"],
                        v["target"],
                        v["day"],
                    )
            self.will_vote_reports.clear()

    def whisper(self) -> str:
        """囁きリクエストに対する応答を返す."""
        return random.choice(self.comments)  # noqa: S311

    def choose_vote_candidate(self) -> int:
        # 投票候補
        vote_candidates = self.alive if hasattr(self, "alive") else []
        # ---------- 5人村 ----------
        self.vote_candidate = (
            self.role_predictor.chooseMostLikely(Role.WEREWOLF, vote_candidates)
            if self.role_predictor
            else None
        )
        # ----- 投票ミスを防ぐ -----
        if self.vote_candidate is None or self.vote_candidate == self.index:
            self.vote_candidate = (
                self.role_predictor.chooseMostLikely(Role.WEREWOLF, vote_candidates)
                if self.role_predictor
                else None
            )
        vote_target = (
            self.vote_candidate if self.vote_candidate is not None else self.index
        )
        return int(vote_target)

    def talk(self) -> str:
        day: int = self.gameInfo.day if self.gameInfo else 0
        self.vote_candidate = self.choose_vote_candidate()
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
            agent_possessed = (
                self.role_predictor.chooseMostLikely(Role.POSSESSED, self.alive, 0.4)
                if self.role_predictor and hasattr(self, "alive")
                else None
            )
            if agent_possessed is not None:
                alive_possessed = (
                    self.gameInfo.statusMap[agent_possessed] == Status.ALIVE
                    if self.gameInfo
                    else False
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

    def vote(self) -> str:
        self.vote_candidate = self.choose_vote_candidate()
        data = {"agentIdx": self.vote_candidate}
        return json.dumps(data, separators=(",", ":"))

    def daily_finish(self) -> None:
        """昼終了リクエストに対する処理を行う."""

    def divine(self) -> str:
        """占いリクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def guard(self) -> str:
        """護衛リクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

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

    def send_via_ssh(self, message: str) -> None:
        if self.ssh_client:
            stdin, stdout, stderr = self.ssh_client.exec_command(f'echo "{message}"')
            # 必要に応じてサーバー側のコマンドに置き換えてください

    def receive_via_ssh(self) -> str:
        if self.ssh_client:
            stdin, stdout, stderr = self.ssh_client.exec_command(
                "cat /tmp/aiwolf_message"
            )
            return stdout.read().decode("utf-8")
        return ""

    def parse_info(self, receive: str) -> None:
        received_list = receive.split("}\n{")
        for index in range(len(received_list)):
            received_list[index] = received_list[index].rstrip()
            if received_list[index][0] != "{":
                received_list[index] = "{" + received_list[index]
            if received_list[index][-1] != "}":
                received_list[index] += "}"
            self.received.append(received_list[index])

    def get_info(self):
        data = json.loads(self.received.pop(0))
        if data.get("gameInfo") is not None:
            self.gameInfo = GameInfo(**data["gameInfo"])
        if data.get("gameSetting") is not None:
            self.gameSetting = GameSetting(**data["gameSetting"])
        self.request = data["request"]
        self.talkHistory = data.get("talkHistory", [])
        if self.talkHistory is None:
            return
        self.protocolHistory = []
        for talk in self.talkHistory:
            self.protocolHistory.extend(
                convert_to_protocol(talk["text"], str(talk["agent"]), self.index)
            )
        self.whisperHistory = data.get("whisperHistory", [])
        if self.score_matrix and self.gameInfo:
            self.score_matrix.update(self.gameInfo)
        for tk, tkz in zip(self.talkHistory, self.protocolHistory):
            day = tk["day"]
            turn = tk["turn"]
            talker = tk["agent"]
            self.talk_list_all.append(tk)
            self.protocol_list_all.append(tkz)
            if talker == self.index:
                continue
            content = copy.deepcopy(tkz)
            if content.action == Topic.CO:
                if content.role in self.gameInfo.existingRoleList:
                    self.comingout_map[talker] = content.role
                    if self.score_matrix:
                        self.score_matrix.talk_co(
                            self.gameInfo,
                            self.gameSetting,
                            talker,
                            content.role,
                            day,
                            turn,
                        )
            elif content.action == Topic.DIVINED:
                if self.score_matrix:
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
            elif content.action == Topic.VOTE:
                if self.score_matrix:
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
            elif content.action == Topic.ESTIMATE:
                if content.role == Role.WEREWOLF:
                    if self.score_matrix:
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
                    if self.score_matrix:
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
                if self.score_matrix:
                    self.score_matrix.talk_suspect(
                        self.gameInfo,
                        self.gameSetting,
                        talker,
                        content.talk_object,
                        day,
                        turn,
                    )
            self.talk_list_head += 1
