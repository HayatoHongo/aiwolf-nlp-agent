"""占い師のエージェントクラスを定義するモジュール."""

from __future__ import annotations

import random
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

        # self.indexが有効であることを確認してから使用
        if self.index and self.index.isdigit():
            self.not_divined_agents = [
                agent
                for agent in (self.gameInfo.statusMap if self.gameInfo else {})
                if agent != int(self.index)
            ]
        else:
            self.not_divined_agents = (
                list(self.gameInfo.statusMap.keys()) if self.gameInfo else []
            )

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

        # 自分のIDを確認
        my_index = None
        if self.index and self.index.isdigit():
            my_index = int(self.index)

        if latest_vote_list:
            self.vote_candidate = (
                self.role_predictor.changeVote(latest_vote_list, Role.WEREWOLF)
                if self.role_predictor
                else None
            )
            if self.vote_candidate is not None and self.vote_candidate != my_index:
                vote_target_id = self.agent_name_to_id(self.vote_candidate)
                import json

                data = {"agentIdx": vote_target_id}
                return json.dumps(data, separators=(",", ":"))

        # 投票候補（自分以外）
        vote_candidates = self.alive.copy() if hasattr(self, "alive") else []
        if my_index:
            vote_candidates = [
                agent
                for agent in vote_candidates
                if agent != my_index and agent != str(my_index)
            ]

        # 発見した人狼がいる場合は優先的に投票
        alive_werewolves = [ww for ww in self.werewolves if ww in vote_candidates]

        if alive_werewolves:
            # 人狼がいる場合は優先的に選択（確定情報に基づく）
            if self.role_predictor:
                self.vote_candidate = self.role_predictor.chooseMostLikely(
                    Role.WEREWOLF, alive_werewolves
                )
            else:
                self.vote_candidate = alive_werewolves[0]  # 安定性重視
        else:
            # 人狼がいない場合は疑わしいエージェントを選択
            if self.role_predictor and vote_candidates:
                self.vote_candidate = self.role_predictor.chooseMostLikely(
                    Role.WEREWOLF, vote_candidates
                )
            elif vote_candidates:
                self.vote_candidate = vote_candidates[0]  # 安定性重視
            else:
                self.vote_candidate = None

        # 自分への投票を避ける
        if (
            self.vote_candidate is None
            or self.vote_candidate == my_index
            or self.vote_candidate == str(my_index)
        ):
            if vote_candidates:
                self.vote_candidate = vote_candidates[0]  # 安定性重視
            else:
                # 最終的なフォールバック
                alive_agents = self.get_alive_agents()
                if my_index:
                    alive_agents = [
                        agent for agent in alive_agents if agent != str(my_index)
                    ]
                self.vote_candidate = alive_agents[0] if alive_agents else "1"

        vote_target = self.vote_candidate if self.vote_candidate is not None else "1"

        # エージェント名を整数IDに安全に変換
        vote_target_id = self.agent_name_to_id(vote_target)
        import json

        data = {"agentIdx": vote_target_id}
        return json.dumps(data, separators=(",", ":"))

    def whisper(self) -> str:
        return super().whisper()

    def divine(self) -> str:
        """占いリクエストに対する応答を返す（JSON形式）."""
        # 占い候補から自分を除外
        alive_ids = self.get_alive_agent_ids()
        my_id = int(self.index) if self.index and self.index.isdigit() else 1

        # まだ占っていないエージェントIDを特定
        not_divined_ids = []
        for agent_id in alive_ids:
            if agent_id != my_id:
                # not_divined_agentsは文字列や整数が混在している可能性があるため安全に変換
                is_not_divined = True
                for nd_agent in self.not_divined_agents:
                    nd_id = (
                        self.agent_name_to_id(nd_agent)
                        if isinstance(nd_agent, str)
                        else nd_agent
                    )
                    if agent_id == nd_id:
                        is_not_divined = True
                        break
                else:
                    is_not_divined = False

                if is_not_divined:
                    not_divined_ids.append(agent_id)

        divine_candidates = not_divined_ids

        # 他の占い師COしているエージェントID
        others_co_ids = []
        for agent_name, role in self.comingout_map.items():
            if role == Role.SEER:
                agent_id = self.agent_name_to_id(agent_name)
                if agent_id in divine_candidates:
                    others_co_ids.append(agent_id)

        # CO していないエージェントID
        divine_no_co_candidates = [
            agent_id for agent_id in divine_candidates if agent_id not in others_co_ids
        ]

        divine_candidate_id = None

        # 1. COしていない候補から選択（優先）
        if divine_no_co_candidates and self.role_predictor:
            try:
                # role_predictorは文字列IDを期待する可能性があるため変換
                str_candidates = [str(id) for id in divine_no_co_candidates]
                chosen_str = self.role_predictor.chooseStrongLikely(
                    Role.WEREWOLF, str_candidates, coef=0.5
                )
                divine_candidate_id = (
                    int(chosen_str)
                    if chosen_str and chosen_str.isdigit()
                    else divine_no_co_candidates[0]
                )
            except Exception as e:
                print(f"[Seer Warning] role_predictor failed: {e}")
                divine_candidate_id = divine_no_co_candidates[0]
        elif divine_no_co_candidates:
            divine_candidate_id = divine_no_co_candidates[0]  # 安定性重視

        # 2. COしていない候補がない場合は、CO済みの候補から選択
        elif others_co_ids and self.role_predictor:
            try:
                str_candidates = [str(id) for id in others_co_ids]
                chosen_str = self.role_predictor.chooseMostLikely(
                    Role.WEREWOLF, str_candidates
                )
                divine_candidate_id = (
                    int(chosen_str)
                    if chosen_str and chosen_str.isdigit()
                    else others_co_ids[0]
                )
            except Exception as e:
                print(f"[Seer Warning] role_predictor failed: {e}")
                divine_candidate_id = others_co_ids[0]
        elif others_co_ids:
            divine_candidate_id = others_co_ids[0]  # 安定性重視

        # 3. 全候補から選択（最終手段）
        elif divine_candidates and self.role_predictor:
            try:
                str_candidates = [str(id) for id in divine_candidates]
                chosen_str = self.role_predictor.chooseMostLikely(
                    Role.WEREWOLF, str_candidates
                )
                divine_candidate_id = (
                    int(chosen_str)
                    if chosen_str and chosen_str.isdigit()
                    else divine_candidates[0]
                )
            except Exception as e:
                print(f"[Seer Warning] role_predictor failed: {e}")
                divine_candidate_id = divine_candidates[0]
        elif divine_candidates:
            divine_candidate_id = divine_candidates[0]  # 安定性重視

        # 4. 最終的なフォールバック（自分以外の生存エージェント）
        if divine_candidate_id is None:
            other_ids = [agent_id for agent_id in alive_ids if agent_id != my_id]
            divine_candidate_id = (
                other_ids[0] if other_ids else (1 if my_id != 1 else 2)
            )

        print(f"[DEBUG] Seer Divine: My ID={my_id}, Target ID={divine_candidate_id}")

        import json

        data = {"agentIdx": divine_candidate_id}
        return json.dumps(data, separators=(",", ":"))

    def action(self) -> str:
        if self.request == "DIVINE":
            return self.divine()
        else:
            return super().action()
