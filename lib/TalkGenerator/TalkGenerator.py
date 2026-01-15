import os

import openai
from cls import ProtocolMean
from lib.aiwolf_share.output_tests.output_module import first_translate
from openai import OpenAI

openai.api_key = os.environ["OPENAI_API_KEY"]


class TalkGenerator:
    def __init__(self, agent_name, profile):
        self.agent_name = agent_name
        self.profile = profile

    def generate_talk(self, protocol: ProtocolMean, request=False, request_target=""):
        if request:
            protocol_text = f"REQUEST {request_target} {str(protocol)}"
        else:
            protocol_text = str(protocol)
        first = first_translate(protocol_text)
        print(f"[DEBUG] TalkGenerator: protocol={protocol_text}, first={first}")
        if first is None:
            first = "OVER"

        # 出力
        client = OpenAI()

        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"あなたは、人狼ゲームの参加者「{self.agent_name}」です。"
                    + f"あなたの性格・背景情報は以下の通りです：\n{self.profile}\n発言したい内容が英語の一文で与えられるので、必ずこの性格・口調・話し方を守り、その趣旨を保ったまま流暢な日本語で発言してください。\n"
                    + "発言は60文字以内の日本語で行ってください"
                    + "出力は発言の内容のみとしてください。"
                    # + f"重要: あなたの名前は「{self.agent_name}」です。必ず一人称（私、僕、俺など）を使って発言し、絶対に「{self.agent_name}」という自分の名前を三人称として使わないでください。"
                    + "他の参加者について話す時は、その人の名前を使って構いませんが、自分について話す時は必ず一人称を使ってください。"
                    + "ゲームは0日目から始まります。つまり0日目=初日、1日目=2日目、2日目=3日目となります。1日目は初日ではありません。"
                    + "ANYは、「皆さん」とよみかえてください。"
                    + "ただし、例外が存在するのでその場合は以下のように出力すること。"
                    + "contentが「SKIP」または「OVER」の場合、出力はそのまま、SKIPおよびOVERを返してください。",
                },
                {"role": "user", "content": first},
            ],
        )

        return completion.choices[0].message.content
