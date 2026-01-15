from openai import OpenAI
import openai
import os

from output_module import first_translate

# APIキーを環境変数として設定
openai.api_key = os.environ["OPENAI_API_KEY"]

#入力のプロトコル文
protocol = "REQUEST ANY (COMINGOUT ANY ANY)" #REQUEST ANY (COMINGOUT ANY ANY)
first = first_translate(protocol)
if first == None:
  first = "SKIP"


#出力
client = OpenAI()

completion = client.chat.completions.create(
  model="gpt-4o",
  messages=[
    {
      "role": "system", 
      "content": """あなたは、関西弁で人狼ゲームをプレイしている。発言したい内容が英語の一文で与えられるので、その趣旨を保ったまま、できる限り流暢な日本語で話を膨らませながら発言しろ。形式はpythonのstrで、最低3文は話せ。
        ただし、"SKIP"または"OVER"が入力された場合、出力はそのまま、SKIPおよびOVERを返せ。"""
    },
    
    {
      "role": "user", 
      "content": first
    }
  ]
)

output = completion.choices[0].message.content
output = eval(output) # 二重のstrになってしまった時
if type(output) != str:
    output = f"{output}"

print(output, type(output))



