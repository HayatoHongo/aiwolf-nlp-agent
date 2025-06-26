"""占い師のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent
from collections import deque
from cls import DivineResult, Judge, ProtocolMean, Role, Species
from lib.AIWolf import RolePredictor, ScoreMatrix
from lib import TalkGenerator


class Seer(Agent):
    """占い師のエージェントクラス."""

    co_date: int
    has_co: bool
    my_judge_queue: deque
    not_divined_agents: list[str]
    werewolves: list[str]
    strategies: list[bool]
    new_target: str
    new_result: Species

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
        super().__init__(config, name, game_id, Role.SEER, ssh_host, ssh_user, ssh_key)
        self.co_date = 1
        self.has_co = False
        self.my_judge_queue = deque()
        self.not_divined_agents = []
        self.werewolves = []
        self.new_target = None
        self.new_result = Species.UNC
        self.strategies = [True]
        self.strategyA = self.strategies[0]
        if self.strategyA:
            self.co_date = 1

    def parse_info(self, receive: str) -> None:
        return super().parse_info(receive)

    def get_info(self):
        return super().get_info()

    def initialize(self) -> None:
        super().initialize()
        self.co_date = 1
        self.has_co = False
        self.my_judge_queue.clear()
        self.not_divined_agents = [
            agent for agent in self.gameInfo.statusMap if agent != self.index
        ]
        self.werewolves.clear()
        self.new_target = None
        self.new_result = Species.UNC
        self.strategies = [True]
        self.strategyA = self.strategies[0]
        if self.strategyA:
            self.co_date = 1

    def daily_initialize(self) -> None:
        super().daily_initialize()
        self.new_target = None
        self.new_result = Species.WEREWOLF
        judge = (
            Judge(**self.gameInfo.divineResult)
            if self.gameInfo and self.gameInfo.divineResult
            else None
        )
        if judge is not None:
            self.my_judge_queue.append(judge)
            if judge.target in self.not_divined_agents:
                self.not_divined_agents.remove(judge.target)
            if judge.result == Species.WEREWOLF:
                self.werewolves.append(judge.target)
            if self.score_matrix:
                self.score_matrix.my_divined(
                    self.gameInfo, self.gameSetting, judge.target, judge.result
                )

    def daily_finish(self) -> None:
        return super().daily_finish()

    def talk(self) -> str:
        day: int = self.gameInfo.day if self.gameInfo else 0
        turn: int = self.turn
        others_seer_co = (
            [
                a
                for a in self.comingout_map
                if a in self.alive and self.comingout_map[a] == Role.SEER
            ]
            if hasattr(self, "alive")
            else []
        )
        others_co_num = len(others_seer_co)
        self.vote_candidate = self.vote() if hasattr(self, "vote") else None
        if day == 0:
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
            elif turn == 2 and self.has_co and self.my_judge_queue:
                judge = self.my_judge_queue.popleft()
                self.new_target = judge.target
                self.new_result = judge.result
                if judge.result == Species.WEREWOLF:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "DIVINED", None, judge.target, judge.result)
                    )
                elif judge.result == Species.HUMAN:
                    self.new_result = Species.WEREWOLF
                    if others_co_num == 0:
                        self.new_target = (
                            self.role_predictor.chooseStrongLikely(
                                Role.WEREWOLF, self.alive, coef=0.1
                            )
                            if self.role_predictor
                            else judge.target
                        )
                    else:
                        self.new_target = (
                            self.role_predictor.chooseMostLikely(
                                Role.WEREWOLF, others_seer_co
                            )
                            if self.role_predictor
                            else judge.target
                        )
                    if self.new_target is None:
                        self.new_target = judge.target
                        self.new_result = judge.result
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(
                            False, "DIVINED", None, self.new_target, self.new_result
                        )
                    )
            elif 3 <= turn <= 9:
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
            if turn == 1 and self.has_co and self.my_judge_queue:
                judge = self.my_judge_queue.popleft()
                self.new_target = judge.target
                self.new_result = judge.result
                if judge.result == Species.WEREWOLF:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "DIVINED", None, judge.target, judge.result)
                    )
                elif judge.result == Species.HUMAN:
                    candidates = (
                        [
                            agent
                            for agent in self.not_divined_agents
                            if agent in self.alive
                        ]
                        if hasattr(self, "alive")
                        else []
                    )
                    self.new_target = (
                        self.role_predictor.chooseMostLikely(Role.WEREWOLF, candidates)
                        if self.role_predictor
                        else judge.target
                    )
                    self.new_result = Species.WEREWOLF
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(
                            False, "DIVINED", None, self.new_target, self.new_result
                        )
                    )
                else:
                    return_text = "SKIP"
            elif (
                turn == 2
                and self.role_predictor
                and hasattr(self.role_predictor, "estimate_alive_possessed")
                and self.role_predictor.estimate_alive_possessed(threshold=0.5)
            ):
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, "WEREWOLF")
                )
            elif 2 <= turn <= 9:
                if turn % 2 == 0:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.new_target)
                    )
                else:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", "ANY", self.new_target),
                        request=True,
                        request_target="ANY",
                    )
            else:
                return_text = "SKIP"
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
        if latest_vote_list:
            self.vote_candidate = (
                self.role_predictor.changeVote(latest_vote_list, Role.WEREWOLF)
                if self.role_predictor
                else None
            )
            return (
                str(self.vote_candidate)
                if self.vote_candidate is not None
                else str(self.index)
            )
        vote_candidates = self.alive.copy() if hasattr(self, "alive") else []
        alive_werewolves = self.werewolves.copy()
        if alive_werewolves:
            self.vote_candidate = (
                self.role_predictor.chooseMostLikely(Role.WEREWOLF, alive_werewolves)
                if self.role_predictor
                else None
            )
        else:
            self.vote_candidate = (
                self.role_predictor.chooseMostLikely(Role.WEREWOLF, vote_candidates)
                if self.role_predictor
                else None
            )
        if self.vote_candidate is None or self.vote_candidate == self.index:
            self.vote_candidate = (
                self.role_predictor.chooseMostLikely(Role.WEREWOLF, vote_candidates)
                if self.role_predictor
                else None
            )
        vote_target = (
            self.vote_candidate if self.vote_candidate is not None else self.index
        )
        import json

        data = {"agentIdx": int(vote_target)}
        return json.dumps(data, separators=(",", ":"))

    def whisper(self) -> str:
        return super().whisper()

    def divine(self) -> str:
        divine_candidates = (
            [agent for agent in self.not_divined_agents if agent in self.alive]
            if hasattr(self, "alive")
            else []
        )
        others_co = [
            a
            for a in self.comingout_map
            if a in divine_candidates and (self.comingout_map[a] == Role.SEER)
        ]
        divine_no_co_candidates = [a for a in divine_candidates if a not in others_co]
        divine_candidate = (
            self.role_predictor.chooseStrongLikely(
                Role.WEREWOLF, divine_no_co_candidates, coef=0.5
            )
            if self.role_predictor
            else None
        )
        divine_target = divine_candidate if divine_candidate is not None else self.index
        import json

        data = {"agentIdx": int(divine_target)}
        return json.dumps(data, separators=(",", ":"))

    def action(self) -> str:
        if self.request == "DIVINE":
            return self.divine()
        else:
            return super().action()
