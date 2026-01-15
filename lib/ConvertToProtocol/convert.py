import re

from cls import ProtocolMean
from lib.aiwolf_share.main_classes import Comment, Sentence
import os
from dotenv import load_dotenv
load_dotenv()
# ...既存のimport...

def convert_to_protocol(nl: str, talker: str, me: str) -> list[ProtocolMean]:
    """自然言語をプロトコルに変換

    Args:
        nl (str): 自然言語の他人の発話
        talker (str): 発話者のエージェントID
        me (str): 自分のエージェントID

    Returns:
        list[ProtocolMean]: プロトコルのリスト
    """
    try:
        # ここに処理を追加
        if nl == "SKIP":
            return [ProtocolMean(False, "SKIP", None, None)]
        elif nl == "Over":
            return [ProtocolMean(False, "Over", None, None)]
        else:
            print("### sentence", nl)
            try:
                talker_agent = talker
                me_agent = me

                # OpenAI APIキーがない場合は基本的なキーワード解析のみ実行

                if not os.environ.get("OPENAI_API_KEY"):
                    print("### protocol_list -1")
                    return [ProtocolMean(False, "SKIP", None, None)]

                comment = Comment(nl, talker=talker_agent, me=me_agent)
                protocol_list: list[Sentence] = comment.remark_to_protocol(
                    ruizido_check=False, check_gpt=True
                )
                print("### protocol_list", len(protocol_list))
                [print(sentence) for sentence in protocol_list]

                result_protocols = []
                for protocol in protocol_list:
                    try:
                        protocol_mean = ProtocolMean(
                            not_flag=(
                                "NOT" in protocol.verb
                                if hasattr(protocol, "verb")
                                else False
                            ),
                            action=(
                                protocol.verb.split(" ")[-1]
                                if hasattr(protocol, "verb") and protocol.verb
                                else "SKIP"
                            ),
                            talk_subject=me,
                            talk_object=getattr(protocol, "agent", None),
                            role=getattr(protocol, "role", None),
                            team=getattr(protocol, "team", None),
                            mention_flag=getattr(comment, "flag", False),
                            original_text=nl,
                        )
                        result_protocols.append(protocol_mean)
                    except Exception as e:
                        print(f"[ERROR] Protocol creation failed: {e}")
                        # フォールバック: 基本的なプロトコルを作成
                        result_protocols.append(ProtocolMean(False, "SKIP", None, None))

                if result_protocols:
                    return result_protocols
                else:
                    print("[DEBUG] No valid protocols found, returning SKIP")
                    return [ProtocolMean(False, "SKIP", None, None)]

            except Exception as e:
                print(f"[ERROR] Comment processing failed: {e}")
                # エラーが発生した場合はSKIPプロトコルを返す
                return [ProtocolMean(False, "SKIP", None, None)]
    except Exception as e:
        print(f"[ERROR] convert_to_protocol failed: {e}")
        return [ProtocolMean(False, "SKIP", None, None)]


# プロトコルのみでやり取りするようの関数
def get_protocol_meaning(protocol: str, index: str) -> ProtocolMean:
    single_actions = ["SUSPECT", "VOTE", "DIVINATION", "AGREE"]
    double_actions = ["ESTIMATE", "CO", "DIVINED"]

    if protocol == "SKIP":
        return ProtocolMean(False, "SKIP", None, None)
    elif protocol == "Over":
        return ProtocolMean(False, "Over", None, None)

    protocol_parts = protocol.split(" ")
    if protocol_parts[0] == "NOT":
        not_flag = True
        protocol_parts.pop(0)
    else:
        not_flag = False

    print(protocol_parts)
    # if protocol_parts[0] in single_actions or protocol_parts[0] in double_actions:
    #     protocol_parts.insert(0, f"Agent[0{index}]")
    if protocol_parts[1] in single_actions:
        talk_subject = _judge_agent_name(protocol_parts[0])
        talk_object = _judge_agent_name(protocol_parts[2])
        protocol_meaning = ProtocolMean(
            not_flag, protocol_parts[1], talk_subject, talk_object
        )
    elif protocol_parts[1] in double_actions:
        if protocol_parts == ["ANY", "CO", "ANY"]:
            protocol_meaning = ProtocolMean(
                not_flag, protocol_parts[1], "ANY", "ANY", None, protocol_parts[0]
            )
        elif protocol_parts[1] == ["DIVINED"]:
            talk_subject = _judge_agent_name(protocol_parts[0])
            talk_object = _judge_agent_name(protocol_parts[2])
            protocol_meaning = ProtocolMean(
                not_flag,
                protocol_parts[1],
                talk_subject,
                talk_object,
                None,
                protocol_parts[3],
            )
        else:
            talk_subject = _judge_agent_name(protocol_parts[0])
            talk_object = _judge_agent_name(protocol_parts[2])
            protocol_meaning = ProtocolMean(
                not_flag,
                protocol_parts[1],
                talk_subject,
                talk_object,
                protocol_parts[3],
            )
    else:
        print("存在しないActionです。", protocol_parts)
        return ProtocolMean(False, "SKIP", None, None)
    return protocol_meaning


def _judge_agent_name(name: str):
    """Agent[01]~Agent[05]の名前かどうか判定し、そうなら1~5の数字を返す。そうでないならそのまま返す。"""
    if re.match(r"Agent\[0[1-5]\]", name):
        return name[-2]
    else:
        return name
