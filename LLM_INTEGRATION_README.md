# DeepSeek LLM 集成说明

## 概述

本项目已集成 DeepSeek LLM API，用于生成 AIWolf 游戏中 agent 的发言和投票决策。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置 API Key

1. 复制环境变量模板文件：
```bash
cp env.example .env
```

2. 编辑 `.env` 文件，填入你的 DeepSeek API Key：
```
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

## 功能特性

### 1. LLM 生成的发言 (talk)
- 所有角色的发言都由 DeepSeek LLM 生成
- 基于当前游戏状态和发言历史
- 生成自然、符合角色特点的日语发言

### 2. LLM 生成的投票决策 (vote)
- 投票目标由 LLM 分析后选择
- 包含投票理由说明
- 格式：`"Agent[03]に投票します。理由は発言が少ないからです。"`

### 3. 错误处理
- API 调用失败时自动回退到随机策略
- 网络超时和格式错误都有相应处理

## 使用方法

### 测试 LLM 集成
```bash
python test_llm_integration.py
```

### 运行游戏可视化
```bash
python game_visualizer.py
```

### 运行批量分析
```bash
python five_player_analysis.py
```

## 代码结构

```
src/
├── utils/
│   └── llm_api.py          # DeepSeek API 调用工具
├── agent/
│   ├── agent.py            # 基类，包含 LLM 生成的 talk/vote
│   ├── villager.py         # 村人（使用基类 LLM 生成）
│   ├── seer.py            # 占い師（保留 divine 方法）
│   ├── werewolf.py        # 人狼（保留 attack/whisper 方法）
│   └── possessed.py       # 狂人（使用基类 LLM 生成）
```

## 自定义 Prompt

你可以在 `src/agent/agent.py` 中修改 `talk()` 和 `vote()` 方法的 prompt 模板：

```python
def talk(self) -> str:
    prompt = (
        f"あなたはAI人狼ゲームの{role}です。以下はこれまでの発言履歴です：\n"
        f"{talk_history}\n"
        "今、あなたが自然な日本語で一言発言してください。"
    )
    return call_deepseek_llm(prompt, temperature=0.7, max_tokens=64)
```

## 注意事项

1. **API 费用**：每次 talk/vote 都会调用 API，请注意控制使用量
2. **响应时间**：LLM 调用需要网络时间，可能影响游戏响应速度
3. **Token 限制**：prompt 长度会影响 API 费用，建议控制历史记录长度
4. **错误处理**：网络问题时会自动回退到随机策略

## 故障排除

### API Key 错误
```
ValueError: DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置
```
解决：检查 `.env` 文件中的 API Key 是否正确

### 网络错误
```
DeepSeek API 调用失败: Connection timeout
```
解决：检查网络连接，或增加 timeout 时间

### 响应格式错误
```
DeepSeek API 响应格式错误: 'choices'
```
解决：检查 API 响应格式，可能需要更新解析逻辑

## 扩展功能

### 添加更多上下文信息
可以在 prompt 中加入：
- 投票历史
- 占卜结果
- 角色分布信息
- 游戏天数

### 支持其他 LLM
可以修改 `llm_api.py` 来支持其他 LLM 服务：
- OpenAI GPT
- Azure OpenAI
- 百度文心一言
- 阿里通义千问

## 示例输出

### 发言示例
```
Agent[01] (村人): 占い師の結果を信じて行動しましょう。
Agent[02] (占い師): 私は占い師です。村を守るために頑張ります！
Agent[04] (人狼): 慎重に判断しましょう。
```

### 投票示例
```
Agent[01] (村人) の投票先: Agent[03]に投票します。理由は発言が少ないからです。
Agent[02] (占い師) の投票先: Agent[04]に投票します。理由は占いで人狼と判定されたからです。
``` 