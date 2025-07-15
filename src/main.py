"""設定に応じたエージェントを起動するスクリプト."""
import logging
import multiprocessing
from pathlib import Path
import sys
import os
import io
import glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
from dotenv import load_dotenv

load_dotenv()
# プロジェクトのルートディレクトリをPythonパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
import yaml
import re
from enum import Enum
import starter

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
console_handler.setFormatter(formatter)


class Role(Enum):
    VILLAGER = "VILLAGER"
    SEER = "SEER"
    MEDIUM = "MEDIUM"
    BODYGUARD = "BODYGUARD"
    WEREWOLF = "WEREWOLF"
    POSSESSED = "POSSESSED"


class Status(Enum):
    ALIVE = "ALIVE"
    DEAD = "DEAD"


def get_latest_log_file(log_dir="log"):
    subdirs = [
        os.path.join(log_dir, d)
        for d in os.listdir(log_dir)
        if os.path.isdir(os.path.join(log_dir, d))
    ]
    if not subdirs:
        return None
    latest_subdir = max(subdirs, key=os.path.getmtime)
    log_files = glob.glob(os.path.join(latest_subdir, "*.log"))
    if not log_files:
        return None
    latest_log = max(log_files, key=os.path.getmtime)
    return latest_log


def parse_finish_packet(log_path):
    with open(log_path, encoding="utf-8") as f:
        lines = f.readlines()
    for line in reversed(lines):
        if "Request.FINISH" in line:
            # 解析 status_map
            status_map_str = re.search(r"status_map=({.*?})", line).group(1)
            role_map_str = re.search(r"role_map=({.*?})", line).group(1)
            # 解析status_map
            status_dict = {}
            for m in re.finditer(
                r"'([^']+)': <Status\.(ALIVE|DEAD): 'ALIVE'|'DEAD'>", status_map_str
            ):
                name, status = m.group(1), m.group(2)
                status_dict[name] = status
            # 解析role_map
            role_dict = {}
            for m in re.finditer(
                r"'([^']+)': <Role\.([A-Z]+): '[A-Z]+'?>", role_map_str
            ):
                name, role = m.group(1), m.group(2)
                role_dict[name] = role
            return status_dict, role_dict
    return None, None


def judge_winner(status_dict, role_dict):
    villager_roles = {"VILLAGER", "SEER", "MEDIUM", "BODYGUARD"}
    werewolf_roles = {"WEREWOLF", "POSSESSED"}
    villager_alive = sum(
        1
        for name, status in status_dict.items()
        if status == "ALIVE" and role_dict[name] in villager_roles
    )
    werewolf_alive = sum(
        1
        for name, status in status_dict.items()
        if status == "ALIVE" and role_dict[name] == "WEREWOLF"
    )
    if werewolf_alive == 0:
        return "VILLAGER"
    elif werewolf_alive >= villager_alive:
        return "WEREWOLF"
    else:
        return "UNKNOWN"


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")

    config_path = "./config/config.yml"
    with Path.open(Path(config_path)) as f:
        config = yaml.safe_load(f)
        logger.info("設定ファイルを読み込みました")

    agent_num = int(config["agent"]["num"])
    logger.info("エージェント数を %d に設定しました", agent_num)
    if agent_num == 1:
        starter.connect(config)
    else:
        threads = []
        for i in range(agent_num):
            thread = multiprocessing.Process(
                target=starter.connect,
                args=(config, i + 1),
            )
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()

    latest_log = get_latest_log_file("log")
    if latest_log:
        status_dict, role_dict = parse_finish_packet(latest_log)
        if status_dict and role_dict:
            winner = judge_winner(status_dict, role_dict)
            print(f"winSide={winner}")
