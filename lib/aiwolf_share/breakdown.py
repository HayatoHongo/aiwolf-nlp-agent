from openai import OpenAI # type: ignore
import openai # type: ignore
import os

# APIキーを環境変数として設定
openai.api_key = os.environ["OPENAI_API_KEY"]
client = OpenAI()

def get_list(talker, remark, me, model="gpt-3.5-turbo"): #gpt-3.5-turbo-0125
    """
    sentense: 発話内容
    """

    system = f"""
    You are playing a werewolf game. Write the output appropriately

    # output
    - English
    - python tuple including two elements
    - The first element is a python list( contents of the input rewritten into concise contents)
    - The second element is 0 or 1. It works as a flag. If the speaker request or inquire something to {me}, the flag must be 1. If else, the flag is 0.

    # rule
    - The Remark should be divided as finely as possible.
    - Avoid using reference terms like 'this', 'that' or 'so'. It's better to have each element of the list be longer than that.
    - Use the following verbs actively: estimate, suspect, vote, divine, agree
    - When referring to a person, never use he, him, she, or her. Use only "I" for yourself, or use the exact Japanese name (e.g., シズエ, ジョナサン) as written in the input for others.
    - Representing the job title, use werewolf, possessed, villager or seer
    - Ignore information that has nothing to do with werewolf game

    # example
    Remark: {me}がずいぶん口をつぐんでるな。{me}は人狼なんじゃないのか？。今夜は{me}に投票するつもりや。
    Your answer should be (["{me} is quiet", "I think {me} is a werewolf", "I'm planning to vote for {me} tonight"], 1)
    Remark: シズエは、占い師であることをカミングアウトしていますが、彼は嘘をついています。
    Your answer should be (["シズエ claims to be a seer", "シズエ is lying"], 0)
    """
    # - The Remark should be divided as finely as possible. Each element in the list should be less than 12 words (less than 8 words is better)

    user = f"Remark: {remark}"

    # 1Mあたり80円/240円
    # 入力が400、出力が100トークンの場合、発話1回あたり80/1000 + 240/10000 = 0.1円

    completion = client.chat.completions.create(
      model=model,
      messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user}
      ]
    )
    gpt_output = eval(completion.choices[0].message.content) # expeceted to be a tuple
    broken_list, frag = gpt_output[0], gpt_output[1]

    # tupleの中身がstrの場合、evalで変換
    if type(broken_list) == str:
        broken_list = eval(broken_list)
    if type(frag) == str:
        frag = eval(frag)
        # fragがtrue/falseの場合、1/0に変換
        if frag == True:
            frag = 1
        if frag == False:
            frag = 0

    return broken_list, frag


if __name__ == "__main__":
    talker = "Agent[03]"
    remark = "おいAgent[03]、お前は嘘をついているんだろ"
    me = "Agent[02]"
    with open("output.log", 'a') as f:
        print('入力: ', file=f)
        print(remark, file=f)
        print(f'me:{me}', file=f)
        print(get_list(talker, remark, me), file=f)
        print(file=f)
