from __future__ import annotations

from aiwolf_nlp_common.protocol import Packet
from aiwolf_nlp_common.protocol.setting.map import RoleNumInfo, RoleNumMap


class gameSettingConverter:
    @classmethod
    def get_game_setting_dict(cls, protocol: Packet) -> dict | None:
        game_setting: dict = dict()

        if protocol.setting is None:
            return None

        game_setting["enableNoAttack"] = protocol.setting.is_enable_no_attack
        game_setting["enableNoExecution"] = protocol.setting.is_enable_no_attack
        game_setting["maxAttackRevote"] = protocol.setting.max_attack_revote
        game_setting["maxRevote"] = protocol.setting.max_revote
        game_setting["maxSkip"] = protocol.setting.max_skip
        game_setting["maxTalk"] = protocol.setting.max_talk
        game_setting["maxTalkTurn"] = protocol.setting.max_talk_turn
        game_setting["maxWhisper"] = protocol.setting.max_whisper
        game_setting["maxWhisperTurn"] = protocol.setting.max_whisper_turn
        game_setting["playerNum"] = protocol.setting.player_num
        game_setting["roleNumMap"] = cls.get_role_num_map(
            role_num_map=protocol.setting.role_num_map
        )
        game_setting["talkOnFirstDay"] = protocol.setting.is_talk_on_first_day
        game_setting["responseTimeout"] = protocol.setting.response_timeout
        game_setting["actionTimeout"] = protocol.setting.action_timeout
        game_setting["voteVisible"] = protocol.setting.is_vote_visible

        return game_setting

    @classmethod
    def get_role_num_map(cls, role_num_map: RoleNumMap) -> dict:
        result: dict = dict()

        role_num_map_element: RoleNumInfo
        for role_num_map_element in role_num_map:
            result[role_num_map_element.role.en] = role_num_map_element.allocated_count

        return result
