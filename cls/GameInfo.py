from dataclasses import dataclass, field
from typing import Optional

from .GameInfoUtils import DivineResult, StatusMap, TalkHist, VoteHist


@dataclass
class GameInfo:
    # 必須フィールド（デフォルト値なし）
    agent: str
    day: int
    statusMap: StatusMap

    # リスト型フィールド（空リストをデフォルト値に）
    attackVoteList: list = field(default_factory=list)
    englishTalkList: list[TalkHist] = field(default_factory=list)
    #5人人狼はこれで確定なので、デフォルト値を設定
    existingRoleList: list[str] = field(default_factory=lambda: ["VILLAGER", "VILLAGER", "SEER", "POSSESSED", "WEREWOLF"])
    lastDeadAgentList: list[str] = field(default_factory=list)
    latestAttackVoteList: list = field(default_factory=list)
    talkList: list[TalkHist] = field(default_factory=list)
    voteList: list[VoteHist] = field(default_factory=list)
    whisperList: list = field(default_factory=list)

    # 辞書型フィールド（空辞書をデフォルト値に）
    remainTalkMap: dict = field(default_factory=dict)
    remainWhisperMap: dict = field(default_factory=dict)
    roleMap: dict = field(default_factory=dict)

    # None可能フィールド（Noneをデフォルト値に）
    attackedAgent: Optional[str] = None
    cursedFox: Optional[str] = None
    executedAgent: Optional[str] = None
    guardedAgent: Optional[str] = None
    latestExecutedAgent: Optional[int] = None
    divineResult: Optional[DivineResult] = None
    mediumResult: Optional[None] = None

    def __post_init__(self):
        """データクラス初期化後に辞書をVoteHistオブジェクトに変換"""
        # voteListが辞書のリストの場合、VoteHistオブジェクトに変換
        if self.voteList and isinstance(self.voteList[0], dict):
            converted_votes = []
            for vote_dict in self.voteList:
                vote_hist = VoteHist()
                vote_hist.agent = vote_dict["agent"]
                vote_hist.day = vote_dict["day"]
                vote_hist.target = vote_dict["target"]
                converted_votes.append(vote_hist)
            self.voteList = converted_votes

    @property
    def latestVoteList(self):
        if not self.voteList:
            return []

        current_day = self.day
        # 現在の日の投票のみをフィルタリング
        current_day_votes = [v for v in self.voteList if v.day == current_day]

        # 各エージェントの最新投票のみを保持（再投票対応）
        latest_votes = {}
        for vote in current_day_votes:
            latest_votes[vote.agent] = vote

        return list(latest_votes.values())
