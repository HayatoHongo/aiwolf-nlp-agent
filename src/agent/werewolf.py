"""人狼のエージェントクラスを定義するモジュール."""

from __future__ import annotations
import configparser
import json
import random
from collections import deque
from typing import Deque


from aiwolf_nlp_common.packet import Role as PacketRole

from agent.agent import Agent
from cls import Judge, ProtocolMean, Role, Species


class Werewolf(Agent):
    """人狼のエージェントクラス."""

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: PacketRole,  # noqa: ARG002
    ) -> None:
        """人狼のエージェントを初期化する."""
        super().__init__(config, name, game_id, PacketRole.WEREWOLF)

    def initialize(self) -> None:
        super().initialize()
        self.turn = 1
        self.werewolves = []
        self.my_judge_queue = deque()
        # ---------- 5人村15人村共通 ----------
        self.allies = list(self.gameInfo.roleMap.keys())
        self.humans = [a for a in self.gameInfo.statusMap if a not in self.allies]
        allies_no = [a for a in self.allies]
        print("仲間:\t", allies_no)
        self.attack_vote_candidate = None
        self.agent_possessed = None
        self.alive_possessed = False
        self.agent_seer = None
        self.alive_seer = False
        self.found_me = False
        self.whisper_turn = 0
        self.threat = []
        self.not_judged_humans = self.humans.copy()
        self.not_judged_agents = [
            agent for agent in self.gameInfo.statusMap if agent != self.index
        ]
        self.guard_success = False
        self.guard_success_agent = None
        # ---------- 5人村 ----------
        self.fake_role = Role.SEER
        # 初日CO
        self.co_date = 1
        self.kakoi = False
        self.has_co = False
        self.has_PP = False
        self.PP_flag = False

        self.strategies = [False, False, False, False, False]
        self.strategyA = self.strategies[0]  # 戦略A: 占い重視
        self.strategyB = self.strategies[1]  # 戦略B: 霊媒重視
        # self.strategyC = self.strategies[2]  # 戦略C: 狩人重視
        return

    def get_fake_judge(self) -> Judge:
        # 対象候補：生存村人
        judge_candidates: list[str] = [
            agent for agent in self.not_judged_humans if agent in self.alive
        ]
        print("not_judged_humans:", self.not_judged_humans)
        print("judge_candidates:", judge_candidates)
        # 対象：勝率の高いエージェント
        # judge_candidate: Agent = Util.get_strong_agent(judge_candidates)
        result: Species = Species.HUMAN
        # ---------- 5人村 ----------
        # judge_candidate = Util.get_strong_agent(judge_candidates)
        judge_candidate = random.choice(judge_candidates)
        # 基本は黒結果
        result = Species.WEREWOLF
        if judge_candidate is None:
            return None
        return Judge(self.index, self.gameInfo.day, judge_candidate, result)

    def estimate_possessed(self) -> None:
        th: float = 0.01
        # self.agent_possessed = self.role_predictor.chooseMostLikely(Role.POSSESSED, self.get_others(self.gameInfo.agent_list), threshold=0.9)
        self.agent_possessed, P_prob = self.role_predictor.chooseMostLikely(
            Role.POSSESSED,
            [agent for agent in self.gameInfo.statusMap if agent != self.index],
            threshold=th,
            returns_prob=True,
        )
        print(
            "agent_possessed, P_prob:\t",
            self.agent_possessed,
            P_prob,
        )
        self.alive_possessed = False
        if self.agent_possessed is not None:
            self.alive_possessed = self.agent_possessed in self.alive
        # PP：3人以下かつ確定狂人生存
        self.PP_flag = False
        alive_cnt: int = len(self.alive)
        if alive_cnt <= 3 and self.alive_possessed:
            self.PP_flag = True
        if self.alive_possessed and self.talk_turn >= 12:
            print(f"狂人推定:\t{self.agent_possessed}\t 生存:\t{self.alive_possessed}")

    def estimate_seer(self) -> None:
        # self.agent_seer = self.role_predictor.chooseMostLikely(Role.SEER, self.get_others(self.gameInfo.agent_list), threshold=0.9)
        self.agent_seer = None
        self.found_me = False
        for judge in self.divination_reports:
            agent = judge.agent
            target = judge.target
            result = judge.result
            # if agent == self.agent_seer and target == self.index and result == Species.WEREWOLF:
            if target in self.allies and result == Species.WEREWOLF:
                self.agent_seer = agent
                if target == self.index:
                    self.found_me = True
                break
        if self.agent_seer is not None:
            self.alive_seer = self.agent_seer in self.alive
        if self.alive_seer and self.talk_turn >= 12:
            print(f"真占い推定:\t{self.agent_seer}\t 生存:\t{self.alive_seer}")

        # 確定狂人の占い結果

    def get_possessed_divination(self) -> Judge:
        ret_judge: Judge = None
        # breakしないことで、最新の狂人の結果を反映する
        for judge in self.divination_reports:
            if judge.agent == self.agent_possessed:
                ret_judge = judge
        return ret_judge

    def daily_initialize(self) -> None:
        super().daily_initialize()
        self.not_judged_agents = self.alive
        day: int = self.gameInfo.day
        self.attack_vote_candidate = None
        self.new_target = self.role_predictor.chooseMostLikely(
            Role.VILLAGER,
            [agent for agent in self.gameInfo.statusMap if agent in self.alive],
        )
        self.new_result = Species.WEREWOLF
        self.whisper_turn = 0
        self.estimate_possessed()
        self.estimate_seer()
        # 騙り結果
        if day >= 1:
            judge: Judge = self.get_fake_judge()
            if judge is not None:
                self.my_judge_queue.append(judge)
                if judge.target in self.not_judged_agents:
                    self.not_judged_agents.remove(judge.target)
                if judge.target in self.not_judged_humans:
                    self.not_judged_humans.remove(judge.target)
                if judge.result == Species.WEREWOLF:
                    self.werewolves.append(judge.target)
        # 襲撃失敗（護衛成功）
        if (
            self.gameInfo.attackedAgent is not None
            and len(self.gameInfo.lastDeadAgentList) == 0
        ):
            self.guard_success = True
            self.guard_success_agent = self.gameInfo.attackedAgent
            print("襲撃失敗：attacked agent:\t", self.gameInfo.attackedAgent)
        # 襲撃成功（護衛失敗）
        if (
            self.gameInfo.attackedAgent is not None
            and len(self.gameInfo.lastDeadAgentList) == 1
        ):
            self.guard_success = False
            self.guard_success_agent = None
        return

    def whisper(self) -> str:
        """囁きリクエストに対する応答を返す."""
        return super().whisper()

    def talk(self) -> str:
        day: int = self.gameInfo.day
        self.estimate_possessed()
        self.estimate_seer()
        return_text = "SKIP"
        others_seer_co: list[str] = [
            a for a in self.comingout_map if self.comingout_map[a] == Role.SEER
        ]
        others_seer_co_num = len(others_seer_co)
        self.vote_candidate = self.vote()
        # ---------- PP ----------
        if self.PP_flag and not self.has_PP:
            self.has_PP = True
            print(f"狂人推定:\t{self.agent_possessed}\t 生存:\t{self.alive_possessed}")
            return_text = self.talk_generator.generate_talk(
                ProtocolMean(False, "CO", self.index, "WEREWOLF")
            )
        # ---------- 5人村 ----------
        if day == 0:
            if self.turn == 1:
                return_text = "よろしくお願いします。"
            elif self.turn >= 2:
                return_text = "Over"
        elif day == 1:
            # 村人と揃える
            if self.turn == 1:
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(
                        False, "CO", "ANY", None, "ANY"
                    ),  # Noneが１つ余計だったことでprotcolmeanでfirst_translateの処理が入りバグっていた。
                    request=True,
                    request_target="ANY",
                )
            # ----- CO -----
            # 1: 真占いの黒結果
            if not self.has_co and self.found_me:
                print("占いCO：見つかった")
                self.has_co = True
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, "SEER")
                )
            # 2: 占い2COかつ狂人あり
            if not self.has_co and (others_seer_co_num >= 2 and self.alive_possessed):
                print("占いCO：2COかつ狂人あり")
                self.has_co = True
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, "SEER")
                )
            # 3: 3ターン目以降かつ占い1CO
            if not self.has_co and (self.turn >= 3 and others_seer_co_num == 1):
                print("占いCO：3ターン目以降かつ占い1CO")
                self.has_co = True
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, "SEER")
                )
            # ----- 結果報告 -----
            if self.has_co and self.my_judge_queue:
                judge: Judge = self.my_judge_queue.popleft()
                # 基本は get_fake_judge を利用する
                # 黒結果
                # 対象：確定占い→狂人に合わせる→占いっぽいエージェント
                if self.alive_seer:
                    self.new_target = self.agent_seer
                elif self.alive_possessed:
                    self.new_target = self.vote_candidate
                else:
                    self.new_target = self.role_predictor.chooseMostLikely(
                        Role.SEER,
                        [
                            agent
                            for agent in self.gameInfo.statusMap
                            if agent in self.alive
                        ],
                    )
                if self.new_target is None:
                    self.new_target = judge.target
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(
                        False, "DIVINED", None, self.new_target, Species.WEREWOLF
                    )
                )
        elif day == 2:
            # PP盤面でない場合、適当に白結果を出して、占いっぽく見せる
            if self.turn == 1:
                # 勝率の低いエージェントに白結果を出して、占いっぽく見せる
                alive_others: list[str] = [
                    agent for agent in self.gameInfo.statusMap if agent in self.alive
                ]
                # weak_agent: Agent = Util.get_weak_agent(alive_others)
                # if weak_agent in alive_others:
                #     alive_others.remove(weak_agent)
                self.new_target = self.role_predictor.chooseLeastLikely(
                    Role.POSSESSED, alive_others
                )
                self.new_result = Species.HUMAN
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "DIVINED", None, self.new_target, Species.HUMAN)
                )
            # ----- VOTE and REQUEST -----
            if 2 <= self.turn <= 9:
                if self.PP_flag:
                    self.vote_candidate = self.role_predictor.chooseLeastLikely(
                        Role.POSSESSED,
                        [
                            agent
                            for agent in self.gameInfo.statusMap
                            if agent in self.alive
                        ],
                    )
                if self.turn % 2 == 0:
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
            return_text = "SKIP"
        self.turn += 1
        return return_text

    def vote(self) -> str:
        # ----------  同数投票の処理 ----------
        latest_vote_list = self.gameInfo.latestVoteList
        tmp_vote_candidate = self.vote_candidate
        if latest_vote_list:
            # print("latest_vote_list:\t", self.vote_to_dict(latest_vote_list))
            # 3人で1:1:1に割れた時、周りが投票を変更しないと仮定すると、絶対に投票を変更するべき
            if len(latest_vote_list) == 3:
                print(
                    "------------------------------ 3人で1:1:1 ------------------------------"
                )
                alive_others: list[str] = [
                    agent for agent in self.gameInfo.statusMap if agent in self.alive
                ]
                if self.vote_candidate in alive_others:
                    alive_others.remove(self.vote_candidate)
                self.vote_candidate = self.role_predictor.chooseMostLikely(
                    Role.WEREWOLF, alive_others
                )
            else:
                # self.vote_candidate = self.changeVote(latest_vote_list, Role.WEREWOLF, mostlikely=False)
                self.vote_candidate = self.changeVote(
                    latest_vote_list, Role.POSSESSED, mostlikely=False
                )
            # 人狼仲間に投票されるのを防ぐ
            if self.vote_candidate in self.allies:
                self.vote_candidate = tmp_vote_candidate
            return self.vote_candidate if self.vote_candidate != None else self.index

        self.estimate_possessed()
        self.estimate_seer()
        vote_candidates: list[str] = [
            agent for agent in self.humans if agent in self.alive
        ]
        # self.vote_candidate = self.role_predictor.chooseMostLikely(Role.VILLAGER, vote_candidates)
        # others_seer_co: list[str] = [a for a in self.comingout_map if self.comingout_map[a] == Role.SEER]
        # 確定狂人がいたら除外
        if self.agent_possessed in vote_candidates:
            vote_candidates.remove(self.agent_possessed)
        # ---------- 5人村15人村共通 ----------
        if self.PP_flag:
            self.vote_candidate = self.role_predictor.chooseMostLikely(
                Role.VILLAGER, vote_candidates
            )
            return (
                self.vote_candidate if self.vote_candidate is not None else self.index
            )
        # ---------- 5人村 ----------
        # 確定狂人がいる場合→狂人の結果に合わせる
        if self.alive_possessed:
            print("alive_possessed")
            possessed_judge: Judge | None = self.get_possessed_divination()
            target = possessed_judge.target
            result = possessed_judge.result
            # 自分への白結果の場合：自分の黒先→処刑されそうなエージェント
            if result == Species.HUMAN:
                if self.new_target is not None:
                    print("自分の黒先")
                    self.vote_candidate = self.new_target
                else:
                    print("処刑されそうなエージェント2")
                    # self.vote_candidate = self.chooseMostlikelyExecuted2(include_list=vote_candidates, exclude_list=[self.agent_possessed])
                    candidates = vote_candidates.copy()
                    candidates.remove(self.agent_possessed)
                    self.vote_candidate = self.role_predictor.chooseLeastLikely(
                        Role.WEREWOLF, vote_candidates
                    )
            # 自分以外への黒結果の場合：狂人の黒先
            elif result == Species.WEREWOLF:
                if target in self.alive:
                    print("狂人の黒先")
                    self.vote_candidate = target
                else:
                    print("処刑されそうなエージェント2")
                    # self.vote_candidate = self.chooseMostlikelyExecuted2(include_list=vote_candidates, exclude_list=[self.agent_possessed])
                    candidates = vote_candidates.copy()
                    candidates.remove(self.agent_possessed)
                    self.vote_candidate = self.role_predictor.chooseLeastLikely(
                        Role.WEREWOLF, vote_candidates
                    )
        else:
            # 自分の黒先→最も処刑されそうなエージェント（自分が死ぬよりはマシ）
            if self.new_target != None:
                self.vote_candidate = self.new_target
            else:
                print("処刑されそうなエージェント2")
                self.vote_candidate = self.role_predictor.chooseLeastLikely(
                    Role.WEREWOLF, vote_candidates
                )
                # self.vote_candidate = self.chooseMostlikelyExecuted2(include_list=vote_candidates)
        vote_target = (
            self.vote_candidate if self.vote_candidate is not None else self.index
        )

        return vote_target

    # 襲撃スコア(=スコア + coef*勝率)の高いエージェント
    def get_attack_agent(self, agent_list: list[str], coef: float = 3.0) -> str:
        p = self.role_predictor.prob_all
        mx_score = 0
        ret_agent = None
        for agent in agent_list:
            score = 2 * p[agent][Role.SEER]
            # score += 3 * Util.win_rate[agent]
            if score > mx_score:
                mx_score = score
                ret_agent = agent
        print("襲撃スコア:\t:", agent_list, ret_agent, mx_score)
        return ret_agent

    def attack(self) -> str:
        self.estimate_possessed()
        self.estimate_seer()
        # alive_werewolf_cnt = len(self.get_alive(self.allies))
        # ----- 襲撃対象 -----
        attack_vote_candidates: list[str] = [
            agent for agent in self.humans if agent in self.alive
        ]
        # 確定狂人は除外
        if self.agent_possessed in attack_vote_candidates:
            attack_vote_candidates.remove(self.agent_possessed)
        # 護衛成功したエージェントを除外
        if self.guard_success_agent in attack_vote_candidates:
            attack_vote_candidates.remove(self.guard_success_agent)
        # 重要：これ以降、襲撃対象に、処刑者・確定狂人・護衛成功者は除きたいから、v.agent in attack_vote_candidates で確認する
        latest_vote_list = self.gameInfo.latestVoteList
        # print("----- attack -----")
        # print("latest_vote_list:\t", self.vote_to_dict(latest_vote_list))
        # print("latest_vote_cnt:\t", self.vote_cnt(latest_vote_list))
        # 脅威：人狼に投票したエージェント
        try:
            print(f"[DEBUG] latest_vote_list type: {type(latest_vote_list)}")
            print(f"[DEBUG] latest_vote_list: {latest_vote_list}")
            if latest_vote_list:
                print(f"[DEBUG] first vote element type: {type(latest_vote_list[0])}")
                print(f"[DEBUG] first vote element: {latest_vote_list[0]}")
            self.threat = [
                v.agent
                for v in latest_vote_list
                if hasattr(v, "target")
                and hasattr(v, "agent")
                and v.target in self.allies
                and v.agent in attack_vote_candidates
            ]
        except Exception as e:
            print(f"[ERROR] threat calculation error: {e}")
            print(f"[ERROR] error type: {type(e)}")
            import traceback

            traceback.print_exc()
            self.threat = []
        # print("脅威:\t", self.self.threat)
        # print("alive_comingout_map:\t", self.alive_comingout_map_str)
        # ---------- 5人村 ----------
        # 注意：5人村ではwhisperが呼ばれないので、attack関数で襲撃対象を決める
        # 襲撃候補：占いCOしていないエージェント
        # if a in attack_vote_candidates でaliveは保証されている
        others_seer_co: list[str] = [
            a
            for a in self.comingout_map
            if a in attack_vote_candidates and self.comingout_map[a] == Role.SEER
        ]
        for seer_candidate in others_seer_co:
            if seer_candidate in attack_vote_candidates:
                attack_vote_candidates.remove(seer_candidate)
        if not attack_vote_candidates:
            attack_vote_candidates = [
                agent for agent in self.humans if agent in self.alive
            ]
        # 脅威噛み
        # 対象：最も村人っぽいエージェント＋勝率を考慮する
        try:
            print(f"[DEBUG] self.threat: {self.threat}")
            print(f"[DEBUG] attack_vote_candidates: {attack_vote_candidates}")

            if self.threat:
                print(f"[DEBUG] Calling chooseStrongLikely with threat list")
                self.attack_vote_candidate = self.role_predictor.chooseStrongLikely(
                    Role.VILLAGER, self.threat, coef=3.0
                )
                print(
                    f"[DEBUG] chooseStrongLikely (threat) returned: {self.attack_vote_candidate}"
                )
            else:
                print(f"[DEBUG] Calling chooseStrongLikely with attack_vote_candidates")
                self.attack_vote_candidate = self.role_predictor.chooseStrongLikely(
                    Role.VILLAGER, attack_vote_candidates, coef=3.0
                )
                print(
                    f"[DEBUG] chooseStrongLikely returned: {self.attack_vote_candidate}"
                )

            print(
                f"[DEBUG] attack_vote_candidate type: {type(self.attack_vote_candidate)}"
            )

            # 狂人っぽい場合、襲撃対象を変更する
            print(
                f"[DEBUG] Calling getMostLikelyRole with: {self.attack_vote_candidate}"
            )
            most_likely_role = self.role_predictor.getMostLikelyRole(
                self.attack_vote_candidate
            )
            print(
                f"[DEBUG] getMostLikelyRole returned: {most_likely_role}, type: {type(most_likely_role)}"
            )

            if most_likely_role == Role.POSSESSED:
                print(f"[DEBUG] Calling chooseLeastLikely for POSSESSED role")
                self.attack_vote_candidate = self.role_predictor.chooseLeastLikely(
                    Role.POSSESSED, attack_vote_candidates
                )
                print(
                    f"[DEBUG] chooseLeastLikely returned: {self.attack_vote_candidate}"
                )

        except Exception as e:
            print(f"[ERROR] role_predictor method call error: {e}")
            print(f"[ERROR] error type: {type(e)}")
            import traceback

            traceback.print_exc()
            # フォールバック値を設定
            self.attack_vote_candidate = (
                attack_vote_candidates[0] if attack_vote_candidates else self.index
            )

        print(f"襲撃対象:\t{self.attack_vote_candidate}")
        attack_target = (
            self.attack_vote_candidate
            if self.attack_vote_candidate is not None
            else self.index
        )
        return attack_target
