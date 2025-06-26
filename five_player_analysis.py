#!/usr/bin/env python3
"""五人ゲーム分析ツール"""

import sys
import os
import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
from enum import Enum
import statistics

# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

class Team(Enum):
    """陣営"""
    VILLAGER = "村人陣営"
    WEREWOLF = "人狼陣営"

@dataclass
class GameResult:
    """ゲーム結果"""
    winner: Team
    day_count: int
    executed_players: List[str]
    attacked_players: List[str]
    divine_results: List[Tuple[str, str, str]]  # (占い師, 対象, 結果)
    game_log: List[str]

class FivePlayerGameAnalyzer:
    """五人ゲーム分析クラス"""
    
    def __init__(self):
        self.results: List[GameResult] = []
        self.villager_wins = 0
        self.werewolf_wins = 0
        self.total_games = 0
    
    def setup_five_player_game(self) -> Dict[str, Tuple[str, Team]]:
        """五人ゲームの初期設定"""
        roles = {
            "Agent[01]": ("村人", Team.VILLAGER),
            "Agent[02]": ("占い師", Team.VILLAGER),
            "Agent[03]": ("村人", Team.VILLAGER),
            "Agent[04]": ("人狼", Team.WEREWOLF),
            "Agent[05]": ("狂人", Team.WEREWOLF)
        }
        return roles
    
    def simulate_single_game(self, game_id: int) -> GameResult:
        """単一ゲームをシミュレート"""
        roles = self.setup_five_player_game()
        players = {name: {"role": role, "team": team, "alive": True} 
                  for name, (role, team) in roles.items()}
        
        game_log = [f"ゲーム {game_id} 開始"]
        executed_players = []
        attacked_players = []
        divine_results = []
        day_count = 0
        
        while day_count < 10:  # 最大10日
            day_count += 1
            game_log.append(f"=== {day_count}日目開始 ===")
            
            # 昼フェーズ
            # 発言フェーズ（簡略化）
            alive_players = [name for name, data in players.items() if data["alive"]]
            for name in alive_players:
                role = players[name]["role"]
                if role == "占い師":
                    game_log.append(f"{name} (占い師): 占い結果を報告します")
                elif role == "人狼":
                    game_log.append(f"{name} (人狼): 村人として発言します")
                elif role == "狂人":
                    game_log.append(f"{name} (狂人): 村人として発言します")
                else:
                    game_log.append(f"{name} (村人): 村人として発言します")
            
            # 投票フェーズ
            votes = {}
            for name in alive_players:
                target = self.generate_vote_for_player(name, players, alive_players)
                votes[name] = target
                game_log.append(f"{name} の投票先: {target}")
            
            # 投票結果集計
            vote_counts = defaultdict(int)
            for target in votes.values():
                vote_counts[target] += 1
            
            if vote_counts:
                executed = max(vote_counts.items(), key=lambda x: x[1])[0]
                players[executed]["alive"] = False
                executed_players.append(executed)
                game_log.append(f"🚨 {executed} が処刑されました")
            
            # 勝利条件チェック
            villager_alive = sum(1 for data in players.values() 
                               if data["team"] == Team.VILLAGER and data["alive"])
            werewolf_alive = sum(1 for data in players.values() 
                               if data["team"] == Team.WEREWOLF and data["alive"])
            
            if villager_alive == 0:
                game_log.append("🎉 人狼陣営の勝利！")
                return GameResult(Team.WEREWOLF, day_count, executed_players, 
                                attacked_players, divine_results, game_log)
            elif werewolf_alive == 0:
                game_log.append("🎉 村人陣営の勝利！")
                return GameResult(Team.VILLAGER, day_count, executed_players, 
                                attacked_players, divine_results, game_log)
            
            # 夜フェーズ
            # 占い師の占い
            seer = None
            for name, data in players.items():
                if data["role"] == "占い師" and data["alive"]:
                    seer = name
                    break
            
            if seer:
                target = self.generate_divine_target(seer, players)
                target_role = players[target]["role"]
                divine_results.append((seer, target, target_role))
                game_log.append(f"{seer} (占い師) が {target} を占いました: {target_role}")
            
            # 人狼の襲撃
            werewolf = None
            for name, data in players.items():
                if data["role"] == "人狼" and data["alive"]:
                    werewolf = name
                    break
            
            if werewolf:
                target = self.generate_attack_target(werewolf, players)
                players[target]["alive"] = False
                attacked_players.append(target)
                game_log.append(f"🐺 {werewolf} (人狼) が {target} を襲撃しました")
            
            # 勝利条件再チェック
            villager_alive = sum(1 for data in players.values() 
                               if data["team"] == Team.VILLAGER and data["alive"])
            werewolf_alive = sum(1 for data in players.values() 
                               if data["team"] == Team.WEREWOLF and data["alive"])
            
            if villager_alive == 0:
                game_log.append("🎉 人狼陣営の勝利！")
                return GameResult(Team.WEREWOLF, day_count, executed_players, 
                                attacked_players, divine_results, game_log)
            elif werewolf_alive == 0:
                game_log.append("🎉 村人陣営の勝利！")
                return GameResult(Team.VILLAGER, day_count, executed_players, 
                                attacked_players, divine_results, game_log)
        
        # 引き分け
        game_log.append("🏆 引き分け")
        return GameResult(None, day_count, executed_players, attacked_players, 
                         divine_results, game_log)
    
    def generate_vote_for_player(self, player_name: str, players: Dict, alive_players: List[str]) -> str:
        """プレイヤーの投票先を生成"""
        candidates = [name for name in alive_players if name != player_name]
        if not candidates:
            return player_name
        
        role = players[player_name]["role"]
        
        if role == "占い師":
            # 占い師は怪しいプレイヤーに投票
            return random.choice(candidates)
        elif role == "人狼":
            # 人狼は真の占い師候補に投票
            seer_candidates = [name for name, data in players.items() 
                             if data["role"] == "占い師" and data["alive"] and name != player_name]
            if seer_candidates:
                return random.choice(seer_candidates)
            return random.choice(candidates)
        elif role == "狂人":
            # 狂人は真の占い師候補に投票
            seer_candidates = [name for name, data in players.items() 
                             if data["role"] == "占い師" and data["alive"] and name != player_name]
            if seer_candidates:
                return random.choice(seer_candidates)
            return random.choice(candidates)
        else:  # 村人
            # 村人は怪しいプレイヤーに投票
            return random.choice(candidates)
    
    def generate_divine_target(self, seer: str, players: Dict) -> str:
        """占い対象を生成"""
        alive_players = [name for name, data in players.items() 
                        if data["alive"] and name != seer]
        return random.choice(alive_players) if alive_players else seer
    
    def generate_attack_target(self, werewolf: str, players: Dict) -> str:
        """襲撃対象を生成"""
        alive_players = [name for name, data in players.items() 
                        if data["alive"] and name != werewolf]
        return random.choice(alive_players) if alive_players else werewolf
    
    def run_analysis(self, num_games: int = 100):
        """分析を実行"""
        print(f"五人ゲーム分析開始 - {num_games}ゲーム実行")
        print("="*60)
        
        start_time = time.time()
        
        for i in range(num_games):
            result = self.simulate_single_game(i + 1)
            self.results.append(result)
            
            if result.winner == Team.VILLAGER:
                self.villager_wins += 1
            elif result.winner == Team.WEREWOLF:
                self.werewolf_wins += 1
            
            self.total_games += 1
            
            # 進捗表示
            if (i + 1) % 10 == 0:
                progress = (i + 1) / num_games * 100
                print(f"進捗: {i + 1}/{num_games} ({progress:.1f}%)")
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"\n分析完了！実行時間: {execution_time:.2f}秒")
        self.display_analysis_results()
    
    def display_analysis_results(self):
        """分析結果を表示"""
        print("\n" + "="*60)
        print("【五人ゲーム分析結果】")
        print("="*60)
        
        # 基本統計
        print(f"\n【基本統計】")
        print(f"総ゲーム数: {self.total_games}")
        print(f"村人陣営勝利: {self.villager_wins}回 ({self.villager_wins/self.total_games*100:.1f}%)")
        print(f"人狼陣営勝利: {self.werewolf_wins}回 ({self.werewolf_wins/self.total_games*100:.1f}%)")
        
        # ゲーム日数分析
        day_counts = [result.day_count for result in self.results if result.winner]
        if day_counts:
            print(f"\n【ゲーム日数分析】")
            print(f"平均ゲーム日数: {statistics.mean(day_counts):.2f}日")
            print(f"最短ゲーム日数: {min(day_counts)}日")
            print(f"最長ゲーム日数: {max(day_counts)}日")
            print(f"中央値: {statistics.median(day_counts)}日")
        
        # 役職別分析
        print(f"\n【役職別分析】")
        
        # 処刑されたプレイヤーの役職分析
        executed_roles = defaultdict(int)
        for result in self.results:
            for executed in result.executed_players:
                if executed == "Agent[01]":
                    executed_roles["村人"] += 1
                elif executed == "Agent[02]":
                    executed_roles["占い師"] += 1
                elif executed == "Agent[03]":
                    executed_roles["村人"] += 1
                elif executed == "Agent[04]":
                    executed_roles["人狼"] += 1
                elif executed == "Agent[05]":
                    executed_roles["狂人"] += 1
        
        print("【処刑されたプレイヤーの役職】")
        for role, count in executed_roles.items():
            percentage = count / self.total_games * 100
            print(f"  {role}: {count}回 ({percentage:.1f}%)")
        
        # 襲撃されたプレイヤーの役職分析
        attacked_roles = defaultdict(int)
        for result in self.results:
            for attacked in result.attacked_players:
                if attacked == "Agent[01]":
                    attacked_roles["村人"] += 1
                elif attacked == "Agent[02]":
                    attacked_roles["占い師"] += 1
                elif attacked == "Agent[03]":
                    attacked_roles["村人"] += 1
                elif attacked == "Agent[04]":
                    attacked_roles["人狼"] += 1
                elif attacked == "Agent[05]":
                    attacked_roles["狂人"] += 1
        
        print("\n【襲撃されたプレイヤーの役職】")
        for role, count in attacked_roles.items():
            percentage = count / self.total_games * 100
            print(f"  {role}: {count}回 ({percentage:.1f}%)")
        
        # 占い結果分析
        print(f"\n【占い結果分析】")
        seer_targets = defaultdict(int)
        seer_results = defaultdict(int)
        
        for result in self.results:
            for seer, target, target_role in result.divine_results:
                seer_targets[target] += 1
                seer_results[target_role] += 1
        
        print("【占い対象】")
        for target, count in seer_targets.items():
            percentage = count / self.total_games * 100
            print(f"  {target}: {count}回 ({percentage:.1f}%)")
        
        print("\n【占い結果】")
        for role, count in seer_results.items():
            percentage = count / self.total_games * 100
            print(f"  {role}: {count}回 ({percentage:.1f}%)")
        
        # 戦略効果分析
        print(f"\n【戦略効果分析】")
        
        # 占い師の効果
        total_divines = 0
        divine_werewolf = 0
        for result in self.results:
            for seer, target, target_role in result.divine_results:
                total_divines += 1
                if target_role == "人狼":
                    divine_werewolf += 1
        
        divine_werewolf_rate = divine_werewolf / total_divines * 100 if total_divines > 0 else 0
        print(f"占い師の占いで人狼を引き当てた割合: {divine_werewolf_rate:.1f}%")
        
        # 人狼の襲撃効果
        werewolf_effectiveness = 0
        for result in self.results:
            if result.winner == Team.WEREWOLF:
                # 人狼陣営が勝利した場合、占い師を襲撃したかチェック
                for attacked in result.attacked_players:
                    if attacked == "Agent[02]":  # 占い師
                        werewolf_effectiveness += 1
                        break
        
        werewolf_effectiveness_rate = werewolf_effectiveness / self.werewolf_wins * 100 if self.werewolf_wins > 0 else 0
        print(f"人狼の占い師襲撃率: {werewolf_effectiveness_rate:.1f}%")
        
        print("="*60)
    
    def save_detailed_results(self, filename: str = "five_player_analysis_results.txt"):
        """詳細結果をファイルに保存"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("五人ゲーム詳細分析結果\n")
            f.write("="*60 + "\n\n")
            
            for i, result in enumerate(self.results):
                f.write(f"ゲーム {i+1}:\n")
                f.write(f"  勝利陣営: {result.winner.value if result.winner else '引き分け'}\n")
                f.write(f"  ゲーム日数: {result.day_count}日\n")
                f.write(f"  処刑されたプレイヤー: {', '.join(result.executed_players)}\n")
                f.write(f"  襲撃されたプレイヤー: {', '.join(result.attacked_players)}\n")
                f.write(f"  占い結果: {result.divine_results}\n")
                f.write("\n")
        
        print(f"詳細結果を {filename} に保存しました")

def main():
    """メイン関数"""
    print("五人ゲーム分析ツール")
    print("AIWolf 五人ゲームの戦略分析を実行します")
    
    analyzer = FivePlayerGameAnalyzer()
    
    # 分析実行
    num_games = 100  # 100ゲーム実行
    analyzer.run_analysis(num_games)
    
    # 詳細結果保存
    analyzer.save_detailed_results()

if __name__ == "__main__":
    main() 