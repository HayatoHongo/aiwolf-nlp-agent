"""人狼のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role, Request

from agent.agent import Agent
from collections import deque
import random
from cls import Judge, ProtocolMean, Role, Species
from lib.AIWolf import RolePredictor, ScoreMatrix
from lib import TalkGenerator


class Werewolf(Agent):
    """人狼のエージェントクラス."""

    allies: list[str]
    humans: list[str]
    attack_vote_candidate: str
    my_judge_queue: deque
    agent_possessed: str
    alive_possessed: bool
    agent_seer: str
    alive_seer: bool
    found_me: bool
    whisper_turn: int
    threat: list[str]
    kakoi: bool
    not_judged_humans: list[str]
    not_judged_agents: list[str]
    werewolves: list[str]
    new_target: str
    new_result: Species
    guard_success: bool
    guard_success_agent: str
    PP_flag: bool
    has_PP: bool
    co_date: int
    has_co: bool
    strategies: list[bool]

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
        super().__init__(
            config, name, game_id, Role.WEREWOLF, ssh_host, ssh_user, ssh_key
        )
        self.my_judge_queue = deque()
        self.allies = []
        self.humans = []
        self.attack_vote_candidate = None
        self.agent_possessed = None
        self.alive_possessed = False
        self.agent_seer = None
        self.alive_seer = False
        self.found_me = False
        self.whisper_turn = 0
        self.threat = []
        self.kakoi = False
        self.not_judged_humans = []
        self.not_judged_agents = []
        self.werewolves = []
        self.new_target = None
        self.new_result = Species.UNC
        self.guard_success = False
        self.guard_success_agent = None
        self.PP_flag = False
        self.has_PP = False
        self.co_date = 1
        self.has_co = False
        self.strategies = [False, False, False, False, False]
        self.strategyA = self.strategies[0]
        self.strategyB = self.strategies[1]

    def parse_info(self, receive: str) -> None:
        return super().parse_info(receive)

    def get_info(self):
        return super().get_info()

    def initialize(self) -> None:
        super().initialize()
        self.werewolves.clear()
        self.my_judge_queue.clear()
        self.allies = list(self.gameInfo.roleMap.keys()) if self.gameInfo else []

        # 人間リストを安全に作成
        if self.gameInfo and hasattr(self.gameInfo, "statusMap"):
            self.humans = [a for a in self.gameInfo.statusMap if a not in self.allies]
        else:
            self.humans = []

        self.attack_vote_candidate = None
        self.agent_possessed = None
        self.alive_possessed = False
        self.agent_seer = None
        self.alive_seer = False
        self.found_me = False
        self.whisper_turn = 0
        self.threat = []
        self.not_judged_humans = self.humans.copy() if self.humans else []
        self.not_judged_agents = (
            [agent for agent in self.gameInfo.statusMap if agent != self.index]
            if self.gameInfo
            else []
        )
        self.guard_success = False
        self.guard_success_agent = None
        self.fake_role = Role.SEER
        self.co_date = 1
        self.kakoi = False
        self.strategies = [False, False, False, False, False]
        self.strategyA = self.strategies[0]
        self.strategyB = self.strategies[1]

    def get_fake_judge(self) -> Judge:
        judge_candidates = (
            [agent for agent in self.not_judged_humans if agent in self.alive]
            if hasattr(self, "alive")
            else []
        )
        judge_candidate = random.choice(judge_candidates) if judge_candidates else None
        result = Species.WEREWOLF
        if judge_candidate is None:
            return None
        return Judge(
            self.index,
            self.gameInfo.day if self.gameInfo else 0,
            judge_candidate,
            result,
        )

    def estimate_possessed(self) -> None:
        th = 0.5
        if self.role_predictor and self.gameInfo:
            res = self.role_predictor.chooseMostLikely(
                Role.POSSESSED,
                [agent for agent in self.gameInfo.statusMap if agent != self.index],
                threshold=th,
                returns_prob=True,
            )
            if isinstance(res, tuple):
                self.agent_possessed, _ = res
            else:
                self.agent_possessed = res
            self.alive_possessed = (
                self.agent_possessed in self.alive if self.agent_possessed else False
            )
        else:
            self.agent_possessed = None
            self.alive_possessed = False
        self.PP_flag = False
        alive_cnt = len(self.alive) if hasattr(self, "alive") else 0
        if alive_cnt <= 3 and self.alive_possessed:
            self.PP_flag = True

    def estimate_seer(self) -> None:
        self.agent_seer = None
        self.found_me = False
        for judge in self.divination_reports:
            agent = judge.agent
            target = judge.target
            result = judge.result
            if target in self.allies and result == Species.WEREWOLF:
                self.agent_seer = agent
                if target == self.index:
                    self.found_me = True
                break
        self.alive_seer = self.agent_seer in self.alive if self.agent_seer else False

    def get_possessed_divination(self) -> Judge:
        ret_judge = None
        for judge in self.divination_reports:
            if judge.agent == self.agent_possessed:
                ret_judge = judge
        return ret_judge

    def daily_initialize(self) -> None:
        super().daily_initialize()
        self.not_judged_agents = self.alive.copy() if hasattr(self, "alive") else []
        day = self.gameInfo.day if self.gameInfo else 0
        self.attack_vote_candidate = None
        self.new_target = (
            self.role_predictor.chooseMostLikely(
                Role.VILLAGER,
                [agent for agent in self.gameInfo.statusMap if agent in self.alive],
            )
            if self.role_predictor and self.gameInfo
            else None
        )
        self.new_result = Species.WEREWOLF
        self.whisper_turn = 0
        self.estimate_possessed()
        self.estimate_seer()
        if day >= 1:
            judge = self.get_fake_judge()
            if judge is not None:
                self.my_judge_queue.append(judge)
                if judge.target in self.not_judged_agents:
                    self.not_judged_agents.remove(judge.target)
                if judge.target in self.not_judged_humans:
                    self.not_judged_humans.remove(judge.target)
                if judge.result == Species.WEREWOLF:
                    self.werewolves.append(judge.target)
        if (
            self.gameInfo
            and self.gameInfo.attackedAgent is not None
            and len(self.gameInfo.lastDeadAgentList) == 0
        ):
            self.guard_success = True
            self.guard_success_agent = self.gameInfo.attackedAgent
        if (
            self.gameInfo
            and self.gameInfo.attackedAgent is not None
            and len(self.gameInfo.lastDeadAgentList) == 1
        ):
            self.guard_success = False
            self.guard_success_agent = None

    def daily_finish(self) -> None:
        return super().daily_finish()

    def talk(self) -> str:
        day = self.gameInfo.day if self.gameInfo else 0
        self.estimate_possessed()
        self.estimate_seer()
        others_seer_co = (
            [a for a in self.comingout_map if self.comingout_map[a] == Role.SEER]
            if hasattr(self, "comingout_map")
            else []
        )
        others_seer_co_num = len(others_seer_co)
        self.vote_candidate = self.vote() if hasattr(self, "vote") else None
        if self.PP_flag and not self.has_PP:
            self.has_PP = True
            return_text = self.talk_generator.generate_talk(
                ProtocolMean(False, "CO", self.index, "WEREWOLF")
            )
        if day == 0:
            if self.turn == 1:
                return_text = "よろしくお願いします。"
            else:
                return_text = "Over"
        elif day == 1:
            if self.turn == 1:
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", "ANY", None, "ANY"),
                    request=True,
                    request_target="ANY",
                )
            if not self.has_co and self.found_me:
                self.has_co = True
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, "SEER")
                )
            if not self.has_co and (others_seer_co_num >= 2 and self.alive_possessed):
                self.has_co = True
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, "SEER")
                )
            if not self.has_co and (self.turn >= 3 and others_seer_co_num == 1):
                self.has_co = True
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, "SEER")
                )
            if self.has_co and self.my_judge_queue:
                judge = self.my_judge_queue.popleft()
                if self.alive_seer:
                    self.new_target = self.agent_seer
                elif self.alive_possessed:
                    self.new_target = self.vote_candidate
                else:
                    self.new_target = (
                        self.role_predictor.chooseMostLikely(
                            Role.SEER,
                            [
                                agent
                                for agent in self.gameInfo.statusMap
                                if agent in self.alive
                            ],
                        )
                        if self.role_predictor and self.gameInfo
                        else None
                    )
                if self.new_target is None:
                    self.new_target = judge.target
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(
                        False, "DIVINED", None, self.new_target, Species.WEREWOLF
                    )
                )
        elif day == 2:
            if self.turn == 1:
                alive_others = (
                    [agent for agent in self.gameInfo.statusMap if agent in self.alive]
                    if self.gameInfo
                    else []
                )
                self.new_target = (
                    self.role_predictor.chooseLeastLikely(Role.POSSESSED, alive_others)
                    if self.role_predictor
                    else None
                )
                self.new_result = Species.HUMAN
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "DIVINED", None, self.new_target, Species.HUMAN)
                )
            if 2 <= self.turn <= 9:
                if self.PP_flag:
                    self.vote_candidate = (
                        self.role_predictor.chooseLeastLikely(
                            Role.POSSESSED,
                            [
                                agent
                                for agent in self.gameInfo.statusMap
                                if agent in self.alive
                            ],
                        )
                        if self.role_predictor and self.gameInfo
                        else None
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
        latest_vote_list = (
            self.gameInfo.latestVoteList
            if self.gameInfo and hasattr(self.gameInfo, "latestVoteList")
            else None
        )
        tmp_vote_candidate = self.vote_candidate

        if latest_vote_list:
            if len(latest_vote_list) == 3:
                alive_others = (
                    [agent for agent in self.gameInfo.statusMap if agent in self.alive]
                    if self.gameInfo
                    else []
                )
                if self.vote_candidate in alive_others:
                    alive_others.remove(self.vote_candidate)
                # 仲間を除外
                alive_others = [
                    agent for agent in alive_others if agent not in self.allies
                ]
                if alive_others and self.role_predictor:
                    self.vote_candidate = self.role_predictor.chooseMostLikely(
                        Role.WEREWOLF, alive_others
                    )
                elif alive_others:
                    self.vote_candidate = alive_others[0]  # 安定性重視
                else:
                    self.vote_candidate = None
            else:
                self.vote_candidate = (
                    self.changeVote(latest_vote_list, Role.POSSESSED, mostlikely=False)
                    if hasattr(self, "changeVote")
                    else None
                )
            if self.vote_candidate in self.allies:
                self.vote_candidate = tmp_vote_candidate
            if self.vote_candidate is not None:
                vote_target_id = self.agent_name_to_id(self.vote_candidate)

                # プロトコルに従ってAgent[XX]形式で返す
                return f"Agent[{vote_target_id:02d}]"

        self.estimate_possessed()
        self.estimate_seer()

        # 投票候補（人間のみ、仲間は除外）
        vote_candidates = (
            [agent for agent in self.humans if agent in self.alive]
            if hasattr(self, "humans")
            else []
        )

        # 狂人は投票候補から除外
        if self.agent_possessed in vote_candidates:
            vote_candidates.remove(self.agent_possessed)

        if self.PP_flag:
            self.vote_candidate = (
                self.role_predictor.chooseMostLikely(Role.VILLAGER, vote_candidates)
                if self.role_predictor and vote_candidates
                else (random.choice(vote_candidates) if vote_candidates else None)
            )
        elif self.alive_possessed:
            possessed_judge = self.get_possessed_divination()
            if possessed_judge:
                target = possessed_judge.target
                result = possessed_judge.result
                if result == Species.HUMAN:
                    if self.new_target is not None:
                        self.vote_candidate = self.new_target
                    else:
                        candidates = vote_candidates.copy()
                        if self.agent_possessed in candidates:
                            candidates.remove(self.agent_possessed)
                        if candidates and self.role_predictor:
                            self.vote_candidate = self.role_predictor.chooseLeastLikely(
                                Role.WEREWOLF, candidates
                            )
                        elif candidates:
                            self.vote_candidate = candidates[0]  # 安定性重視
                        else:
                            self.vote_candidate = None
                elif result == Species.WEREWOLF:
                    if target in self.alive:
                        self.vote_candidate = target
                    else:
                        candidates = vote_candidates.copy()
                        if self.agent_possessed in candidates:
                            candidates.remove(self.agent_possessed)
                        if candidates and self.role_predictor:
                            self.vote_candidate = self.role_predictor.chooseLeastLikely(
                                Role.WEREWOLF, candidates
                            )
                        elif candidates:
                            self.vote_candidate = candidates[0]  # 安定性重視
                        else:
                            self.vote_candidate = None
        else:
            if self.new_target is not None:
                self.vote_candidate = self.new_target
            else:
                if vote_candidates and self.role_predictor:
                    self.vote_candidate = self.role_predictor.chooseLeastLikely(
                        Role.WEREWOLF, vote_candidates
                    )
                elif vote_candidates:
                    self.vote_candidate = vote_candidates[0]  # 安定性重視
                else:
                    self.vote_candidate = None

        # 最終的なフォールバック
        if self.vote_candidate is None or self.vote_candidate in self.allies:
            # 人間の候補から選択
            human_candidates = [
                agent
                for agent in self.humans
                if agent in self.alive and agent not in self.allies
            ]
            if human_candidates:
                self.vote_candidate = human_candidates[0]  # 安定性重視
            else:
                # 最終手段として生存エージェントから選択（仲間以外）
                alive_agents = self.get_alive_agents()
                non_ally_agents = [
                    agent for agent in alive_agents if agent not in self.allies
                ]
                self.vote_candidate = non_ally_agents[0] if non_ally_agents else "1"

        vote_target = self.vote_candidate if self.vote_candidate is not None else "1"

        # エージェント名を整数IDに安全に変換
        vote_target_id = self.agent_name_to_id(vote_target)

        # プロトコルに従ってAgent[XX]形式で返す
        return f"Agent[{vote_target_id:02d}]"

    def whisper(self) -> str:
        return super().whisper()

    def attack(self) -> str:
        """攻撃リクエストに対する応答を返す（JSON形式）."""
        self.estimate_possessed()
        self.estimate_seer()

        # 生存エージェントID（自分と仲間以外）
        alive_ids = self.get_alive_agent_ids()
        my_id = int(self.index) if self.index and self.index.isdigit() else 1

        # 仲間（人狼）のIDリストを作成
        ally_ids = []
        if hasattr(self, "allies"):
            for ally in self.allies:
                ally_id = self.agent_name_to_id(ally) if isinstance(ally, str) else ally
                ally_ids.append(ally_id)
        ally_ids.append(my_id)  # 自分も追加

        # 攻撃候補（仲間以外の生存エージェント）
        attack_candidates = [
            agent_id for agent_id in alive_ids if agent_id not in ally_ids
        ]

        # 狂人のIDを除外
        if hasattr(self, "agent_possessed") and self.agent_possessed:
            possessed_id = self.agent_name_to_id(self.agent_possessed)
            if possessed_id in attack_candidates:
                attack_candidates.remove(possessed_id)

        # 護衛成功したエージェントのIDを除外
        if hasattr(self, "guard_success_agent") and self.guard_success_agent:
            guard_success_id = self.agent_name_to_id(self.guard_success_agent)
            if guard_success_id in attack_candidates:
                attack_candidates.remove(guard_success_id)

        # 脅威となるエージェントIDを特定
        threat_ids = []
        if (
            self.gameInfo
            and hasattr(self.gameInfo, "latestVoteList")
            and self.gameInfo.latestVoteList
        ):
            for vote in self.gameInfo.latestVoteList:
                if hasattr(vote, "agent") and hasattr(vote, "target"):
                    voter_id = self.agent_name_to_id(vote.agent)
                    target_id = self.agent_name_to_id(vote.target)
                    if target_id in ally_ids and voter_id in attack_candidates:
                        threat_ids.append(voter_id)

        # 占い師COしているエージェントID
        seer_co_ids = []
        if hasattr(self, "comingout_map"):
            for agent_name, role in self.comingout_map.items():
                if role == Role.SEER:
                    agent_id = self.agent_name_to_id(agent_name)
                    if agent_id in attack_candidates:
                        seer_co_ids.append(agent_id)

        # 占い師CO以外の候補
        non_seer_candidates = [
            agent_id for agent_id in attack_candidates if agent_id not in seer_co_ids
        ]

        attack_target_id = None

        # 攻撃戦略
        if threat_ids:
            # 脅威となるエージェントを優先攻撃
            if self.role_predictor:
                try:
                    str_candidates = [str(id) for id in threat_ids]
                    chosen_str = self.role_predictor.chooseStrongLikely(
                        Role.VILLAGER, str_candidates, coef=3.0
                    )
                    attack_target_id = (
                        int(chosen_str)
                        if chosen_str and chosen_str.isdigit()
                        else threat_ids[0]
                    )
                except Exception as e:
                    print(f"[Werewolf Warning] role_predictor failed: {e}")
                    attack_target_id = threat_ids[0]
            else:
                attack_target_id = threat_ids[0]  # 安定性重視
        elif non_seer_candidates:
            # 占い師CO以外から選択
            if self.role_predictor:
                try:
                    str_candidates = [str(id) for id in non_seer_candidates]
                    chosen_str = self.role_predictor.chooseStrongLikely(
                        Role.VILLAGER, str_candidates, coef=3.0
                    )
                    attack_target_id = (
                        int(chosen_str)
                        if chosen_str and chosen_str.isdigit()
                        else non_seer_candidates[0]
                    )
                except Exception as e:
                    print(f"[Werewolf Warning] role_predictor failed: {e}")
                    attack_target_id = non_seer_candidates[0]
            else:
                attack_target_id = non_seer_candidates[0]  # 安定性重視
        elif attack_candidates:
            # 占い師COも含めて選択（最終手段）
            if self.role_predictor:
                try:
                    str_candidates = [str(id) for id in attack_candidates]
                    chosen_str = self.role_predictor.chooseStrongLikely(
                        Role.VILLAGER, str_candidates, coef=3.0
                    )
                    attack_target_id = (
                        int(chosen_str)
                        if chosen_str and chosen_str.isdigit()
                        else attack_candidates[0]
                    )
                except Exception as e:
                    print(f"[Werewolf Warning] role_predictor failed: {e}")
                    attack_target_id = attack_candidates[0]
            else:
                attack_target_id = attack_candidates[0]  # 安定性重視
        else:
            # 最終フォールバック
            other_ids = [agent_id for agent_id in alive_ids if agent_id != my_id]
            attack_target_id = other_ids[0] if other_ids else (1 if my_id != 1 else 2)

        # 狂人への攻撃を避ける最終チェック
        if (
            self.role_predictor
            and attack_target_id
            and hasattr(self, "agent_possessed")
            and self.agent_possessed
        ):
            possessed_id = self.agent_name_to_id(self.agent_possessed)
            if attack_target_id == possessed_id:
                remaining_candidates = [
                    agent_id
                    for agent_id in attack_candidates
                    if agent_id != attack_target_id and agent_id != possessed_id
                ]
                if remaining_candidates:
                    attack_target_id = remaining_candidates[0]

        # プロトコルに従ってAgent[XX]形式で返す
        return f"Agent[{attack_target_id:02d}]"

    def action(self) -> str:
        if self.request == Request.ATTACK:
            return self.attack()
        else:
            return super().action()
