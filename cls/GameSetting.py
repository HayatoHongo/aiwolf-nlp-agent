from dataclasses import dataclass

from .Role import Role


@dataclass
class GameSetting:
    enableNoAttack: bool
    enableNoExecution: bool
    maxAttackRevote: int
    maxRevote: int
    maxSkip: int
    maxTalk: int
    maxTalkTurn: int
    maxWhisper: int
    maxWhisperTurn: int
    playerNum: int
    roleNumMap: dict[Role:int]
    talkOnFirstDay: bool
    voteVisible: bool

    enableRoleRequest: bool = False
    randomSeed: int = 0
    timeLimit: int = 0
    validateUtterance: bool = False
    votableInFirstDay: bool = False
    whisperBeforeRevote: bool = False
