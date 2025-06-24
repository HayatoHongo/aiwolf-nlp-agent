from dataclasses import dataclass

from .GameInfoUtils import DivineResult, StatusMap, TalkHist, VoteHist


@dataclass
class GameInfo:
    agent: int
    attackVoteList: list
    attackedAgent: int
    cursedFox: int
    day: int
    divineResult: DivineResult
    englishTalkList: list[TalkHist]
    executedAgent: int
    existingRoleList: list[str]
    guardedAgent: int
    lastDeadAgentList: list[int]
    # 空？
    latestAttackVoteList: list
    latestExecutedAgent: int
    latestVoteList: list[VoteHist]
    mediumResult: None
    # エージェントごとの残りの発話回数？
    remainTalkMap: dict
    # エージェントごとの残りの囁き回数？
    remainWhisperMap: dict
    # 終了時以外は自分の役職のみ
    roleMap: dict
    statusMap: StatusMap
    talkList: list[TalkHist]
    voteList: list[VoteHist]
    # whisperは使われていないため基本的に空
    whisperList: list
