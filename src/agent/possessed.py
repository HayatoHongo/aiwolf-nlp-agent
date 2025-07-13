"""狂人のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent
import configparser
import json
from collections import deque
from typing import Deque

from cls import Judge, ProtocolMean, Role, Species


class Possessed(Agent):
    """狂人のエージェントクラス."""

    """ddhb possessed agent."""
    fake_role: Role  # 騙る役職
    """Fake role."""
    co_date: int  # COする日にち
    """Scheduled comingout date."""
    has_co: bool  # COしたか
    """Whether or not comingout has done."""
    my_judge_queue: Deque[Judge]  # 自身の（占い or 霊媒）結果キュー
    """Queue of fake judgements."""
    not_judged_agents: list[str]  # 占っていないエージェント
    """Agents that have not been judged."""
    num_wolves: int  # 人狼数
    """The number of werewolves."""
    werewolves: list[str]  # 人狼結果のエージェント
    """Fake werewolves."""
    PP_flag: bool  # PPフラグ
    has_PP: bool  # PP宣言したか
    # ----- 騙り共通 -----
    has_report: bool  # 結果を報告したか
    black_count: int  # 黒判定した数
    # ----- 占い騙り -----
    new_target: str  # 偽の占い対象
    new_result: Species  # 偽の占い結果
    agent_werewolf: str  # 人狼っぽいエージェント

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        """狂人のエージェントを初期化する."""
        super().__init__(config, name, game_id, Role.POSSESSED)
        self.fake_role = Role.SEER
        self.co_date = 0
        self.has_co = False
        self.my_judge_queue = deque()
        self.not_judged_agents = []
        self.num_wolves = 0
        self.werewolves = []
        self.PP_flag = False
        self.has_PP = False
        self.has_report = False
        self.black_count = 0  # 霊媒師が黒判定した数
        self.new_target = None
        self.new_result = Species.UNC
        self.agent_werewolf = None
        self.strategies = []

    def initialize(self) -> None:
        super().initialize()
        # ---------- 5人村15人村共通 ----------
        self.co_date = 1
        self.has_co = False
        self.my_judge_queue.clear()
        self.not_judged_agents = [
            agent for agent in self.gameInfo.statusMap if agent != self.index
        ]
        self.num_wolves = self.gameSetting.roleNumMap.get(Role.WEREWOLF, 0)
        self.werewolves.clear()
        self.PP_flag = False
        self.has_PP = False
        self.has_report = False
        self.black_count = 0
        self.new_target = None
        self.new_result = Species.WEREWOLF
        self.agent_werewolf = None

        # 戦略を検証するためのフラグ
        self.strategies = [False, True, True]
        self.strategyA = self.strategies[0]  # 戦略A：一日で何回も占い結果を言う
        self.strategyB = self.strategies[1]  # 戦略B：100%で占いCO
        self.strategyC = self.strategies[2]  # 戦略C：15人村：COしてから占い結果

        self.fake_role = Role.SEER
        return

    # スコアマトリックスから人狼を推測する
    def estimate_werewolf(self) -> None:
        th: float = 0.7
        # game: int = Util.game_count
        # # ---------- 5人村 ----------
        # if self.N == 5:
        #     if game < 10:
        #         th = 0.9
        #     elif game < 50:
        #         th = 0.7
        #     else:
        #         th = 0.4
        # # ---------- 15人村 ----------
        # elif self.N == 15:
        #     th = 0.4
        th = 0.4
        self.agent_werewolf, W_prob = self.role_predictor.chooseMostLikely(
            Role.WEREWOLF, self.alive, threshold=th, returns_prob=True
        )
        print("agent_werewolf, W_prob:\t", self.agent_werewolf, W_prob)

    def daily_initialize(self) -> None:
        super().daily_initialize()

        day: int = self.gameInfo.day
        if day >= 2:
            vote_list = self.gameInfo.voteList
            print("----- day_start -----")
            print("vote_list:\t", [(v.agent, v.target, v.day) for v in vote_list])
            # print("vote_cnt:\t", self.vote_cnt(vote_list))

        self.new_target = self.role_predictor.chooseMostLikely(
            Role.VILLAGER, self.alive
        )
        self.new_result = Species.WEREWOLF
        # 常に報告内容あり
        self.has_report = False
        # PP：3人以下
        alive_cnt: int = len(self.alive)
        if alive_cnt <= 3:
            self.PP_flag = True
        self.not_judged_agents = self.alive
        return

    def talk(self) -> str:
        """狂人のtalkメソッド."""
        #return self.talk_protocol()
        return self.talk_llmbase()

    def talk_protocol(self) -> str:
        day: int = self.gameInfo.day
        turn: int = self.turn
        self.estimate_werewolf()
        alive_others: list[str] = self.alive
        # if self.is_alive(a)でaliveを保証している
        others_seer_co = [
            a
            for a in self.comingout_map
            if a in self.alive and self.comingout_map[a] == Role.SEER
        ]
        self.vote_candidate = self.vote()
        # ---------- PP ----------
        if self.PP_flag and not self.has_PP:
            print("PP: Possessed")
            self.has_PP = True
            # return Content(ComingoutContentBuilder(self.me, Role.POSSESSED))
            return_text = self.talk_generator.generate_talk(
                ProtocolMean(False, "CO", self.index, None,"WEREWOLF")
            )
        # ---------- 5人村 ----------
        if day == 0:
            if turn == 1:
                return_text = "よろしくお願いします。"
            elif turn >= 2:
                return_text = "Over"
        elif day == 1:
            # ----- CO -----
            if turn == 1:
                if not self.has_co:
                    self.has_co = True
                    # return_text = self.talk_generator.generate_talk(
                    #     ProtocolMean(False, "CO", self.index, None, "SEER")
                    # )
                    return_text = "私は占い師です。"
            # ----- 結果報告 -----
            elif turn == 2:
                if self.has_co and not self.has_report:
                    self.has_report = True
                    self.new_result = Species.WEREWOLF
                    # 候補の優先順位：対抗の占いっぽいエージェント→人狼っぽくないエージェント
                    if others_seer_co:
                        self.new_target = self.role_predictor.chooseMostLikely(
                            Role.SEER, others_seer_co
                        )
                    else:
                        self.new_target = self.role_predictor.chooseLeastLikely(
                            Role.WEREWOLF, alive_others
                        )
                    # return_text = self.talk_generator.generate_talk(
                    #     ProtocolMean(
                    #         False, "DIVINED", None, self.new_target, self.new_result
                    #     )
                    # )
                    return_text = f"今日の占い結果は{self.new_target}は人狼です。"
            elif 2 <= turn <= 9:
                if turn % 2 == 0:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.new_target),
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
                # ----- PP -----
                # 上のPPでreturnされているから、特に必要ない
                # return_text = self.talk_generator.generate_talk(
                #     ProtocolMean(False, "CO", self.index, None, "WEREWOLF")
                # )
                return_text = "PP宣言します。私は人狼です。"
            # ----- VOTE and REQUEST -----
            elif 2 <= turn <= 9:
                # 候補：人狼っぽくないエージェント
                self.new_target = self.role_predictor.chooseLeastLikely(
                    Role.WEREWOLF, alive_others
                )
                if turn % 2 == 0:
                    # return_text = self.talk_generator.generate_talk(
                    #     ProtocolMean(False, "VOTE", None, self.new_target),
                    #     request=True,
                    #     request_target="ANY",
                    # )
                    return_text = f"投票先は{self.new_target}です。"
                else:
                    # return_text = self.talk_generator.generate_talk(
                    #     ProtocolMean(False, "VOTE", None, self.new_target)
                    # )
                    return_text = f"皆さん、投票先は{self.new_target}にすべきです。"
            else:
                return_text = "SKIP"
        else:
            return_text = "SKIP"
        self.turn += 1
        return return_text

    def vote(self) -> str:
        return self.vote_protocol()
        # return self.vote_llmbase()

    def vote_protocol(self) -> str:
        self.estimate_werewolf()
        vote_candidates: list[str] = self.alive.copy()
        # 確定人狼がいたら除外
        if self.agent_werewolf:
            if self.agent_werewolf in vote_candidates:
                vote_candidates.remove(self.agent_werewolf)
        # ----------  同数投票の処理 ----------
        latest_vote_list = self.gameInfo.latestVoteList
        if latest_vote_list:
            self.vote_candidate = self.changeVote(
                latest_vote_list, Role.WEREWOLF, mostlikely=False
            )
            # 最多投票者が自分Aともう1人Bの場合、Bが選ばれている
            # Bが人狼っぽいなら、投票を人狼っぽくないエージェントに変更する
            # これにより、自分の投票が原因で人狼が処刑されることを防ぐ
            if (
                self.role_predictor.getMostLikelyRole(self.vote_candidate)
                == Role.WEREWOLF
            ):
                self.vote_candidate = self.role_predictor.chooseLeastLikely(
                    Role.WEREWOLF, vote_candidates
                )
            return (
                self.vote_candidate if self.vote_candidate is not None else self.index
            )
        # ---------- PP ----------
        if self.PP_flag:
            # 投票対象：人狼っぽくないエージェント
            self.vote_candidate = self.role_predictor.chooseLeastLikely(
                Role.WEREWOLF, vote_candidates
            )
            return (
                self.vote_candidate if self.vote_candidate is not None else self.index
            )
        # ---------- 5人村 ----------
        # 人狼を判別できている場合：人狼の投票先に合わせる
        if self.agent_werewolf is not None:
            self.vote_candidate = self.will_vote_reports.get(self.agent_werewolf, None)
            print("投票先\t", self.will_vote_reports)
            print(
                f"人狼っぽい:{self.agent_werewolf}\t投票を合わせる:{self.vote_candidate}"
            )
            # 投票対象が自分 or 投票対象が死んでいる：処刑されそうなエージェントに投票
            if (
                self.vote_candidate == self.index
                or self.vote_candidate is None
                or self.vote_candidate not in self.alive
            ):
                # self.vote_candidate = self.chooseMostlikelyExecuted2(include_list=vote_candidates)
                self.vote_candidate = self.role_predictor.chooseLeastLikely(
                    Role.WEREWOLF, vote_candidates
                )
                print("処刑されそうなエージェント2:", self.vote_candidate)
        # 人狼を判別できていない or 投票対象が自分 or 投票対象が死んでいる：人狼っぽくないエージェントに投票
        elif self.agent_werewolf is None or self.vote_candidate is None:
            # print("vote_candidates:\t", self.agent_to_index(vote_candidates))
            self.vote_candidate = self.role_predictor.chooseLeastLikely(
                Role.WEREWOLF, vote_candidates
            )

        # ----- 投票ミスを防ぐ -----
        if self.vote_candidate is None or self.vote_candidate == self.index:
            print("vote_candidates: AGENT_NONE or self.index")
            self.vote_candidate = self.role_predictor.chooseLeastLikely(
                Role.WEREWOLF, vote_candidates
            )

        vote_target = (
            self.vote_candidate if self.vote_candidate is not None else self.index
        )
        return vote_target
