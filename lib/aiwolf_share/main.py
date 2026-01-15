from main_classes import Sentence, Comment # Sentence/Commentクラス

comment1 = Comment("俺は占い師に決まってる！そんなことを言うなんて、Agent2のことは信用できぬな。Agent1は正しいよ。agent1に投票しようなんて言っている奴がいるが、わしはそんなことはしない。", talker="Agent[00]", me="Agent[03]") 
protocol_list = comment1.remark_to_protocol(ruizido_check=True, check_gpt=True)


for protocol in protocol_list:
    print(protocol.verb, protocol.agent, protocol.role, protocol.team)
print(comment1.flag)

