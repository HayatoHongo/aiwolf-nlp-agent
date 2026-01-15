import inspect
from collections import defaultdict
from typing import DefaultDict, Dict, List, Set

import numpy as np
import pandas as pd
from cls import DivineResult, GameInfo, GameSetting, Role, Side, Species


class ScoreMatrix:
    seer_co: List[str]
    rtoi: DefaultDict[Role, int]
    hidden_seers: Set[str] = set()  # クラス変数。1セット内で共有される。

    def __init__(
        self, game_info: GameInfo, game_setting: GameSetting, index: str, role: str
    ) -> None:
        self.game_info = game_info
        self.game_setting = game_setting
        self.N = game_setting.playerNum
        self.M = len(game_info.existingRoleList)
        self.agent_list = sorted(list(game_info.statusMap.keys()))
        # score_matrix[エージェント1, 役職1, エージェント2, 役職2]: エージェント1が役職1、エージェント2が役職2である相対確率の対数
        # -infで相対確率は0になる
        self.score_matrix: np.ndarray = np.zeros((self.N, self.M, self.N, self.M))
        self.me = index  # 自身のエージェント
        self.my_role = role  # 自身の役職
        self.rtoi = defaultdict(lambda: -1)
        for r, i in {
            Role.VILLAGER: 0,
            Role.SEER: 1,
            Role.POSSESSED: 2,
            Role.WEREWOLF: 3,
        }.items():
            self.rtoi[r] = i
        self.seer_co_count = 0
        self.seer_co = []

        for a, r in game_info.roleMap.items():
            if r != Role.ANY and r != Role.UNC:
                self.set_score(a, r, a, r, float("inf"))

    def update(self, game_info: GameInfo) -> None:
        self.game_info = game_info

    # スコアは相対確率の対数を表す
    # スコア = log(相対確率)
    # スコアの付け方
    # 確定情報: +inf または -inf
    # 非確定情報: 有限値 最大を10で統一する
    # 書くときは100を最大として、相対確率に直すときに1/10倍する

    # スコアの取得
    # agent1, agent2: str or int
    # role1, role2: Role or int

    def get_score(self, agent1: str, role1: Role, agent2: str, role2: Role) -> float:
        # agent1, agent2は人名strまたはintインデックス
        i = self.agent_list.index(agent1) if isinstance(agent1, str) else agent1
        ri = self.rtoi[role1] if isinstance(role1, str) else role1
        j = self.agent_list.index(agent2) if isinstance(agent2, str) else agent2
        rj = self.rtoi[role2] if isinstance(role2, str) else role2

        if ri >= self.M or rj >= self.M or ri < 0 or rj < 0:
            return -float("inf")
        return self.score_matrix[i, ri, j, rj]

    # スコアの設定
    # agent1, agent2: str or int
    # role1, role2: Role or int
    def set_score(
        self, agent1: str, role1: Role, agent2: str, role2: Role, score: float
    ) -> None:
        i = self.agent_list.index(agent1) if isinstance(agent1, str) else agent1
        ri = self.rtoi[role1] if isinstance(role1, str) else role1
        j = self.agent_list.index(agent2) if isinstance(agent2, str) else agent2
        rj = self.rtoi[role2] if isinstance(role2, str) else role2
        # print(i, ri, j, rj, score)
        print(type(i), type(ri), type(j), type(rj), type(score))

        if ri >= self.M or rj >= self.M or ri < 0 or rj < 0:
            return

        if score == float("inf"):
            self.score_matrix[i, :, j, :] = -float("inf")
            self.score_matrix[i, ri, j, rj] = 0
        else:
            if score > 100:
                self.score_matrix[i, ri, j, rj] = 100
            elif score < -100:
                self.score_matrix[i, ri, j, rj] = -100
            else:
                self.score_matrix[i, ri, j, rj] = score

    # スコアの加算
    # agent1, agent2: str or int
    # role1, rold2: Role, int, Species, Side or List
    def add_score(
        self, agent1: str, role1: Role, agent2: str, role2: Role, score: float
    ) -> None:
        if abs(score) >= 5:
            caller = inspect.stack()[1]
            if caller.function != "add_scores":
                print("add_score:\t", caller.function, caller.lineno, "\t", score)

        if role1 == Side():
            role1 = self.get_role_list(role1)
        if role2 == Side():
            role2 = self.get_role_list(role2)
        if role1 == Species():
            if role1 == Species.HUMAN:
                role1 = self.get_role_list("WHITE") + [Role.POSSESSED]
            elif role1 == Species.WEREWOLF:
                role1 = Role.WEREWOLF
            else:
                print("role1 is not Species.HUMAN or Species.WEREWOLF")
        if role2 == Species():
            if role2 == Species.HUMAN:
                role2 = self.get_role_list("WHITE") + [Role.POSSESSED]
            elif role2 == Species.WEREWOLF:
                role2 = Role.WEREWOLF
            else:
                print("role2 is not Species.HUMAN or Species.WEREWOLF")
        if type(role1) is not list:
            role1 = [role1]
        if type(role2) is not list:
            role2 = [role2]
        for r1 in role1:
            for r2 in role2:
                modified_score = self.get_score(agent1, r1, agent2, r2) + score
                self.set_score(agent1, r1, agent2, r2, modified_score)

    def get_role_list(self, side: Side) -> List[Role]:
        if side == Side.WHITE:
            return [Role.VILLAGER, Role.SEER]
        elif side == Side.BLACK:
            return [Role.WEREWOLF, Role.POSSESSED]
        else:
            raise ValueError("side is not Side.WHITE or Side.BLACK")

    # スコアの加算をまとめて行う
    def add_scores(self, agent: str, score_dict: Dict[Role, float]) -> None:
        # 加算するスコアが大きい場合はどの関数から呼ばれたかを表示
        if min(score_dict.values()) <= -5 or max(score_dict.values()) >= 5:
            caller = inspect.stack()[1]
            print(
                "add_scores:\t",
                caller.function,
                caller.lineno,
                "\t",
                {str(r)[5]: s for r, s in score_dict.items()},
            )

        for key, value in score_dict.items():
            self.add_score(agent, key, agent, key, value)

    # --------------- 公開情報から推測する ---------------
    # 襲撃結果を反映
    def killed(
        self, game_info: GameInfo, game_setting: GameSetting, agent: str
    ) -> None:
        self.update(game_info)
        # 襲撃されたエージェントは人狼ではない
        self.set_score(agent, Role.WEREWOLF, agent, Role.WEREWOLF, -float("inf"))

    # 投票行動を反映
    def vote(
        self,
        game_info: GameInfo,
        game_setting: GameSetting,
        voter: str,
        target: str,
        day: int,
    ) -> None:
        self.update(game_info)
        # N = self.N
        # 自分の投票行動は無視
        if voter == self.me:
            return
        # ---------- 5人村 ----------
        # 2日目でゲームの勝敗が決定しているので、1日目の投票行動の反映はほとんど意味ない
        # 投票者が村陣営で、投票対象が人狼である確率を上げる
        self.add_score(voter, Role.VILLAGER, target, Role.WEREWOLF, +0.1)
        self.add_score(voter, Role.SEER, target, Role.WEREWOLF, +0.3)

    # --------------- 公開情報から推測する ---------------

    # --------------- 自身の能力の結果から推測する：確定情報なのでスコアを +inf or -inf にする ---------------
    # 自分の占い結果を反映（結果騙りは考慮しない）
    def my_divined(
        self,
        game_info: GameInfo,
        game_setting: GameSetting,
        target: str,
        species: Species,
    ) -> None:
        self.update(game_info)
        # 黒結果
        if species == Species.WEREWOLF:
            # 人狼であることが確定しているので、人狼のスコアを+inf(実際には他の役職のスコアを-inf(相対確率0)にする)
            self.set_score(target, Role.WEREWOLF, target, Role.WEREWOLF, +float("inf"))
        # 白結果
        elif species == Species.HUMAN:
            # 人狼でないことが確定しているので、人狼のスコアを-inf(相対確率0)にする
            self.set_score(target, Role.WEREWOLF, target, Role.WEREWOLF, -float("inf"))
        else:
            # 万が一不確定(Species.UNC, Species.ANY)の場合
            print("my_divined: species is not Species.WEREWOLF or Species.HUMAN")

    # --------------- 自身の能力の結果から推測する ---------------

    # --------------- 他の人の発言から推測する：確定情報ではないので有限の値を加減算する ---------------
    # 他者のCOを反映
    def talk_co(
        self,
        game_info: GameInfo,
        game_setting: GameSetting,
        talker: str,
        role: Role,
        day: int,
        turn: int,
    ) -> None:
        self.update(game_info)
        my_role = self.my_role
        role_map = self.game_info.roleMap
        # 自分と仲間の人狼のCOは無視
        if talker == self.me or (
            talker in role_map and role_map[talker] == Role.WEREWOLF
        ):
            return

        # ---------- 5人村 ----------
        # TODO: 占いCOのスコアをCO回数をもとに変更する
        score_df = _load_score_df("CO")
        score_df = score_df.replace("", "0")
        for i in range(self.N):
            if talker == i + 1:
                continue
            df = score_df[score_df.role == role]
            if i + 1 == self.me:
                df = df[df.own_role == my_role]
            for j in range(len(df)):
                tds = df.iloc[j]
                for role in role_map:
                    talker_score = tds[role]
                    self.add_score(i + 1, tds.own_role, talker, role, int(talker_score))

    # 投票意思を反映
    # それほど重要ではないため、スコアの更新は少しにする
    def talk_will_vote(
        self,
        game_info: GameInfo,
        game_setting: GameSetting,
        talker: str,
        target: str,
        day: int,
        turn: int,
        will_vote_reports,
    ) -> None:
        self.update(game_info)
        my_role = self.my_role
        role_map = self.game_info.roleMap
        # will_vote = self.player.will_vote_reports
        # 自分の投票意思は無視
        if talker == self.me:
            return
        # 同じ対象に二回目以降の投票意思は無視
        if will_vote_reports[talker] == target:
            return
        # 初日初ターンは無視
        if day == 1 and turn <= 1:
            return
        # ---------- 5人村 ----------
        score_df = _load_score_df("VOTE")
        score_df = score_df.replace("", "0")
        for i in range(self.N):
            if talker == i + 1:
                continue
            if target == i + 1:
                df = score_df[(score_df.target == "own")]
            else:
                df = score_df[(score_df.target == "else")]
            if i + 1 == self.me:
                df = df[df.own_role == my_role]
            for j in range(len(df)):
                tds = df.iloc[j]
                for role in role_map:
                    talker_score, target_score = tds[role]
                    self.add_score(i + 1, tds.own_role, talker, role, int(talker_score))
                    self.add_score(i + 1, tds.own_role, target, role, int(target_score))

    # Basketにないため、後で実装する→実装しない
    def talk_estimate(
        self,
        game_info: GameInfo,
        game_setting: GameSetting,
        talker: str,
        target: str,
        role: Role,
        day: int,
        turn: int,
    ) -> None:
        self.update(game_info)
        my_role = self.my_role
        role_map = self.game_info.roleMap
        # 自分のESTIMATEは無視
        if talker == self.me:
            return
        score_df = _load_score_df("ESTIMATE")
        score_df = score_df.replace("", "0")
        for i in range(self.N):
            if talker == i + 1:
                continue
            if target == i + 1:
                df = score_df[(score_df.target == "own") & (score_df.role == role)]
            else:
                df = score_df[(score_df.target == "else") & (score_df.role == role)]
            if i + 1 == self.me:
                df = df[df.own_role == my_role]
            for j in range(len(df)):
                tds = df.iloc[j]
                for role in role_map:
                    talker_score, target_score = tds[role]
                    self.add_score(i + 1, tds.own_role, talker, role, int(talker_score))
                    self.add_score(i + 1, tds.own_role, target, role, int(target_score))

    def talk_suspect(
        self,
        game_info: GameInfo,
        game_setting: GameSetting,
        talker: str,
        target: str,
        day: int,
        turn: int,
    ) -> None:
        self.update(game_info)
        my_role = self.my_role
        role_map = self.game_info.roleMap

        score_df = _load_score_df("SUSPECT")
        score_df = score_df.replace("", "0")
        for i in range(self.N):
            if talker == i + 1:
                continue
            if target == i + 1:
                df = score_df[(score_df.target == "own")]
            else:
                df = score_df[(score_df.target == "else")]
            if i + 1 == self.me:
                df = df[df.own_role == my_role]
            for j in range(len(df)):
                tds = df.iloc[j]
                for role in role_map:
                    talker_score, target_score = tds[role]
                    self.add_score(i + 1, tds.own_role, talker, role, int(talker_score))
                    self.add_score(i + 1, tds.own_role, target, role, int(target_score))

    # 他者の占い結果を反映
    # 条件分岐は、N人村→myrole→白黒結果→targetが自分かどうか
    def talk_divined(
        self,
        game_info: GameInfo,
        comingout_map: DefaultDict[str, Role],
        talker: str,
        target: str,
        species: Species,
        day: int,
        turn: int,
        divination_reports: list[DivineResult],
    ) -> None:
        self.update(game_info)
        my_role = self.my_role
        role_map = self.game_info.roleMap
        # 自分と仲間の人狼の結果は無視
        if talker == self.me or (
            talker in role_map and role_map[talker] == Role.WEREWOLF
        ):
            return
        # CO の時点で占い師以外の村人陣営の可能性を0にしているが、COせずに占い結果を出した場合のためにここでも同じ処理を行う
        self.add_scores(talker, {Role.VILLAGER: -100})
        # すでに同じ相手に対する占い結果がある場合は無視
        # ただし、結果が異なる場合は、人狼・狂人の確率を上げる
        for report in divination_reports:
            if report.agent == talker and report.target == target:
                if report.result == species:
                    return
                else:
                    print("同じ相手に対して異なる占い結果を出した時")
                    self.add_scores(talker, {Role.POSSESSED: +100, Role.WEREWOLF: +100})
                    return
        # ---------- 5人村 ----------
        score_df = _load_score_df("DIVINED")
        score_df = score_df.replace("", "0")
        for i in range(self.N):
            if talker == i + 1:
                continue
            if target == i + 1:
                df = score_df[
                    (score_df.target == "own") & (score_df.species == species)
                ]
            else:
                df = score_df[
                    (score_df.target == "else") & (score_df.species == species)
                ]
            if i + 1 == self.me:
                df = df[df.own_role == my_role]
            for j in range(len(df)):
                tds = df.iloc[j]
                for role in role_map:
                    talker_score, target_score = tds[role]
                    self.add_score(i + 1, tds.own_role, talker, role, int(talker_score))
                    self.add_score(i + 1, tds.own_role, target, role, int(target_score))

    # N日目の始めに推測する
    # COしているのに、噛まれていない違和感を反映する
    def Nth_day_start(self, game_info: GameInfo, game_setting: GameSetting) -> None:
        self.update(game_info)
        day: int = self.game_info.day
        my_role = self.my_role

        # if day <= 2 or len(game_info.last_dead_agent_list) == 0:
        #     return
        if day <= 2:
            return

        # 生存者数の推移(GJなし)：15→13→11→9→7→5
        # 3日目0GJ(11人)、4日目1GJ以下(14-day人以下)なら、採用
        alive_cnt: int = len(
            [val for val in self.game_info.statusMap.values() if val == "ALIVE"]
        )
        print("(day, alive_cnt) = ", day, alive_cnt)
        if (day == 3 and alive_cnt <= 11) or (day >= 4 and alive_cnt <= 14 - day):
            print("Nth_day_start: 採用")
            if my_role != Role.WEREWOLF:
                for agent, role in self.player.alive_comingout_map.items():
                    if role in [Role.SEER]:
                        self.add_scores(agent, {Role.POSSESSED: +1, Role.WEREWOLF: +3})


def _load_score_df(verb: str) -> pd.DataFrame:
    with open(f"data/{verb}_score.csv", "r") as f:
        contents = f.readlines()
    score_contents = [content.strip().split(",") for content in contents]
    score_df = pd.DataFrame(score_contents[2:], columns=score_contents[1])
    return score_df
