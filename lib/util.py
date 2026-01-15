import configparser
import errno
import os
import random


def read_text(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def random_select(data: list):
    return random.choice(data)


def is_json_complate(responces: bytes) -> bool:

    try:
        responces = responces.decode("utf-8")
    except:
        return False

    if responces == "":
        return False

    cnt = 0

    for word in responces:
        if word == "{":
            cnt += 1
        elif word == "}":
            cnt -= 1

    return cnt == 0


def init_role(agent, inifile: configparser.ConfigParser, name: str):
    from agent.villager import Villager
    from agent.werewolf import Werewolf
    from agent.seer import Seer
    from agent.possessed import Possessed

    if agent.role == "VILLAGER":
        new_agent = Villager(inifile=inifile, name=name)
    elif agent.role == "WEREWOLF":
        new_agent = Werewolf(inifile=inifile, name=name)
    elif agent.role == "SEER":
        new_agent = Seer(inifile=inifile, name=name)
    elif agent.role == "POSSESSED":
        new_agent = Possessed(inifile=inifile, name=name)

    agent.hand_over(new_agent=new_agent)
    return new_agent


def check_config(config_path: str) -> configparser.ConfigParser:

    if not os.path.exists(config_path):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), config_path)

    return configparser.ConfigParser()
