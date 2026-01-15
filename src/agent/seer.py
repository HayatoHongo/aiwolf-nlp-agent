"""占い師のエージェントクラスを定義するモジュール."""

from __future__ import annotations

from aiwolf_nlp_common.packet import Role
import random
from utils.llm_api import call_openai_llm
from agent.agent import Agent
import configparser
import json
from collections import deque
from typing import Deque
from cls import DivineResult, Judge, ProtocolMean, Role, Species


class Seer(Agent):
    """占い師のエージェントクラス."""

    """ddhb seer agent."""
    co_date: int  # COする日にち
    """Scheduled comingout date."""
    has_co: bool  # COしたか
    """Whether or not comingout has done."""
    my_judge_queue: Deque[DivineResult]  # 自身の占い結果キュー
    """Queue of divination results."""
    not_divined_agents: list[str]  # 占っていないエージェント
    """strs that have not been divined."""
    werewolves: list[str]  # 人狼結果のエージェント
    """Found werewolves."""
    strategies: list[bool]  # 戦略フラグのリスト
    # ----- 5人村用：結果を変更して報告する -----
    new_target: str  # 偽の占い対象
    new_result: Species  # 偽の占い結果

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        """占い師のエージェントを初期化する."""
        super().__init__(config, name, game_id, Role.SEER)
        self.co_date = 0
        self.has_co = False
        self.my_judge_queue = deque()
        self.not_divined_agents = []
        self.werewolves = []

        self.new_target = None
        self.new_result = Species.UNC
        self.strategies = []
        self.divine_results: dict[str, str] = {}  # 占い結果を保存

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
        self.strategyA = self.strategies[0]  # 戦略A: COする日にちの変更（初日CO）
        # 戦略A: 初日CO
        if self.strategyA:
            self.co_date = 1
        return

    def daily_initialize(self) -> None:
        super().daily_initialize()
        self.new_target = None
        self.new_result = Species.WEREWOLF
        # 占い結果
        judge: Judge | None = (
            Judge(**self.gameInfo.divineResult) if self.gameInfo.divineResult else None
        )
        if judge is not None:
            self.my_judge_queue.append(judge)  # 結果追加
            # 占い対象を、占っていないエージェントリストから除く
            if judge.target in self.not_divined_agents:
                self.not_divined_agents.remove(judge.target)
            # 黒結果
            if judge.result == Species.WEREWOLF:
                self.werewolves.append(judge.target)  # 人狼リストに追加
            # スコアの更新
            self.score_matrix.my_divined(
                self.gameInfo, self.gameSetting, judge.target, judge.result
            )
        return

    def talk(self) -> str:
        """占い師のtalkメソッド."""
        return self.talk_protocol()
        #return self.talk_llmbase()

    def talk_protocol(self) -> str:
        others_seer_co: list[str] = [
            a
            for a in self.comingout_map
            if a in self.alive and self.comingout_map[a] == Role.SEER
        ]
        day: int = self.gameInfo.day
        others_co_num: int = len(others_seer_co)
        self.vote_candidate = self.vote()
        # ---------- 5人村 ----------
        if day == 0:
            if self.turn == 1:
                return_text = "よろしくお願いします。"
            elif self.turn >= 2:
                return_text = "Over"
        elif day == 1:
            # ----- CO -----
            if self.turn == 1:
                if not self.has_co:
                    self.has_co = True
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "CO", self.index, None, "SEER")
                    )
                    # return_text = "私はほんとに占い師です。"
            # ----- 結果報告 -----
            elif self.turn == 2:
                if self.has_co and self.my_judge_queue:
                    judge: Judge = self.my_judge_queue.popleft()
                    self.new_target = judge.target
                    self.new_result = judge.result
                    # 黒結果：そのまま報告
                    if judge.result == Species.WEREWOLF:
                        return_text = self.talk_generator.generate_talk(
                            ProtocolMean(
                                False, "DIVINED", None, judge.target, judge.result
                            )
                        )
                        # return_text = f"{judge.target}を占いました。人狼です！{judge.target}に投票しましょう。"
                    # 白結果：状況に応じて黒結果を報告
                    elif judge.result == Species.HUMAN:
                        self.new_result = Species.WEREWOLF
                        # 対抗なし：人狼確率＋勝率が高いエージェント
                        if others_co_num == 0:
                            self.new_target = self.role_predictor.chooseStrongLikely(
                                Role.WEREWOLF, self.alive, coef=0.1
                            )
                        # 対抗あり：game<50では対抗で人狼っぽいエージェント、game>=50では人狼っぽいエージェント
                        else:
                            # if game < 50:
                            self.new_target = self.role_predictor.chooseMostLikely(
                                Role.WEREWOLF, others_seer_co
                            )
                            # else:
                            #     self.new_target = self.role_predictor
                            #                           .chooseMostLikely(Role.WEREWOLF, self.alive)
                        if self.new_target is None:
                            self.new_target = judge.target
                            self.new_result = judge.result
                        return_text = self.talk_generator.generate_talk(
                            ProtocolMean(
                                False, "DIVINED", None, self.new_target, self.new_result
                            )
                        )
                        # return_text = f"{self.new_target}を占いました。人狼です！{self.new_target}に投票しましょう。"
            # ----- VOTE and REQUEST -----
            elif 3 <= self.turn <= 9:
                if self.turn % 2 == 0:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.new_target),
                        request=True,
                        request_target="ANY",
                    )
                    # return_text = f"今日は{self.new_target}に投票しましょう。"
                else:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.new_target)
                    )
                    # return_text = f"今日は{self.new_target}に投票します。"
            else:
                return_text = "SKIP"
        elif day >= 2:
            # ----- 結果報告 -----
            if self.turn == 1:
                if self.has_co and self.my_judge_queue:
                    judge: Judge = self.my_judge_queue.popleft()
                    self.new_target = judge.target
                    self.new_result = judge.result
                    # 黒結果：そのまま報告
                    if judge.result == Species.WEREWOLF:
                        return_text = self.talk_generator.generate_talk(
                            ProtocolMean(
                                False, "DIVINED", None, judge.target, judge.result
                            )
                        )
                        # return_text = f"私はほんとに占い師で、{judge.target}を占いました。人狼です！{judge.target}に投票しましょう。"
                    # 白結果：生存者3人だから、残りの1人に黒結果（結果としては等価）
                    # 注意：占い先が噛まれた場合は等価ではない→人狼っぽい方に黒結果
                    elif judge.result == Species.HUMAN:
                        self.new_target = self.role_predictor.chooseMostLikely(
                            Role.WEREWOLF,
                            [
                                agent
                                for agent in self.not_divined_agents
                                if agent in self.alive
                            ],
                        )
                        self.new_result = Species.WEREWOLF
                        return_text = self.talk_generator.generate_talk(
                            ProtocolMean(
                                False, "DIVINED", None, self.new_target, self.new_result
                            )
                        )
                        # return_text = f"私はほんとに占い師で、{self.new_target}を占いました。人狼です！(実は嘘){self.new_target}に投票しましょう。"
                else:
                    return_text = "SKIP"
            # 狂人が生きている場合→人狼COでPPを防ぐ
            elif self.turn == 2 and self.role_predictor.estimate_alive_possessed(
                threshold=0.5
            ):
                return_text = self.talk_generator.generate_talk(
                    ProtocolMean(False, "CO", self.index, None, "WEREWOLF")
                )
                # return_text = "私は人狼です。PP宣言します"
            # ----- VOTE and REQUEST -----
            elif 2 <= self.turn <= 9:
                if self.turn % 2 == 0:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.new_target)
                    )
                    # return_text = f"今日は{self.new_target}に投票します。"
                else:
                    return_text = self.talk_generator.generate_talk(
                        ProtocolMean(False, "VOTE", None, self.new_target),
                        request=True,
                        request_target="ANY",
                    )
                    # return_text = f"今日は{self.new_target}に投票しましょう。"
            else:
                return_text = "SKIP"
        self.turn += 1
        return return_text

    def vote(self) -> str:
        return self.vote_protocol()
        #return self.vote_llmbase()

    def vote_protocol(self) -> str:
        # ----------  同数投票の処理 ----------
        latest_vote_list = self.gameInfo.latestVoteList
        if latest_vote_list:
            self.vote_candidate = self.changeVote(latest_vote_list, Role.WEREWOLF)
            return (
                self.vote_candidate if self.vote_candidate is not None else self.index
            )
        # 投票候補
        vote_candidates: list[str] = self.alive.copy()
        # if a in vote_candidates としているから、aliveは保証されている
        # others_seer_co: list[str] = [a for a in self.comingout_map
        #                              if a in vote_candidates and
        # self.comingout_map[a] == Role.SEER]
        alive_werewolves: list[str] = self.werewolves.copy()
        # ---------- 5人村 ----------
        # 投票対象の優先順位：黒結果→偽の黒先→人狼っぽいエージェント
        if alive_werewolves:
            # print("alive_werewolves:\t", self.agent_to_index(alive_werewolves))
            self.vote_candidate = self.role_predictor.chooseMostLikely(
                Role.WEREWOLF, alive_werewolves
            )
        # 2ターン目の推論だとミスしている可能性があるので、行動学習で推定した結果を使う
        # elif self.new_target != AGENT_NONE:
        #     self.vote_candidate = self.new_target
        else:
            # print("vote_candidates:\t", self.agent_to_index(vote_candidates))
            self.vote_candidate = self.role_predictor.chooseMostLikely(
                Role.WEREWOLF, vote_candidates
            )
        # ----- 投票ミスを防ぐ -----
        if self.vote_candidate is None or self.vote_candidate == self.index:
            print("vote_candidates: AGENT_NONE or self.me")
            self.vote_candidate = self.role_predictor.chooseMostLikely(
                Role.WEREWOLF, vote_candidates
            )
        vote_target = (
            self.vote_candidate if self.vote_candidate is not None else self.index
        )
        return vote_target

    def divine(self) -> str:
        """占い師の占いメソッド."""
        return self.divine_protocol()
        #return self.divine_llmbase()

    def divine_protocol(self) -> str:
        # game: int = Util.game_count
        divine_candidate: str = None
        # 占い候補：占っていないエージェント
        divine_candidates: list[str] = [
            agent for agent in self.not_divined_agents if agent in self.alive
        ]
        others_co: list[str] = [
            a
            for a in self.comingout_map
            if a in divine_candidates and (self.comingout_map[a] == Role.SEER)
        ]
        # 占い候補：占っていないエージェント＋(占いor霊媒)COしていないエージェント
        divine_no_co_candidates: list[str] = [
            a for a in divine_candidates if a not in others_co
        ]
        # 占い対象：game<50では人狼確率＋勝率が高いエージェント、game>=50では人狼っぽいエージェント
        # game後半は、推論精度が高いため、人狼っぽいエージェントを占う
        # if game < 50:
        # divine_candidate = self.role_predictor.chooseStrongLikely(Role.WEREWOLF,
        # divine_candidates, coef=0.5)
        divine_candidate = self.role_predictor.chooseStrongLikely(
            Role.WEREWOLF, divine_no_co_candidates, coef=0.5
        )
        # else:
        #     # divine_candidate = self.role_predictor.chooseMostLikely(Role.WEREWOLF,
        # divine_candidates)
        #     divine_candidate = self.role_predictor.chooseMostLikely(Role.WEREWOLF,
        # divine_no_co_candidates)
        # ---------- 5人村15人村共通 ----------
        # 初日：勝率が高いエージェント（情報がほぼないため）
        # 白結果：味方になる、黒結果：早めに処理できる
        print(f"占い対象：{divine_candidate}")
        divine_target = divine_candidate if divine_candidate is not None else self.index
        return divine_target

    def divine(self) -> str:
        """占いリクエストに対する応答を返す（LLM＋ルールベースフォールバック）。"""
        alive_agents = self.get_alive_agents()
        # まだ占っていない人を抽出
        undivined = [
            agent for agent in alive_agents if agent not in self.divine_results
        ]
        if not undivined:
            print("未占い候補なし → ランダム選択")
            return random.choice(alive_agents)

        # 発言履歴を文字列化
        filtered = [t for t in self.talk_history if t.text not in ("OVER", "SKIP")]
        talk_history = "\n".join(f"{t.agent}: {t.text}" for t in filtered)

        # エージェント番号マップ作成
        agent_map = {f"Agent[{i+1:02d}]": name for i, name in enumerate(undivined)}
        agent_list_str = "\n".join(f"{v}（{k}）" for k, v in agent_map.items())

        # プロンプト組み立て
        prompt = (
            f"あなたは人狼ゲームの占い師役です。以下はこれまでの発言履歴です：\n"
            f"{talk_history}\n"
            f"まだ占っていないプレイヤーは以下の通りです：\n{agent_list_str}\n"
            "この中から最適な占い対象を一人選び、その理由も日本語で簡潔に説明してください。\n"
            "出力は「Agent[xx]」または名前のみでお願いします。"
            "例: Agent[03]を占います。理由は発言が少ないからです。"
            "例: ベンジャミンに占います。理由は発言が少ないからです。"
        )

        try:
            # result = call_o4mini_http(user_prompt=prompt, system_prompt="256文字以内で簡潔に回答してください。")
            model = "gpt-3.5-turbo"  # "gpt-4o-mini"
            result = call_openai_llm(
                prompt, temperature=1.0, max_tokens=256, model=model
            )
            print(f"LLM出力（占い候補）: {result}")

            import re

            # Agent[xx]形式があれば優先
            m = re.search(r"(Agent\[\d+\])", result)
            if m and m.group(1) in agent_map:
                chosen = agent_map[m.group(1)]
                print(f"マッチ: {m.group(1)} → {chosen}")
                return chosen

            # 名前直接マッチ
            for name in undivined:
                if name in result:
                    print(f"名前マッチ: {name}")
                    return name

            print("LLMから有効な占い対象が取れず")
        except Exception as e:
            print(f"LLM呼び出し失敗: {e}")
