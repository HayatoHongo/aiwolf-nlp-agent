from lib.aiwolf_share.main_classes import Comment  # Sentence/Commentクラス
from lib.aiwolf_share.main_classes import Sentence

text = "Agent[02]の言っていることは信じられない。今夜はAgent[01]に投票するよ。"

comment1 = Comment(text, talker="Agent[00]", me="Agent[03]")
protocol_list: list[Sentence] = comment1.remark_to_protocol(ruizido_check=True, check_gpt=True)


for protocol in protocol_list:
    print(protocol.verb, protocol.agent, protocol.role, protocol.team)
print(comment1.flag)
print(comment1.talker)
