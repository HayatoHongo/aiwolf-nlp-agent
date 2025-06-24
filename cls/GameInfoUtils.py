from typing import Literal


class DivineResult:
    agent: int
    day: int
    target: int
    result: str


class VoteHist:
    agent: int
    day: int
    target: int


class TalkHist:
    agent: int
    day: int
    idx: int
    text: str
    turn: int


class StatusMap(dict):
    # "1"等のエージェント番号ごとの生死状態
    agent_num: Literal["ALIVE", "DEAD"]
