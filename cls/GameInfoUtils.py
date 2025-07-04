from typing import Literal


class DivineResult:
    agent: str
    day: int
    target: str
    result: str


class VoteHist:
    agent: str
    day: int
    target: str


class TalkHist:
    agent: str
    day: int
    idx: int
    text: str
    turn: int


class StatusMap(dict):
    # "1"等のエージェント番号ごとの生死状態
    agent_num: Literal["ALIVE", "DEAD"]
