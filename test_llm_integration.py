#!/usr/bin/env python3
"""LLM集成测试脚本"""

import sys
import os

# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

def test_llm_integration():
    """测试LLM集成"""
    print("=== LLM集成测试 ===")
    
    # 检查.env文件是否存在
    if not os.path.exists('.env'):
        print("❌ .env文件不存在")
        print("请复制 env.example 为 .env 并填入你的 DeepSeek API Key")
        return False
    
    try:
        from utils.llm_api import call_deepseek_llm
        
        # 测试简单的prompt
        test_prompt = "あなたはAI人狼ゲームの村人です。自然な日本語で一言発言してください。"
        
        print("🔄 正在调用 DeepSeek API...")
        result = call_deepseek_llm(test_prompt, temperature=0.7, max_tokens=32)
        
        print(f"✅ API调用成功！")
        print(f"结果: {result}")
        return True
        
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        return False
    except Exception as e:
        print(f"❌ API调用失败: {e}")
        return False

def test_agent_with_llm():
    """测试agent的LLM集成"""
    print("\n=== Agent LLM集成测试 ===")
    
    try:
        from agent.villager import Villager
        from aiwolf_nlp_common.packet import Role
        
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
        
        # 创建村人agent
        villager = Villager(config, "Agent[01]", "test_game", Role.VILLAGER)
        
        # 模拟一些发言历史
        from aiwolf_nlp_common.packet import Talk
        villager.talk_history = [
            Talk(idx=1, day=1, turn=1, agent="Agent[02]", text="私は占い師です"),
            Talk(idx=2, day=1, turn=2, agent="Agent[03]", text="村人として頑張ります"),
        ]
        
        # 测试LLM生成的发言
        print("🔄 测试LLM生成的发言...")
        talk_result = villager.talk()
        print(f"发言结果: {talk_result}")
        
        # 模拟存活玩家
        villager.info = type('Info', (), {
            'status_map': {
                'Agent[01]': 'ALIVE',
                'Agent[02]': 'ALIVE',
                'Agent[03]': 'ALIVE'
            }
        })()
        
        # 测试LLM生成的投票
        print("🔄 测试LLM生成的投票...")
        vote_result = villager.vote()
        print(f"投票结果: {vote_result}")
        
        print("✅ Agent LLM集成测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ Agent LLM集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("DeepSeek LLM集成测试")
    print("="*50)
    
    # 测试基本LLM集成
    llm_ok = test_llm_integration()
    
    if llm_ok:
        # 测试agent集成
        agent_ok = test_agent_with_llm()
        
        if agent_ok:
            print("\n🎉 所有测试通过！LLM集成成功！")
        else:
            print("\n⚠️  LLM集成成功，但agent集成有问题")
    else:
        print("\n❌ LLM集成失败，请检查配置")

if __name__ == "__main__":
    main() 