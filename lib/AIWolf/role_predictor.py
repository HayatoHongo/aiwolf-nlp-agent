from collections import Counter, defaultdict
from typing import DefaultDict, List, Set, Tuple, Union

import numpy as np
from cls import GameInfo, GameSetting, Role
from lib.AIWolf import Assignment
from lib.SortedSet import SortedSet

from .score_matrix import ScoreMatrix

# from Util import Util


class RolePredictor:
    # 保持しておく役職の割り当ての数
    # これを超えたら評価の低いものから削除する
    ASSIGNMENT_NUM = 100
    ADDITIONAL_ASSIGNMENT_NUM = 100

    assignments_set: Set[Assignment]
    prob_all: DefaultDict[str, DefaultDict[Role, float]]

    def get_initail_assignment(self) -> np.ndarray:
        # 役職の割り当ての初期値を設定する
        # 5人村なら [Role.VILLAGER, Role.VILLAGER,
        # Role.SEER, Role.POSSESSED, Role.WEREWOLF] のような感じ
        # todo: np.array をやめる (List にする？)
        assignment = np.array([Role.UNC] * self.N, dtype=Role)

        # すでにわかっている役職を埋める (自分自身+人狼なら仲間の人狼)
        for agent, role in self.game_info.roleMap.items():
            assignment[int(self.agent_list.index(agent))] = role

        # 残りの役職を収納するキュー
        rest_roles = []
        for role, num in self.game_setting.roleNumMap.items():
            # self.assignment に num 個だけ role を追加する
            # すでに埋めた役職の分は除く (人狼なら3、それ以外なら1)
            if role == self.game_info.roleMap[str(self.game_info.agent)]:
                num -= len(self.game_info.roleMap)
            for i in range(num):
                rest_roles.append(role)

        # 残りの役職を埋める
        for i in range(self.N):
            if assignment[i] == Role.UNC:
                assignment[i] = rest_roles.pop(0)

        return assignment

    def __init__(
        self,
        game_info: GameInfo,
        game_setting: GameSetting,
        _player: str,
        _score_matrix: ScoreMatrix,
    ) -> None:
        self.game_setting = game_setting
        self.game_info = game_info
        self.N = game_setting.playerNum
        self.M = len(game_info.existingRoleList)
        self.player = _player
        self.me = _player.index
        self.agent_list = sorted(list(game_info.statusMap.keys()))
        # assignments は現在保持している Assignment の SortedSet (C++ の std::set みたいなもの)
        # assignments_set はこれまでに作成した Assignment の集合 (リストから外れても保持しておく)
        self.assignments: SortedSet = SortedSet()
        self.assignments_set = set()
        self.score_matrix = _score_matrix
        # すでに役職がわかっているエージェント(自分と人狼仲間)は固定する
        self.fixed_positions = [
            int(self.agent_list.index(agent)) for agent in self.game_info.roleMap.keys()
        ]
        self.prob_all: DefaultDict[str, DefaultDict[Role, float]] = None

        assignment = self.get_initail_assignment()

        # assignment のすべての並び替えを列挙する
        # 5人村はすべて列挙する
        for p in unique_permutations(assignment):
            self.assignments.add(
                Assignment(game_info, game_setting, _player.index, np.copy(p))
            )
        self.getProbAll()

    def agent_to_index(self, agent_name: str) -> int:
        """エージェント名をインデックス（0ベース）に変換"""
        return self.agent_list.index(agent_name)

    def index_to_agent(self, index: int) -> str:
        """インデックス（0ベース）をエージェント名に変換"""
        return self.agent_list[index]

    # すべての割り当ての評価値を計算する
    def update(
        self, game_info: GameInfo, game_setting: GameSetting, timeout: int = 40
    ) -> None:

        self.game_info = game_info
        # Util.debug_print("len(self.assignments)1:\t", len(self.assignments))
        # Util.start_timer("RolePredictor.update")

        # if len(self.assignments) == 0:
        #     self.addAssignments(game_info, game_setting, timeout=timeout//3)

        # assignments の評価値を更新
        # 逆順にして評価値の高いものから更新する
        for assignment in list(reversed(self.assignments)):
            # assignment を変更するので一度削除して、評価した後に再度追加する
            # res = self.assignments.discard(assignment)
            self.assignments.discard(assignment)
            assignment.evaluate(self.score_matrix)
            if assignment.score != -float("inf"):
                self.assignments.add(assignment)
            # if Util.timeout("RolePredictor.update", timeout):
            #     break
        # Util.debug_print("len(self.assignments)2:\t", len(self.assignments))
        # ここで確率の更新をしてキャッシュする
        self.getProbAll()
        print(f"[DEBUG][RolePredictor] after update: prob_all={self.prob_all}")

    # def addAssignments(self, game_info: GameInfo,
    #                   game_setting: GameSetting, timeout: int = 40) -> None:
    #     if self.N == 5: # 5人村ならすべて列挙しているので、追加する必要はない
    #         return

    #     # 新しい割り当てを追加する
    #     # Util.start_timer("RolePredictor.addAssignments")
    #     for _ in range(self.ADDITIONAL_ASSIGNMENT_NUM):
    #         self.addAssignment(game_info, game_setting)
    #         # if Util.timeout("RolePredictor.addAssignments", timeout):
    #         #     break

    def addAssignment(self, game_info: GameInfo, game_setting: GameSetting) -> None:
        if (len(self.assignments) < self.ASSIGNMENT_NUM) or (np.random.rand() < 0.1):
            # 割り当てが少ない場合は初期割り当てをシャッフルして追加する (多様性確保のため)
            # そうでなくても、10%の確率で初期割り当てをシャッフルして追加する (遺伝的アルゴリズムでいう突然変異)
            base = self.get_initail_assignment()
            times = self.N
        else:
            # 既にある割り当てからランダムに1つ選んで少しだけシャッフルして追加する
            assignment_idx = np.random.randint(len(self.assignments))
            base = self.assignments[assignment_idx].assignment
            times = min(
                self.N,
                # 基本的に1~3程度の小さな値 (正規分布を使用)
                int(abs(np.random.normal(scale=0.2) * self.N)) + 1,
            )

        # 指定回数シャッフルする
        assignment = Assignment(game_info, game_setting, self.player, np.copy(base))
        assignment.shuffle(times, self.fixed_positions)

        # すでにある割り当てと同じなら追加しない
        if assignment in self.assignments_set:
            return

        # 評価値を計算
        assignment.evaluate(self.score_matrix)

        # 確率 0 の割り当ては追加しない
        if assignment.score == -float("inf"):
            return

        # 割り当て数が超過していたら、スコアの低いものから削除する
        while len(self.assignments) > self.ASSIGNMENT_NUM:
            self.assignments.pop(0)

        # 割り当て数が足りなかったら追加する
        # 丁度だった場合は、すでにある割り当てよりもスコアが高ければ追加する
        if len(self.assignments) < self.ASSIGNMENT_NUM:
            self.assignments.add(assignment)
        elif assignment.score > self.assignments[0].score:
            self.assignments.discard(self.assignments[0])
            self.assignments.add(assignment)

        # 割り当て重複チェック用のセットに追加
        self.assignments_set.add(assignment)

    # 各プレイヤーの役職の確率を表す二次元配列を返す
    # (実際には defaultdict[str, defaultdict[Role, float]])
    # p[a][r] はエージェント a が役職 r である確率 (a: str, r: Role)
    def getProbAll(self) -> DefaultDict[str, DefaultDict[Role, float]]:

        # ndarray だと添字に Role を使えないので、defaultdict[Role, float] の配列を使う
        probs = defaultdict(lambda: defaultdict(float))

        if len(self.assignments) > 0:
            # 各割り当ての相対確率を計算する
            relative_prob = np.zeros(len(self.assignments))
            sum_relative_prob = 0
            # スコアは対数尤度なので、exp して相対確率に変換する
            for i, assignment in enumerate(self.assignments):
                try:
                    # スコアが大きいとオーバーフローするので10で割る
                    relative_prob[i] = np.exp(assignment.score / 10)
                except RuntimeWarning:
                    # Util.error_print("OverflowError", assignment.score)
                    # print("OverflowError", assignment.score)
                    pass
                sum_relative_prob += relative_prob[i]
            # 各割り当ての相対確率を確率に変換する
            assignment_prob = np.zeros(len(self.assignments))
            for i in range(len(assignment_prob)):
                assignment_prob[i] = relative_prob[i] / sum_relative_prob
            # 各プレイヤーの役職の確率を計算する
            for i, assignment in enumerate(self.assignments):
                for a in self.game_info.existingRoleList:
                    probs[a][assignment[a]] += assignment_prob[i]
        else:
            # 割り当てがない場合は、個々のスコアから確率を計算する
            for agent in self.game_info.existingRoleList:
                # 相対確率を計算する
                relative_probs = defaultdict(lambda: defaultdict(float))
                sum_relative_prob = 0.0
                for role in self.game_info.existingRoleList:
                    score = self.score_matrix.get_score(agent, role, agent, role)
                    relative_probs[agent][role] = np.exp(score / 10)
                    sum_relative_prob += relative_probs[agent][role]
                # 確率に変換する
                for role in self.game_info.existingRoleList:
                    # すべての役職の確率が 0 だった場合は、すべての役職の確率を等分する
                    if sum_relative_prob == 0.0:
                        role_num = len(self.game_info.existingRoleList)
                        probs[agent][role] = 1.0 / role_num
                    else:
                        probs[agent][role] = (
                            relative_probs[agent][role] / sum_relative_prob
                        )

        self.prob_all = probs
        print(f"[DEBUG][RolePredictor] getProbAll: prob_all={self.prob_all}")
        return probs

    # キャッシュがあればそれを返し、なければ getProbAll を呼んで返す
    def getProbCache(self) -> DefaultDict[str, DefaultDict[Role, float]]:
        return self.prob_all if self.prob_all is not None else self.getProbAll()

    # i 番目のプレイヤーが役職 role である確率を返す
    # 毎回 getProbAll を呼ぶのは無駄なので、キャッシュしたものを使う
    def getProb(self, agent, role: Role) -> float:
        if type(agent) is int:
            agent = self.game_info.existingRoleList[agent]
        p = self.getProbCache()
        return p[agent][role]

    # 指定された役職である確率が最も高いプレイヤーを返す
    # 確率が threshold 未満の場合は AGENT_NONE を返す
    # returns_prob が True の場合は、プレイヤーと確率を返す
    def chooseMostLikely(
        self,
        role: Role,
        existingRoleList: List[str],
        threshold: float = 0.0,
        returns_prob: bool = False,
    ) -> Union[str, Tuple[str, float], None]:
        print(f"[DEBUG][ScoreMatrix] chooseMostLikely: {self.score_matrix}")

        if len(existingRoleList) == 0:
            return None

        p = self.getProbCache()
        ret_agent = existingRoleList[0]
        mx_score = 0
        for a in existingRoleList:
            score = p[a][role]
            if score > mx_score:
                ret_agent = a
                mx_score = score
        if returns_prob:
            if mx_score < threshold:
                return None, mx_score
            else:
                return ret_agent, mx_score
        else:
            if mx_score < threshold:
                return None
            else:
                return ret_agent

    # 指定された役職である確率が最も低いプレイヤーを返す
    def chooseLeastLikely(self, role: Role, existingRoleList: List[str]) -> str:
        if len(existingRoleList) == 0:
            return None

        p = self.getProbCache()
        ret_agent = existingRoleList[0]
        for a in existingRoleList:
            if p[a][role] < p[ret_agent][role]:
                ret_agent = a
        return ret_agent

    def getMostLikelyRole(self, agent: str) -> Role:
        p = self.getProbCache()
        ret_role = Role.VILLAGER
        for r in list(Role):
            if p[agent][r] > p[agent][ret_role]:
                ret_role = r
        return ret_role

    # 狂人が生存しているか推測する
    def estimate_alive_possessed(self, threshold=0.5) -> bool:
        p = self.getProbCache()
        all = 0
        alive = 0
        for i in range(self.N):
            agent = self.agent_list[i]
            all += p[agent][Role.POSSESSED]
            # 型安全なキーアクセス
            agent_key = str(agent)
            if (
                agent_key in self.game_info.statusMap
                and self.game_info.statusMap[agent_key] == "ALIVE"
            ):
                alive += p[agent][Role.POSSESSED]
        return alive / all > threshold if all > 0 else False

    # (役職である確率＋係数＊勝率)が最も高いプレイヤーを返す←不採用
    def chooseStrongLikely(
        self, role: Role, existingRoleList: List[str], coef: float = 0.0
    ) -> str:
        if len(existingRoleList) == 0:
            return None
        p = self.getProbCache()
        mx_score = 0
        ret_agent = existingRoleList[0]
        for a in existingRoleList:
            score = p[a][role]
            # score += coef * Util.win_rate[a]
            if score > mx_score:
                mx_score = score
                ret_agent = a
        return ret_agent


def unique_permutations(lst, fixed_positions=None):
    if fixed_positions is None:
        fixed_positions = {}

    counter = Counter(lst)
    for pos, val in fixed_positions.items():
        counter[val] -= 1

    unique_elems = list(counter.keys())
    counts = list(counter.values())
    n = len(lst)

    def _unique_permutations(current_perm, remaining_counts, current_length):
        if current_length == n:
            yield tuple(current_perm)
            return
        if current_length in fixed_positions:
            yield from _unique_permutations(
                current_perm + [fixed_positions[current_length]],
                remaining_counts,
                current_length + 1,
            )
        else:
            for idx, (elem, count) in enumerate(zip(unique_elems, remaining_counts)):
                if count > 0:
                    remaining_counts[idx] -= 1
                    yield from _unique_permutations(
                        current_perm + [elem], remaining_counts, current_length + 1
                    )
                    remaining_counts[idx] += 1

    return _unique_permutations([], counts, 0)
