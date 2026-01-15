import numpy as np
from cls import GameInfo, GameSetting, Role, Status
from lib.AIWolf.score_matrix import ScoreMatrix


class Assignment:

    def __init__(
        self,
        game_info: GameInfo,
        game_setting: GameSetting,
        index: str,
        _assignment: np.ndarray,
    ) -> None:
        self.N = game_setting.playerNum
        self.M = len(game_info.existingRoleList)
        self.me = index
        self.score = 0.0
        self.assignment = _assignment
        self.hash = hash(self)
        self.gameInfo = game_info
        self.agent_list = sorted(list(game_info.statusMap.keys()))

    def __str__(self) -> str:
        m = ""
        for r in self.assignment:
            m += r.name[0] + ", "
        return m

    def __eq__(self, o: object) -> bool:
        return self.score == o.score and self.hash == o.hash

    def __hash__(self) -> int:
        return hash(tuple(self.assignment))

    def __lt__(self, other: object) -> bool:
        if self.score == other.score:
            return self.hash < other.hash
        else:
            return self.score < other.score

    def __le__(self, other: object) -> bool:
        return self < other or self == other

    def agent_to_index(self, agent_name: str) -> int:
        """エージェント名をインデックス（0ベース）に変換"""
        return self.agent_list.index(agent_name)

    def index_to_agent(self, index: int) -> str:
        """インデックス（0ベース）をエージェント名に変換"""
        return self.agent_list[index]

    # 外部クラスから assignment.assignment[i] ではなく assignment[i] でアクセスできるようにする
    def __getitem__(self, agent) -> Role:
        if type(agent) is str:
            if agent in list(vars(Role).keys()):
                return agent
            return self.assignment[self.agent_list.index(agent)]
        elif type(agent) is int:
            return self.assignment[agent]
        else:
            return self.assignment[0]

    # 役職の割り当ての評価値を計算する
    def evaluate(self, score_matrix: ScoreMatrix, debug=False) -> float:
        score = 0.0

        # 既に負けているような割り当ての評価値は-inf
        if not debug:
            werewolf_num = 0
            alive_agent_num = 0
            game_info = self.gameInfo
            for i in range(self.N):
                agent = self.index_to_agent(i)
                status = game_info.statusMap[agent]
                if status == Status.ALIVE:
                    alive_agent_num += 1
                    if self.assignment[i] == Role.WEREWOLF:
                        werewolf_num += 1

            if werewolf_num >= alive_agent_num / 2:
                return -float("inf")

        for i in range(self.N):
            for j in range(self.N):
                # if i == j:
                #     continue
                # self.score += np.random.rand()
                score += score_matrix.get_score(
                    i, self.assignment[i], j, self.assignment[j]
                )
                # if self.score == -float("inf"):
                #     return self.score
                if (
                    debug
                    and abs(
                        score_matrix.get_score(
                            i, self.assignment[i], j, self.assignment[j]
                        )
                    )
                    >= 4.5
                ):
                    print(
                        "score[",
                        i,
                        "\t",
                        self.assignment[i],
                        "\t",
                        j,
                        "\t",
                        self.assignment[j],
                        "\t] = ",
                        round(
                            score_matrix.get_score(
                                i, self.assignment[i], j, self.assignment[j]
                            ),
                            2,
                        ),
                    )
        self.score = score

        return self.score

    # エージェント i とエージェント j の役職を入れ替える
    def swap(self, i: int, j: int) -> None:
        self.assignment[i], self.assignment[j] = self.assignment[j], self.assignment[i]
        self.hash = hash(self)

    # リストをシャッフルする
    # fixed_positions で指定した位置はシャッフルしない
    def shuffle(self, times=-1, fixed_positions=[]):
        times = times if times != -1 else self.N

        a = np.arange(self.N)
        a = np.setdiff1d(a, np.array(fixed_positions))

        for _ in range(times):
            i = np.random.randint(len(a))
            j = np.random.randint(len(a))
            i = a[i]
            j = a[j]
            self.assignment[i], self.assignment[j] = (
                self.assignment[j],
                self.assignment[i],
            )

        self.hash = hash(self)
