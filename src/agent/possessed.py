"""狂人のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent
from collections import defaultdict, deque
from typing import DefaultDict, Deque
from cls import Judge, ProtocolMean, Role, Species
from lib.AIWolf import RolePredictor, ScoreMatrix
from lib import TalkGenerator


class Possessed(Agent):
    """狂人のエージェントクラス."""

    # --- 独自属性定義 ---
    fake_role: Role  # 騙る役職
    co_date: int  # COする日にち
    has_co: bool  # COしたか
    my_judge_queue: Deque[Judge]  # 自身の（占い or 霊媒）結果キュー
    not_judged_agents: list[str]  # 占っていないエージェント
    num_wolves: int  # 人狼数
    werewolves: list[str]  # 人狼結果のエージェント
    PP_flag: bool  # PPフラグ
    has_PP: bool  # PP宣言したか
    has_report: bool  # 結果を報告したか
    black_count: int  # 黒判定した数
    new_target: str  # 偽の占い対象
    new_result: Species  # 偽の占い結果
    agent_werewolf: str  # 人狼っぽいエージェント
    strategies: list[bool]  # 戦略フラグ

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
        ssh_host=None,
        ssh_user=None,
        ssh_key=None,
    ) -> None:
        """狂人のエージェントを初期化する."""
        super().__init__(
            config, name, game_id, Role.POSSESSED, ssh_host, ssh_user, ssh_key
        )
        # --- Possessed独自属性の初期化 ---
        self.fake_role = Role.SEER
        self.co_date = 1
        self.has_co = False
        self.my_judge_queue = deque()
        self.not_judged_agents = []
        self.num_wolves = 0
        self.werewolves = []
        self.PP_flag = False
        self.has_PP = False
        self.has_report = False
        self.black_count = 0
        self.new_target = None
        self.new_result = Species.UNC
        self.agent_werewolf = None
        self.strategies = [False, True, True]
        self.strategyA = self.strategies[0]  # 戦略A：一日で何回も占い結果を言う
        self.strategyB = self.strategies[1]  # 戦略B：100%で占いCO
        self.strategyC = self.strategies[2]  # 戦略C：15人村：COしてから占い結果

    def initialize(self) -> None:
        super().initialize()
        self.co_date = 1
        self.has_co = False
        self.my_judge_queue.clear()

        # self.indexが有効であることを確認してから使用
        if self.index and self.index.isdigit():
            self.not_judged_agents = [
                agent
                for agent in (self.gameInfo.statusMap if self.gameInfo else {})
                if agent != int(self.index)
            ]
        else:
            self.not_judged_agents = (
                list(self.gameInfo.statusMap.keys()) if self.gameInfo else []
            )

        self.num_wolves = (
            self.gameSetting.roleNumMap.get(Role.WEREWOLF, 0) if self.gameSetting else 0
        )
        self.werewolves.clear()
        self.PP_flag = False
        self.has_PP = False
        self.has_report = False
        self.black_count = 0
        self.new_target = None
        self.new_result = Species.WEREWOLF
        self.agent_werewolf = None
        self.strategies = [False, True, True]
        self.strategyA = self.strategies[0]
        self.strategyB = self.strategies[1]
        self.strategyC = self.strategies[2]
        self.fake_role = Role.SEER

    def estimate_werewolf(self) -> None:
        th = 0.4
        if self.role_predictor and hasattr(self, "alive"):
            res = self.role_predictor.chooseMostLikely(
                Role.WEREWOLF, self.alive, threshold=th, returns_prob=True
            )
            if isinstance(res, tuple):
                self.agent_werewolf, _ = res
            else:
                self.agent_werewolf = res
        else:
            self.agent_werewolf = None

    def daily_initialize(self) -> None:
        super().daily_initialize()
        day: int = self.gameInfo.day if self.gameInfo else 0
        if day >= 2 and self.gameInfo:
            vote_list = self.gameInfo.voteList
            # print("----- day_start -----")
            # print("vote_list:", vote_list)
        self.new_target = (
            self.role_predictor.chooseMostLikely(Role.VILLAGER, self.alive)
            if self.role_predictor and hasattr(self, "alive")
            else None
        )
        self.new_result = Species.WEREWOLF
        self.has_report = False
        alive_cnt = len(self.alive) if hasattr(self, "alive") else 0
        if alive_cnt <= 3:
            self.PP_flag = True
        self.not_judged_agents = self.alive.copy() if hasattr(self, "alive") else []

    def talk(self) -> str:
        day: int = self.gameInfo.day if self.gameInfo else 0
        turn: int = self.turn
        self.estimate_werewolf()
        alive_others = self.alive.copy() if hasattr(self, "alive") else []
        others_seer_co = [
            a
            for a in self.comingout_map
            if a in alive_others and self.comingout_map[a] == Role.SEER
        ]
        self.vote_candidate = self.vote() if hasattr(self, "vote") else None
        if self.PP_flag and not self.has_PP:
            self.has_PP = True
            return_text = self.talk_generator.generate_talk(
                ProtocolMean(False, "CO", self.index, "WEREWOLF")
            )
        elif day == 0:
            if turn == 1:
                return_text = "よろしくお願いします。"
            else:
                return_text = "Over"
        elif day == 1:
            if turn == 1 and not self.has_co:
                self.has_co = True
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, None, "SEER")
                )
            elif turn == 2 and self.has_co and not self.has_report:
                self.has_report = True
                self.new_result = Species.WEREWOLF
                if others_seer_co:
                    self.new_target = (
                        self.role_predictor.chooseMostLikely(Role.SEER, others_seer_co)
                        if self.role_predictor
                        else None
                    )
                else:
                    self.new_target = (
                        self.role_predictor.chooseLeastLikely(
                            Role.WEREWOLF, alive_others
                        )
                        if self.role_predictor
                        else None
                    )
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(
                        False, "DIVINED", None, self.new_target, self.new_result
                    )
                )
            elif 2 <= turn <= 9:
                if turn % 2 == 0:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", "ANY", self.new_target),
                        request=True,
                        request_target="ANY",
                    )
                else:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.new_target)
                    )
            else:
                return_text = "SKIP"
        elif day >= 2:
            if turn == 1:
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, None, "WEREWOLF")
                )
            elif 2 <= turn <= 9:
                self.new_target = (
                    self.role_predictor.chooseLeastLikely(Role.WEREWOLF, alive_others)
                    if self.role_predictor
                    else None
                )
                if turn % 2 == 0:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", "ANY", self.new_target),
                        request=True,
                        request_target="ANY",
                    )
                else:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.new_target)
                    )
            else:
                return_text = "SKIP"
        else:
            return_text = "SKIP"
        self.turn += 1
        return return_text

    def vote(self) -> str:
        self.estimate_werewolf()
        vote_candidates = self.alive.copy() if hasattr(self, "alive") else []
        if self.agent_werewolf and self.agent_werewolf in vote_candidates:
            vote_candidates.remove(self.agent_werewolf)
        latest_vote_list = (
            self.gameInfo.latestVoteList
            if self.gameInfo and hasattr(self.gameInfo, "latestVoteList")
            else None
        )
        if latest_vote_list:
            self.vote_candidate = (
                self.role_predictor.changeVote(
                    latest_vote_list, Role.WEREWOLF, mostlikely=False
                )
                if self.role_predictor
                else None
            )
            if (
                self.role_predictor
                and self.role_predictor.getMostLikelyRole(self.vote_candidate)
                == Role.WEREWOLF
            ):
                self.vote_candidate = self.role_predictor.chooseLeastLikely(
                    Role.WEREWOLF, vote_candidates
                )
            return (
                str(self.vote_candidate)
                if self.vote_candidate is not None
                else str(self.index)
            )
        if self.PP_flag:
            self.vote_candidate = (
                self.role_predictor.chooseLeastLikely(Role.WEREWOLF, vote_candidates)
                if self.role_predictor
                else None
            )
            return (
                str(self.vote_candidate)
                if self.vote_candidate is not None
                else str(self.index)
            )
        if self.agent_werewolf is not None:
            self.vote_candidate = self.will_vote_reports.get(self.agent_werewolf, None)
            if (
                self.vote_candidate == self.index
                or self.vote_candidate is None
                or self.vote_candidate not in vote_candidates
            ):
                self.vote_candidate = (
                    self.role_predictor.chooseLeastLikely(
                        Role.WEREWOLF, vote_candidates
                    )
                    if self.role_predictor
                    else None
                )
        elif self.agent_werewolf is None or self.vote_candidate is None:
            self.vote_candidate = (
                self.role_predictor.chooseLeastLikely(Role.WEREWOLF, vote_candidates)
                if self.role_predictor
                else None
            )
        if self.vote_candidate is None or self.vote_candidate == self.index:
            self.vote_candidate = (
                self.role_predictor.chooseLeastLikely(Role.WEREWOLF, vote_candidates)
                if self.role_predictor
                else None
            )
        vote_target = (
            self.vote_candidate if self.vote_candidate is not None else self.index
        )
        # エージェント名を整数IDに安全に変換
        vote_target_id = self.agent_name_to_id(vote_target)
        import json

        data = {"agentIdx": vote_target_id}
        return json.dumps(data, separators=(",", ":"))

    def parse_info(self, receive: str) -> None:
        """サーバーからの情報をパースし履歴に追加する."""
        return super().parse_info(receive)

    def get_info(self):
        """受信履歴から最新情報を取得し、ゲーム情報・設定・履歴を更新する."""
        return super().get_info()

    def daily_finish(self) -> None:
        """昼終了リクエストに対する処理."""
        return super().daily_finish()

    def whisper(self) -> str:
        """囁きリクエストに対する応答."""
        return super().whisper()

    def action(self) -> str:
        """リクエストの種類に応じたアクションを実行する."""
        return super().action()
