from __future__ import annotations

from .map.role_num_map import RoleNumMap


class Setting:
    role_num_map: RoleNumMap
    max_talk: int
    max_talk_turn: int
    max_whisper: int
    max_whisper_turn: int
    max_skip: int
    is_enable_no_attack: bool
    is_vote_visible: bool
    is_talk_on_first_day: bool
    response_timeout: int
    action_timeout: int
    max_revote: int
    max_attack_revote: int
    player_num: int

    def __str__(self) -> str:
        return (
            f"{self.role_num_map}\n\n"
            f"MaxTalk: {self.max_talk}\n"
            f"MaxTalkTurn: {self.max_talk_turn}\n"
            f"MaxWhisper: {self.max_whisper}\n"
            f"MaxWhisperTurn: {self.max_whisper_turn}\n"
            f"MaxSkip: {self.max_skip}\n"
            f"isEnableNoAttack: {self.is_enable_no_attack}\n"
            f"isVoteVisible: {self.is_vote_visible}\n"
            f"isTalkOnFirstDay: {self.is_talk_on_first_day}\n"
            f"ResponseTimeOut: {self.response_timeout}\n"
            f"ActionTimeOut: {self.action_timeout}\n"
            f"MaxReVote: {self.max_revote}\n"
            f"MaxAttackReVote: {self.max_attack_revote}\n"
            f"PlayerNum: {self.player_num}\n"
        )

    def __init__(self, value: dict | None = None) -> None:
        if value is not None:
            # 新形式のサーバーデータに対応
            self.role_num_map = RoleNumMap(value=value.get("role_num_map", {}))

            # Talk設定の取得
            talk_settings = value.get("talk", {})
            talk_max_count = talk_settings.get("max_count", {})
            self.max_talk = talk_max_count.get("per_agent", 5)
            self.max_talk_turn = talk_max_count.get("per_day", 20)
            self.max_skip = talk_settings.get("max_skip", 0)

            # Whisper設定の取得
            whisper_settings = value.get("whisper", {})
            whisper_max_count = whisper_settings.get("max_count", {})
            self.max_whisper = whisper_max_count.get("per_agent", 5)
            self.max_whisper_turn = whisper_max_count.get("per_day", 20)

            # Vote設定の取得
            vote_settings = value.get("vote", {})
            self.max_revote = vote_settings.get("max_count", 1)

            # AttackVote設定の取得
            attack_vote_settings = value.get("attack_vote", {})
            self.max_attack_revote = attack_vote_settings.get("max_count", 1)
            self.is_enable_no_attack = attack_vote_settings.get(
                "allow_no_target", False
            )

            # Timeout設定の取得
            timeout_settings = value.get("timeout", {})
            self.response_timeout = timeout_settings.get("response", 120000) // 1000
            self.action_timeout = timeout_settings.get("action", 60000) // 1000

            # その他の設定
            self.player_num = value.get("agent_count", 5)
            self.is_vote_visible = value.get("vote_visibility", False)
            self.is_talk_on_first_day = (
                True  # デフォルト値（新サーバーには対応項目なし）
            )

    def update(self, value: dict | None) -> None:
        self.__init__(value)
