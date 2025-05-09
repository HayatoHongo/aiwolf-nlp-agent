"""エージェントの基底クラスを定義するモジュール."""

from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING

from aiwolf_nlp_common.packet import Info, Packet, Request, Role, Setting, Status, Talk
from config.prompt_templates import (
    PROMPT_STATEMENT,
    PROMPT_WHISPER,
    PROMPT_VOTE,
    PROMPT_VOTE_WOLF,
    PROMPT_DIVINE,
)
from utils.history_manager import HistoryBuffer
from utils.agent_logger import AgentLogger
from utils.stoppable_thread import StoppableThread
import openai
from openai import Client, OpenAIError

client = Client()
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if TYPE_CHECKING:
    from collections.abc import Callable


class Agent:
    """エージェントの基底クラス."""

    def __init__(
        self,
        config: dict,
        name: str,
        game_id: str,
        role: Role,
    ) -> None:
        """エージェントの初期化を行う."""
        self.config = config
        self.agent_name = name
        self.agent_logger = AgentLogger(config, name, game_id)
        self.request: Request | None = None
        self.info: Info | None = None
        self.setting: Setting | None = None
        self.talk_history: list[Talk] = []
        self.whisper_history: list[Talk] = []
        self.role = role
        self.history = HistoryBuffer()
        self.game_day: int = 0

        self.comments: list[str] = []
        with Path.open(
            Path(str(self.config["path"]["random_talk"])),
            encoding="utf-8",
        ) as f:
            self.comments = f.read().splitlines()

    @property
    def role_ja(self) -> str:
        m = {
            Role.VILLAGER: "村人",
            Role.SEER: "占い師",
            Role.WEREWOLF: "人狼",
            Role.POSSESSED: "狂人",
            Role.BODYGUARD: "狩人",
            Role.MEDIUM: "霊媒師",
        }
        return m[self.role]

    @staticmethod
    def timeout(func: Callable) -> Callable:
        """アクションタイムアウトを設定するデコレータ."""

        def _wrapper(self, *args, **kwargs) -> str:  # noqa: ANN001, ANN002, ANN003
            res = ""

            def execute_with_timeout() -> None:
                nonlocal res
                try:
                    res = func(self, *args, **kwargs)
                except Exception as e:  # noqa: BLE001
                    res = e

            thread = StoppableThread(target=execute_with_timeout)
            thread.start()
            timeout_value = (
                self.setting.timeout.action
                if hasattr(self, "setting") and self.setting
                else 0
            ) // 1000
            if timeout_value > 0:
                thread.join(timeout=timeout_value)
                if thread.is_alive():
                    self.agent_logger.logger.warning(
                        "アクションがタイムアウトしました: %s",
                        self.request,
                    )
                    if bool(self.config["agent"]["kill_on_timeout"]):
                        thread.stop()
                        self.agent_logger.logger.warning(
                            "アクションを強制終了しました: %s",
                            self.request,
                        )
            else:
                thread.join()
            if isinstance(res, Exception):
                raise res
            return res

        return _wrapper

    @staticmethod
    def generate_statement(
        prompt_text: str,
        model: str | None = None,  # 型を少し広げる
        temperature: float = 0.7,
        max_tokens: int = 64,
    ) -> str:
        m = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        try:
            response = client.chat.completions.create(
                model=m,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは人狼知能コンテストのプレイヤーです。",
                    },
                    {"role": "user", "content": prompt_text},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except OpenAIError as e:
            print("OpenAIError:", e)
            return "…"

    def set_packet(self, packet: Packet) -> None:
        """パケット情報をセットする."""
        self.request = packet.request
        if packet.info:
            self.info = packet.info
        if packet.setting:
            self.setting = packet.setting
        if packet.talk_history:
            self.talk_history.extend(packet.talk_history)
        if packet.whisper_history:
            self.whisper_history.extend(packet.whisper_history)
        if self.request == Request.INITIALIZE:
            self.talk_history: list[Talk] = []
            self.whisper_history: list[Talk] = []
        self.agent_logger.logger.debug(packet)

    def update_game_info(self, packet: Packet) -> None:
        """ゲーム進行情報を更新し、トーク履歴も管理する."""
        # ゲームサーバから送られてきた「今日は何日目か」を保持
        if packet.info and packet.info.day is not None:
            self.game_day = packet.info.day
        # 新しいトークが届いたら履歴に追加
        if hasattr(packet, "talk") and packet.talk:
            self.history.add(packet.talk.text)
        # 既存の情報も更新
        self.set_packet(packet)

    def get_alive_agents(self) -> list[str]:
        """生存しているエージェントのリストを取得する."""
        if not self.info:
            return []
        return [k for k, v in self.info.status_map.items() if v == Status.ALIVE]

    def name(self) -> str:
        """名前リクエストに対する応答を返す."""
        return self.agent_name

    def initialize(self) -> None:
        """ゲーム開始リクエストに対する初期化処理を行う."""

    def daily_initialize(self) -> None:
        """昼開始リクエストに対する処理を行う."""

    def whisper(self) -> str:
        context = self.history.get_context()
        prompt = PROMPT_WHISPER.format(
            name=self.name, day=self.game_day, context=context
        )
        return self.generate_statement(prompt)

    def talk(self) -> str:
        alive = ", ".join(self.get_alive_agents())
        context = self.history.get_context()
        prompt = PROMPT_STATEMENT.format(
            day=self.game_day,
            role_ja=self.role_ja,
            alive_list=alive,
            context=context or "（まだ会話はありません）",
        )

        return Agent.generate_statement(prompt)

    def daily_finish(self) -> None:
        """昼終了リクエストに対する処理を行う."""

    def divine(self) -> str:
        """占いリクエストに対する応答を返す。LLMで最も怪しい生存者を選ぶ。"""
        alive_agents = [a for a in self.get_alive_agents() if a != self.agent_name]
        if not alive_agents:
            return self.agent_name  # フォールバック

        context = self.history.get_context() or "（まだ会話はありません）"
        alive = ", ".join(alive_agents)
        prompt = PROMPT_DIVINE.format(
            context=context,
            alive_list=alive,
        )
        # LLMで候補取得
        candidate = self.generate_statement(prompt).strip()
        # 生存者リストに含まれているかチェック
        if candidate not in alive_agents:
            candidate = random.choice(alive_agents)
        return candidate

    # 五人人狼では不要
    def guard(self) -> str:
        """護衛リクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def vote(self) -> str:
        """投票リクエストに対する応答を返す."""
        # 1) 生存者リストを文字列化
        alive = ", ".join(self.get_alive_agents())

        # 2) 会話履歴コンテキストを取得（空なら案内文を）
        context = self.history.get_context() or "（まだ会話はありません）"

        # 3) 陣営ごとにプロンプトを切り替え
        if self.role in [Role.WEREWOLF, Role.POSSESSED]:
            prompt_template = PROMPT_VOTE_WOLF  # 人狼陣営用プロンプト
        else:
            prompt_template = PROMPT_VOTE  # 市民陣営用プロンプト

        prompt = prompt_template.format(
            day=self.game_day,
            role_ja=self.role_ja,
            name=self.agent_name,
            alive_list=alive,
            context=context,
        )

        # 4) LLM 呼び出しで名前を得る
        candidate = self.generate_statement(prompt).strip()

        # 5) 誤答防止: 生存者リストに含まれているかチェック
        if candidate not in self.get_alive_agents():
            # 最も近い名前を選び直す（単純にランダムフォールバック）
            candidate = random.choice(self.get_alive_agents())

        return candidate

    def attack(self) -> str:
        """襲撃リクエストに対する応答を返す."""
        return random.choice(self.get_alive_agents())  # noqa: S311

    def finish(self) -> None:
        """ゲーム終了リクエストに対する処理を行う."""

    @timeout
    def action(self) -> str | None:  # noqa: C901, PLR0911
        """リクエストの種類に応じたアクションを実行する."""
        match self.request:
            case Request.NAME:
                return self.name()
            case Request.TALK:
                return self.talk()
            case Request.WHISPER:
                return self.whisper()
            case Request.VOTE:
                return self.vote()
            case Request.DIVINE:
                return self.divine()
            case Request.GUARD:
                return self.guard()
            case Request.ATTACK:
                return self.attack()
            case Request.INITIALIZE:
                self.initialize()
            case Request.DAILY_INITIALIZE:
                self.daily_initialize()
            case Request.DAILY_FINISH:
                self.daily_finish()
            case Request.FINISH:
                self.finish()
        return None
