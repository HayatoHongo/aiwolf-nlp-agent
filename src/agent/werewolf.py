"""人狼のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

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
        self.humans = (
            [a for a in self.gameInfo.statusMap if a not in self.allies]
            if self.gameInfo
            else []
        )
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
                self.vote_candidate = (
                    self.role_predictor.chooseMostLikely(Role.WEREWOLF, alive_others)
                    if self.role_predictor
                    else None
                )
            else:
                self.vote_candidate = (
                    self.changeVote(latest_vote_list, Role.POSSESSED, mostlikely=False)
                    if hasattr(self, "changeVote")
                    else None
                )
            if self.vote_candidate in self.allies:
                self.vote_candidate = tmp_vote_candidate
            return (
                self.vote_candidate if self.vote_candidate is not None else self.index
            )
        self.estimate_possessed()
        self.estimate_seer()
        vote_candidates = (
            [agent for agent in self.humans if agent in self.alive]
            if hasattr(self, "humans")
            else []
        )
        if self.agent_possessed in vote_candidates:
            vote_candidates.remove(self.agent_possessed)
        if self.PP_flag:
            self.vote_candidate = (
                self.role_predictor.chooseMostLikely(Role.VILLAGER, vote_candidates)
                if self.role_predictor
                else None
            )
            return (
                self.vote_candidate if self.vote_candidate is not None else self.index
            )
        if self.alive_possessed:
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
                        self.vote_candidate = (
                            self.role_predictor.chooseLeastLikely(
                                Role.WEREWOLF, candidates
                            )
                            if self.role_predictor
                            else None
                        )
                elif result == Species.WEREWOLF:
                    if target in self.alive:
                        self.vote_candidate = target
                    else:
                        candidates = vote_candidates.copy()
                        if self.agent_possessed in candidates:
                            candidates.remove(self.agent_possessed)
                        self.vote_candidate = (
                            self.role_predictor.chooseLeastLikely(
                                Role.WEREWOLF, candidates
                            )
                            if self.role_predictor
                            else None
                        )
        else:
            if self.new_target is not None:
                self.vote_candidate = self.new_target
            else:
                self.vote_candidate = (
                    self.role_predictor.chooseLeastLikely(
                        Role.WEREWOLF, vote_candidates
                    )
                    if self.role_predictor
                    else None
                )
        vote_target = (
            self.vote_candidate if self.vote_candidate is not None else self.index
        )
        import json

        data = {"agentIdx": int(vote_target)}
        return json.dumps(data, separators=(",", ": "))

    def whisper(self) -> str:
        return super().whisper()

    def attack(self) -> str:
        self.estimate_possessed()
        self.estimate_seer()
        attack_vote_candidates = (
            [agent for agent in self.humans if agent in self.alive]
            if hasattr(self, "humans")
            else []
        )
        if self.agent_possessed in attack_vote_candidates:
            attack_vote_candidates.remove(self.agent_possessed)
        if self.guard_success_agent in attack_vote_candidates:
            attack_vote_candidates.remove(self.guard_success_agent)
        latest_vote_list = (
            self.gameInfo.latestVoteList
            if self.gameInfo and hasattr(self.gameInfo, "latestVoteList")
            else []
        )
        self.threat = [
            v.agent
            for v in latest_vote_list
            if hasattr(v, "agent")
            and hasattr(v, "target")
            and v.target in self.allies
            and v.agent in attack_vote_candidates
        ]
        others_seer_co = (
            [
                a
                for a in self.comingout_map
                if a in attack_vote_candidates and self.comingout_map[a] == Role.SEER
            ]
            if hasattr(self, "comingout_map")
            else []
        )
        for seer_candidate in others_seer_co:
            if seer_candidate in attack_vote_candidates:
                attack_vote_candidates.remove(seer_candidate)
        if not attack_vote_candidates:
            attack_vote_candidates = (
                [agent for agent in self.humans if agent in self.alive]
                if hasattr(self, "humans")
                else []
            )
        if self.threat:
            self.attack_vote_candidate = (
                self.role_predictor.chooseStrongLikely(
                    Role.VILLAGER, self.threat, coef=3.0
                )
                if self.role_predictor
                else None
            )
        else:
            self.attack_vote_candidate = (
                self.role_predictor.chooseStrongLikely(
                    Role.VILLAGER, attack_vote_candidates, coef=3.0
                )
                if self.role_predictor
                else None
            )
        if (
            self.role_predictor
            and self.role_predictor.getMostLikelyRole(self.attack_vote_candidate)
            == Role.POSSESSED
        ):
            self.attack_vote_candidate = (
                self.role_predictor.chooseLeastLikely(
                    Role.POSSESSED, attack_vote_candidates
                )
                if self.role_predictor
                else self.attack_vote_candidate
            )
        attack_target = (
            self.attack_vote_candidate
            if self.attack_vote_candidate is not None
            else self.index
        )
        import json

        data = {"agentIdx": int(attack_target)}
        return json.dumps(data, separators=(",", ": "))

    def action(self) -> str:
        if self.request == "ATTACK":
            return self.attack()
        else:
            return super().action()
