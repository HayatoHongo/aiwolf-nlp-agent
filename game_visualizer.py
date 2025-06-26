#!/usr/bin/env python3
"""五人ゲームの可視化ツール（LLMエージェント対応版）"""

import sys
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

# 添加src目录到Python路径（只在本文件生效）
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from agent.villager import Villager
from agent.seer import Seer
from agent.werewolf import Werewolf
from agent.possessed import Possessed
from aiwolf_nlp_common.packet import Role

class GamePhase(Enum):
    """ゲームフェーズ"""
    INITIALIZE = "初期化"
    DAY_START = "昼開始"
    TALK = "発言"
    VOTE = "投票"
    NIGHT_START = "夜開始"
    WHISPER = "囁き"
    DIVINE = "占い"
    ATTACK = "襲撃"
    DAY_FINISH = "昼終了"
    GAME_FINISH = "ゲーム終了"

class Team(Enum):
    """陣営"""
    VILLAGER = "村人陣営"
    WEREWOLF = "人狼陣営"

@dataclass
class PlayerWrap:
    """LLMエージェントのラッパー"""
    name: str
    role: str
    team: Team
    agent: object
    is_alive: bool = True
    vote_target: Optional[str] = None
    divine_target: Optional[str] = None
    attack_target: Optional[str] = None
    talk_history: List[str] = None
    
    def __post_init__(self):
        if self.talk_history is None:
            self.talk_history = []

@dataclass
class GameState:
    """ゲーム状態"""
    day: int = 1
    phase: GamePhase = GamePhase.INITIALIZE
    players: Dict[str, PlayerWrap] = None
    game_log: List[str] = None
    winner: Optional[Team] = None
    
    def __post_init__(self):
        if self.players is None:
            self.players = {}
        if self.game_log is None:
            self.game_log = []

class FivePlayerGameVisualizer:
    """五人ゲーム可視化クラス（LLMエージェント対応）"""
    
    def __init__(self):
        self.game_state = GameState()
        self.setup_five_player_game()
    
    def setup_five_player_game(self):
        """五人ゲームの初期設定（LLMエージェント）"""
        # 五人ゲームの役職設定
        roles = [
            ("Agent[01]", "村人", Team.VILLAGER, Villager, Role.VILLAGER),
            ("Agent[02]", "占い師", Team.VILLAGER, Seer, Role.SEER),
            ("Agent[03]", "村人", Team.VILLAGER, Villager, Role.VILLAGER),
            ("Agent[04]", "人狼", Team.WEREWOLF, Werewolf, Role.WEREWOLF),
            ("Agent[05]", "狂人", Team.WEREWOLF, Possessed, Role.POSSESSED)
        ]
        config = {
            "path": {
                "random_talk": "./resource/2019071_44011_AIWolfTalkLogs.txt"
            },
            "agent": {
                "kill_on_timeout": False
            },
            "log": {
                "console_output": True,
                "file_output": False,
                "output_dir": "./log",
                "level": "INFO"
            }
        }
        for name, role_str, team, agent_class, role_enum in roles:
            agent = agent_class(config, name, "test_game", role_enum)
            self.game_state.players[name] = PlayerWrap(name, role_str, team, agent)
    
    def log_event(self, message: str):
        """イベントをログに記録"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.game_state.game_log.append(log_entry)
        print(log_entry)
    
    def display_game_status(self):
        """ゲーム状態を表示"""
        print("\n" + "="*60)
        print(f"五人ゲーム - 日目: {self.game_state.day} | フェーズ: {self.game_state.phase.value}")
        print("="*60)
        
        # プレイヤー状態を表示
        print("\n【プレイヤー状態】")
        for name, player in self.game_state.players.items():
            status = "生存" if player.is_alive else "死亡"
            print(f"  {name}: {player.role} ({player.team.value}) - {status}")
        
        # 陣営別生存者数
        villager_alive = sum(1 for p in self.game_state.players.values() 
                           if p.team == Team.VILLAGER and p.is_alive)
        werewolf_alive = sum(1 for p in self.game_state.players.values() 
                           if p.team == Team.WEREWOLF and p.is_alive)
        
        print(f"\n【陣営別生存者数】")
        print(f"  村人陣営: {villager_alive}人")
        print(f"  人狼陣営: {werewolf_alive}人")
        
        # 勝利条件チェック
        if villager_alive == 0:
            self.game_state.winner = Team.WEREWOLF
            print(f"\n🎉 人狼陣営の勝利！")
        elif werewolf_alive == 0:
            self.game_state.winner = Team.VILLAGER
            print(f"\n🎉 村人陣営の勝利！")
        
        print("="*60)
    
    def simulate_talk_phase(self):
        """発言フェーズ（LLMエージェント）"""
        self.game_state.phase = GamePhase.TALK
        self.log_event("=== 発言フェーズ開始 ===")
        
        # 各生存プレイヤーの发言（调用agent.talk）
        for name, player in self.game_state.players.items():
            if player.is_alive:
                # 构造虚拟packet，设置talk_history
                player.agent.talk_history = []
                for n, p in self.game_state.players.items():
                    if p.is_alive:
                        player.agent.talk_history.extend([
                            type('Talk', (), dict(agent=n, text=th, day=self.game_state.day, turn=0))
                            for th in p.talk_history[-3:]
                        ])
                talk = player.agent.talk()
                player.talk_history.append(talk)
                self.log_event(f"{name} ({player.role}): {talk}")
                time.sleep(0.5)
    
    def simulate_vote_phase(self):
        """投票フェーズ（LLMエージェント）"""
        self.game_state.phase = GamePhase.VOTE
        self.log_event("=== 投票フェーズ開始 ===")
        
        # 各生存プレイヤーの投票（调用agent.vote）
        votes = {}
        for name, player in self.game_state.players.items():
            if player.is_alive:
                # 构造虚拟packet，设置talk_history
                player.agent.talk_history = []
                for n, p in self.game_state.players.items():
                    if p.is_alive:
                        player.agent.talk_history.extend([
                            type('Talk', (), dict(agent=n, text=th, day=self.game_state.day, turn=0))
                            for th in p.talk_history[-3:]
                        ])
                # 设置info.status_map
                class Info:
                    pass
                info = Info()
                info.status_map = {n: ("ALIVE" if p.is_alive else "DEAD") for n, p in self.game_state.players.items()}
                player.agent.info = info
                vote_result = player.agent.vote()
                player.vote_target = vote_result
                votes[name] = vote_result
                self.log_event(f"{name} ({player.role}) の投票先: {vote_result}")
                time.sleep(0.3)
        
        # 投票结果を集計
        vote_counts = {}
        for target in votes.values():
            # 只统计Agent[xx]部分
            import re
            m = re.search(r"(Agent\[\d+\])", target)
            if m:
                t = m.group(1)
                vote_counts[t] = vote_counts.get(t, 0) + 1
        
        # 最多票のプレイヤーを処刑
        if vote_counts:
            executed = max(vote_counts.items(), key=lambda x: x[1])[0]
            self.game_state.players[executed].is_alive = False
            self.log_event(f"🚨 {executed} が処刑されました！")
    
    def simulate_night_phase(self):
        """夜フェーズ（LLMエージェント）"""
        self.game_state.phase = GamePhase.NIGHT_START
        self.log_event("=== 夜フェーズ開始 ===")
        
        # 占い師の占い
        seer = None
        for name, player in self.game_state.players.items():
            if player.role == "占い師" and player.is_alive:
                seer = player
                break
        
        if seer:
            # 设置info.status_map
            class Info:
                pass
            info = Info()
            info.status_map = {n: ("ALIVE" if p.is_alive else "DEAD") for n, p in self.game_state.players.items()}
            seer.agent.info = info
            target = seer.agent.divine()
            seer.divine_target = target
            self.log_event(f"{seer.name} (占い師) が {target} を占いました")
            time.sleep(0.5)
        
        # 人狼の襲撃
        werewolf = None
        for name, player in self.game_state.players.items():
            if player.role == "人狼" and player.is_alive:
                werewolf = player
                break
        
        if werewolf:
            # 设置info.status_map
            class Info:
                pass
            info = Info()
            info.status_map = {n: ("ALIVE" if p.is_alive else "DEAD") for n, p in self.game_state.players.items()}
            werewolf.agent.info = info
            target = werewolf.agent.attack()
            werewolf.attack_target = target
            # 只取Agent[xx]部分
            import re
            m = re.search(r"(Agent\[\d+\])", target)
            if m:
                t = m.group(1)
                if t in self.game_state.players:
                    self.game_state.players[t].is_alive = False
                    self.log_event(f"🐺 {werewolf.name} (人狼) が {t} を襲撃しました！")
            else:
                # fallback
                if target in self.game_state.players:
                    self.game_state.players[target].is_alive = False
                    self.log_event(f"🐺 {werewolf.name} (人狼) が {target} を襲撃しました！")
            time.sleep(0.5)
    
    def simulate_game(self):
        """ゲーム全体をシミュレート"""
        self.log_event("五人ゲーム（LLMエージェント）開始！")
        self.display_game_status()
        
        day = 1
        while not self.game_state.winner and day <= 10:  # 最大10日
            self.game_state.day = day
            self.log_event(f"\n=== {day}日目開始 ===")
            
            # 昼フェーズ
            self.simulate_talk_phase()
            self.simulate_vote_phase()
            
            # 勝利条件チェック
            self.display_game_status()
            if self.game_state.winner:
                break
            
            # 夜フェーズ
            self.simulate_night_phase()
            
            # 勝利条件チェック
            self.display_game_status()
            if self.game_state.winner:
                break
            
            day += 1
            time.sleep(1)  # 日付の間隔
        
        # ゲーム終了
        self.game_state.phase = GamePhase.GAME_FINISH
        self.log_event("=== ゲーム終了 ===")
        
        if self.game_state.winner:
            self.log_event(f"🏆 最終結果: {self.game_state.winner.value}の勝利！")
        else:
            self.log_event("🏆 最終結果: 引き分け")
        
        self.display_final_summary()
    
    def display_final_summary(self):
        """最終サマリーを表示"""
        print("\n" + "="*60)
        print("【ゲーム最終サマリー】")
        print("="*60)
        
        print("\n【全プレイヤーの役職】")
        for name, player in self.game_state.players.items():
            status = "生存" if player.is_alive else "死亡"
            print(f"  {name}: {player.role} ({player.team.value}) - {status}")
        
        print(f"\n【勝利陣営】: {self.game_state.winner.value if self.game_state.winner else '引き分け'}")
        print(f"【ゲーム日数】: {self.game_state.day}日")
        
        print("\n【ゲームログ】")
        for log in self.game_state.game_log[-30:]:  # 最後の30行を表示
            print(f"  {log}")
        
        print("="*60)

def main():
    """メイン関数"""
    print("五人ゲーム可視化ツール（LLMエージェント対応）")
    print("AIWolf 五人ゲームの LLM エージェント対戦をシミュレーションします")
    visualizer = FivePlayerGameVisualizer()
    visualizer.simulate_game()

if __name__ == "__main__":
    main() 