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
        """生存しているエージェントのリストを取得する（エージェント名）."""
        if not self.info:
            return []
        return [k for k, v in self.info.status_map.items() if v == Status.ALIVE]

    def get_alive_agent_ids(self) -> list[int]:
        """生存しているエージェントのIDリストを取得する."""
        alive_names = self.get_alive_agents()
        alive_ids = []
        for name in alive_names:
            agent_id = self.agent_name_to_id(name)
            if agent_id not in alive_ids:  # 重複を避ける
                alive_ids.append(agent_id)
        return alive_ids

    def name(self) -> str:
        """名前リクエストに対する応答を返す."""
        return self.agent_name

    def initialize(self) -> None:
        """ゲーム開始リクエストに対する初期化処理を行う."""
        # self.infoからエージェントIDを取得（aiwolf-nlp-common対応）
        if (
            self.info
            and hasattr(self.info, "agent")
            and hasattr(self.info, "status_map")
        ):
            agent_name = self.info.agent
            # status_mapから該当するエージェントのIDを探す
            # status_mapのキーがエージェント名で、エージェントIDは1から始まる連番と仮定
            if isinstance(self.info.status_map, dict):
                agent_names = list(self.info.status_map.keys())
                if agent_name in agent_names:
                    # エージェント名のインデックス + 1 をIDとする
                    self.index = str(agent_names.index(agent_name) + 1)
                    print(f"[DEBUG] Agent {agent_name} assigned ID {self.index}")
                else:
                    self.index = "1"  # デフォルト値
                    print(
                        f"[DEBUG] Agent {agent_name} not found in status_map, using default ID 1"
                    )
            else:
                self.index = "1"  # デフォルト値
                print(f"[DEBUG] status_map not dict, using default ID 1")
        else:
            # フォールバック: gameInfoがある場合はそれを使用、なければ"1"をデフォルト
            self.index = str(self.gameInfo.agent) if self.gameInfo else "1"
            print(f"[DEBUG] Using fallback ID {self.index}")

        # デバッグ用マッピング表示
        self.debug_agent_mapping()

        # 役職もself.infoから取得（可能であれば）
        if (
            self.info
            and hasattr(self.info, "role_map")
            and hasattr(self.info, "agent")
            and self.info.agent in self.info.role_map
        ):
            self.role = self.info.role_map[self.info.agent]
        elif (
            self.gameInfo
            and hasattr(self.gameInfo, "roleMap")
            and self.index in self.gameInfo.roleMap
        ):
            self.role = self.gameInfo.roleMap[self.index]
        # else: self.roleはコンストラクタで設定済み

        print(f"[DEBUG] Final role: {self.role}")

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
        self.score_matrix = None
        self.role_predictor = None
        try:
            if self.gameInfo and self.gameSetting:
                self.score_matrix = ScoreMatrix(
                    self.gameInfo, self.gameSetting, self.index, self.role
                )
                self.role_predictor = RolePredictor(
                    self.gameInfo, self.gameSetting, self, self.score_matrix
                )
                print(f"[DEBUG] ScoreMatrix and RolePredictor initialized successfully")
        except Exception as e:
            print(
                f"[Agent Warning] Failed to initialize ScoreMatrix/RolePredictor: {e}"
            )

        try:
            self.talk_generator = TalkGenerator(self.name)
            print(f"[DEBUG] TalkGenerator initialized successfully")
        except Exception as e:
            print(f"[Agent Warning] Failed to initialize TalkGenerator: {e}")
            self.talk_generator = None

    def daily_initialize(self) -> None:
        """昼開始リクエストに対する処理を行う."""
        self.talk_list_head = 0
        self.vote_candidate = None
        self.alive = []
        self.turn = 1

        # aiwolf-nlp-common対応: self.infoから状態を取得
        if self.info and hasattr(self.info, "status_map"):
            # 生存エージェントIDリストを更新
            for agent_name, status in self.info.status_map.items():
                if status == Status.ALIVE:
                    agent_id = self.agent_name_to_id(agent_name)
                    if (
                        agent_id != int(self.index)
                        if self.index and self.index.isdigit()
                        else 1
                    ):
                        self.alive.append(agent_id)

        # 従来のgameInfo対応（互換性維持）
        elif self.gameInfo:
            for agent_num in self.gameInfo.statusMap:
                if (self.gameInfo.statusMap[agent_num] == "ALIVE") and (
                    agent_num != self.index
                ):
                    self.alive.append(int(agent_num))

        # 投票情報の処理
        day = (
            self.info.day if self.info else (self.gameInfo.day if self.gameInfo else 0)
        )
        if day >= 2 and self.score_matrix:
            # vote_listの処理（aiwolf-nlp-common対応）
            if self.info and hasattr(self.info, "vote_list") and self.info.vote_list:
                for vote in self.info.vote_list:
                    if hasattr(vote, "agent") and hasattr(vote, "target"):
                        voter_id = self.agent_name_to_id(vote.agent)
                        target_id = self.agent_name_to_id(vote.target)
                        self.score_matrix.vote(
                            self.gameInfo,
                            self.gameSetting,
                            str(voter_id),
                            str(target_id),
                            day - 1,  # 前日の投票
                        )
            # 従来のgameInfo対応
            elif self.gameInfo and hasattr(self.gameInfo, "voteList"):
                vote_list = self.gameInfo.voteList
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
        """投票候補を選択する（エージェントIDを返す）."""
        # 投票候補（自分以外の生存エージェント）
        alive_ids = self.get_alive_agent_ids()
        my_id = int(self.index) if self.index and self.index.isdigit() else 1

        # 自分以外の生存エージェントID
        vote_candidates = [agent_id for agent_id in alive_ids if agent_id != my_id]

        if not vote_candidates:
            # 候補がない場合は1を返す（エラー回避）
            return 1 if my_id != 1 else 2

        # ---------- 元のシステムの設計思想に基づく投票戦略 ----------
        vote_target = None

        # 1. role_predictorがある場合は人狼として疑わしいエージェントを優先選択
        if self.role_predictor and vote_candidates:
            try:
                # role_predictorは文字列IDを期待する可能性があるため変換
                str_candidates = [str(id) for id in vote_candidates]
                chosen_str = self.role_predictor.chooseMostLikely(
                    Role.WEREWOLF, str_candidates
                )
                if chosen_str and chosen_str.isdigit():
                    vote_target = int(chosen_str)
                else:
                    vote_target = vote_candidates[0]
            except Exception as e:
                print(f"[Agent Warning] role_predictor failed: {e}")
                vote_target = vote_candidates[0]

        # 2. role_predictorがない場合は最初の候補を選択（安定性重視）
        else:
            vote_target = vote_candidates[0]

        # ----- 投票ミスを防ぐ -----
        if vote_target is None or vote_target == my_id:
            # フォールバック: 候補から最初を選択（安定性重視）
            if vote_candidates:
                vote_target = vote_candidates[0]
            else:
                vote_target = 1 if my_id != 1 else 2

        return vote_target

    def talk(self) -> str:
        # aiwolf-nlp-common対応: self.infoから日付を取得
        day: int = (
            self.info.day if self.info else (self.gameInfo.day if self.gameInfo else 0)
        )
        self.vote_candidate = self.choose_vote_candidate()

        if day == 1:
            if self.turn == 1:
                return_text = "よろしくお願いします。"
            elif self.turn == 2:
                return_text = "まずは様子を見ましょう。"
            elif 3 <= self.turn <= 8:
                rnd = random.randint(0, 3)
                if rnd == 0:
                    try:
                        if self.talk_generator:
                            return_text = self.talk_generator.generate_talk(
                                ProtocolMean(
                                    False,
                                    "ESTIMATE",
                                    None,
                                    self.vote_candidate,
                                    "WEREWOLF",
                                )
                            )
                        else:
                            return_text = (
                                f"ESTIMATE Agent{self.vote_candidate} WEREWOLF"
                            )
                    except Exception:
                        return_text = f"ESTIMATE Agent{self.vote_candidate} WEREWOLF"
                elif rnd == 1:
                    try:
                        if self.talk_generator:
                            return_text = self.talk_generator.generate_talk(
                                ProtocolMean(False, "VOTE", None, self.vote_candidate)
                            )
                        else:
                            return_text = f"VOTE Agent{self.vote_candidate}"
                    except Exception:
                        return_text = f"VOTE Agent{self.vote_candidate}"
                elif rnd == 2:
                    try:
                        if self.talk_generator:
                            return_text = self.talk_generator.generate_talk(
                                ProtocolMean(False, "VOTE", "ANY", self.vote_candidate),
                                request=True,
                                request_target="ANY",
                            )
                        else:
                            return_text = (
                                f"REQUEST ANY (VOTE Agent{self.vote_candidate})"
                            )
                    except Exception:
                        return_text = f"REQUEST ANY (VOTE Agent{self.vote_candidate})"
                else:
                    # 一般的な推理発言（安定性重視）
                    return_text = "みなさんの発言を注意深く聞いています。"
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
                    try:
                        if self.talk_generator:
                            return_text = self.talk_generator.generate_talk(
                                ProtocolMean(
                                    False, "CO", self.index, self.index, "POSSESSED"
                                )
                            )
                        else:
                            return_text = f"CO Agent{self.index} POSSESSED"
                    except Exception:
                        return_text = f"CO Agent{self.index} POSSESSED"
            if 1 <= self.turn <= 6:
                rnd = random.randint(0, 3)
                if rnd == 0:
                    try:
                        if self.talk_generator:
                            return_text = self.talk_generator.generate_talk(
                                ProtocolMean(
                                    False,
                                    "ESTIMATE",
                                    None,
                                    self.vote_candidate,
                                    "WEREWOLF",
                                )
                            )
                        else:
                            return_text = (
                                f"ESTIMATE Agent{self.vote_candidate} WEREWOLF"
                            )
                    except Exception:
                        return_text = f"ESTIMATE Agent{self.vote_candidate} WEREWOLF"
                elif rnd == 1:
                    try:
                        if self.talk_generator:
                            return_text = self.talk_generator.generate_talk(
                                ProtocolMean(False, "VOTE", None, self.vote_candidate)
                            )
                        else:
                            return_text = f"VOTE Agent{self.vote_candidate}"
                    except Exception:
                        return_text = f"VOTE Agent{self.vote_candidate}"
                elif rnd == 2:
                    try:
                        if self.talk_generator:
                            return_text = self.talk_generator.generate_talk(
                                ProtocolMean(False, "VOTE", "ANY", self.vote_candidate),
                                request=True,
                                request_target="ANY",
                            )
                        else:
                            return_text = (
                                f"REQUEST ANY (VOTE Agent{self.vote_candidate})"
                            )
                    except Exception:
                        return_text = f"REQUEST ANY (VOTE Agent{self.vote_candidate})"
                    except Exception:
                        return_text = f"REQUEST ANY (VOTE Agent{self.vote_candidate})"
                else:
                    # 2日目以降の推理発言（安定性重視）
                    return_text = "昨日の投票結果を分析しています。"
            else:
                return_text = "Over"
        elif day == 0:
            if self.turn > 1:
                return_text = "Over"
            else:
                return_text = "よろしくお願いします。"
        else:
            return_text = "Over"
        self.turn += 1
        return return_text

    def vote(self) -> str:
        """投票リクエストに対する応答を返す."""
        self.vote_candidate = self.choose_vote_candidate()

        # 投票候補が無効な場合の安全対策
        if (
            self.vote_candidate is None
            or self.vote_candidate == ""
            or self.vote_candidate == "None"
        ):
            # 生存エージェントIDからランダムに選択（自分以外）
            alive_ids = self.get_alive_agent_ids()
            my_id = int(self.index) if self.index and self.index.isdigit() else 1
            alive_ids = [agent_id for agent_id in alive_ids if agent_id != my_id]

            if alive_ids:
                vote_target_id = alive_ids[0]  # 最初の候補を選択
            else:
                # 全員が自分の場合は1を選択（エラー回避）
                vote_target_id = 1
        else:
            # vote_candidateを安全に整数IDに変換
            vote_target_id = self.agent_name_to_id(self.vote_candidate)

        # 自分に投票しないようにする最終チェック
        my_id = int(self.index) if self.index and self.index.isdigit() else 1
        if vote_target_id == my_id:
            alive_ids = self.get_alive_agent_ids()
            other_ids = [agent_id for agent_id in alive_ids if agent_id != my_id]
            if other_ids:
                vote_target_id = other_ids[0]
                print(f"[DEBUG] Avoiding self-vote, changed target to {vote_target_id}")
            else:
                vote_target_id = 1 if my_id != 1 else 2
                print(f"[DEBUG] No other targets, fallback to {vote_target_id}")

        print(f"[DEBUG] Vote: My ID={my_id}, Target ID={vote_target_id}")

        data = {"agentIdx": vote_target_id}
        return json.dumps(data, separators=(",", ":"))

    def daily_finish(self) -> None:
        """昼終了リクエストに対する処理を行う."""

    def divine(self) -> str:
        """占いリクエストに対する応答を返す."""
        alive_ids = self.get_alive_agent_ids()
        my_id = int(self.index) if self.index and self.index.isdigit() else 1
        other_ids = [agent_id for agent_id in alive_ids if agent_id != my_id]

        if other_ids:
            target_id = random.choice(other_ids)  # noqa: S311
        else:
            target_id = 1 if my_id != 1 else 2

        print(f"[DEBUG] Divine: My ID={my_id}, Target ID={target_id}")

        data = {"agentIdx": target_id}
        return json.dumps(data, separators=(",", ":"))

    def guard(self) -> str:
        """護衛リクエストに対する応答を返す."""
        alive_ids = self.get_alive_agent_ids()
        my_id = int(self.index) if self.index and self.index.isdigit() else 1
        other_ids = [agent_id for agent_id in alive_ids if agent_id != my_id]

        if other_ids:
            target_id = random.choice(other_ids)  # noqa: S311
        else:
            target_id = 1 if my_id != 1 else 2

        print(f"[DEBUG] Guard: My ID={my_id}, Target ID={target_id}")

        data = {"agentIdx": target_id}
        return json.dumps(data, separators=(",", ":"))

    def attack(self) -> str:
        """襲撃リクエストに対する応答を返す."""
        alive_ids = self.get_alive_agent_ids()
        my_id = int(self.index) if self.index and self.index.isdigit() else 1
        other_ids = [agent_id for agent_id in alive_ids if agent_id != my_id]

        if other_ids:
            target_id = random.choice(other_ids)  # noqa: S311
        else:
            target_id = 1 if my_id != 1 else 2

        print(f"[DEBUG] Attack: My ID={my_id}, Target ID={target_id}")

        data = {"agentIdx": target_id}
        return json.dumps(data, separators=(",", ":"))

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

    def agent_name_to_id(self, agent_name) -> int:
        """エージェント名をエージェントIDに変換する."""
        if agent_name is None:
            return 1  # デフォルト値

        # 既に整数の場合はそのまま返す
        if isinstance(agent_name, int):
            return agent_name

        # 文字列が数字の場合は変換
        if isinstance(agent_name, str) and agent_name.isdigit():
            return int(agent_name)

        # self.infoからエージェント名→ID変換を試行
        if (
            self.info
            and hasattr(self.info, "status_map")
            and isinstance(self.info.status_map, dict)
        ):
            agent_names = list(self.info.status_map.keys())
            if agent_name in agent_names:
                return agent_names.index(agent_name) + 1

        # gameInfoからの変換も試行
        if (
            self.gameInfo
            and hasattr(self.gameInfo, "statusMap")
            and isinstance(self.gameInfo.statusMap, dict)
        ):
            # gameInfoではキーがエージェントIDの文字列、値がステータス
            for agent_id_str, status in self.gameInfo.statusMap.items():
                # ここではエージェント名とIDの対応表がないため、
                # 推測ベースで変換。実際のマッピングが必要
                pass

        # 名前ベースの推測変換（AIWolfでよく使われるパターン）
        if isinstance(agent_name, str):
            # エージェント名からIDを推測（例: "Agent_01" -> 1）
            if "Agent_" in agent_name:
                try:
                    return int(agent_name.split("_")[-1])
                except (ValueError, IndexError):
                    pass

            # 他の一般的なパターンも追加可能

        # フォールバック: 最初の生存エージェントID（自分以外）
        if (
            self.info
            and hasattr(self.info, "status_map")
            and isinstance(self.info.status_map, dict)
        ):
            my_idx = int(self.index) if self.index and self.index.isdigit() else 1
            for i, (name, status) in enumerate(self.info.status_map.items()):
                agent_id = i + 1
                if status == Status.ALIVE and agent_id != my_idx:
                    return agent_id

        return 1  # 最終フォールバック

    def debug_agent_mapping(self):
        """デバッグ用: エージェント名とIDのマッピングを表示"""
        print(f"[DEBUG] My name: {self.agent_name}, My index: {self.index}")
        if self.info and hasattr(self.info, "status_map"):
            print("[DEBUG] Agent mapping:")
            for i, (name, status) in enumerate(self.info.status_map.items()):
                agent_id = i + 1
                print(f"  {name} -> ID {agent_id} ({status})")
            print(
                f"[DEBUG] Self ID calculation: {self.agent_name_to_id(self.agent_name)}"
            )
        else:
            print("[DEBUG] No status_map available")

    def debug_log(self, message: str) -> None:
        """デバッグ用ログ出力."""
        print(f"[DEBUG {self.agent_name}] {message}")
