keywords = [
    "ESTIMATE", "COMINGOUT", "DIVINATION", "GUARD", "VOTE", "ATTACK", "DIVINED", "IDENTIFIED", "GUARDED", "VOTED", "ATTACKED",
    "AND", "OR", "NOT", "XOR", "CO"
]
verbs = [
    "ESTIMATE", "COMINGOUT", "DIVINATION", "GUARD", "VOTE", "ATTACK", "DIVINED", "IDENTIFIED", "GUARDED", "VOTED", "ATTACKED", "CO"
]

def keyword_check(protocol):
    # OVERとSKIPを確認
    if protocol == "OVER":
        return "OVER"
    elif protocol == "SKIP":
        return "SKIP"
    # REQUEST文/INQUIRE文か判別
    elif protocol.split()[0] == "REQUEST":
        return "REQUEST"
    elif protocol.split()[0] == "INQUIRE":
        return "INQUIRE"
    # 動詞・文構造を確定させる
    else:
        a = None
        for i in keywords:
            if i in [protocol.split()[0], protocol.split()[1]]:
                a = i
                break
        if a == "NOT":
            b = None
            for i in verbs:
                if i in [protocol.split()[1], protocol.split()[2], protocol.split()[3]]:
                    b = i
                    return "NOT" + " " + b
        else:
            return a

def first_translate(protocol):
    keyword = keyword_check(protocol)
    print(f"[DEBUG] first_translate: protocol={protocol}, keyword={keyword}")
    if keyword == "OVER" or keyword == "SKIP":
        return keyword
    elif keyword in verbs:
        tokens = protocol.split()
        print(f"[DEBUG] tokens: {tokens}")
        # ProtocolMeanの__str__に合わせて、主語・動詞・目的語・役職の順で解釈
        # 例: "アスカ CO SEER" → CO発言
        if len(tokens) >= 3 and keyword == "CO":
            # CO発言: "アスカ CO SEER" → "I am the SEER."
            return f"I am the {tokens[2]}."
        # elif len(tokens) >= 4 and tokens[2] == "CO":
        #     # CO発言: "Agent[アスカ] CO SEER" のような場合
        #     return f"I am the {tokens[3]}."
        elif len(tokens) >= 3 and tokens[1] == "COMINGOUT":
            return f"I am the {tokens[2]}."
        elif len(tokens) >= 4 and tokens[2] == "COMINGOUT":
            return f"I am the {tokens[3]}."
        # その他の動詞
        elif keyword == "ESTIMATE" and len(tokens) >= 3:
            return f"I think {tokens[1]} is the {tokens[2]}."
        elif keyword == "DIVINATION" and len(tokens) >= 2:
            return f"I will divine {tokens[1]} tonight."
        elif keyword == "GUARD" and len(tokens) >= 2:
            return f"I'm going to guard {tokens[1]} from werewolf."
        elif keyword == "VOTE" and len(tokens) >= 2:
            return f"I'm going to vote {tokens[1]} today."
        elif keyword == "ATTACK" and len(tokens) >= 2:
            return f"I will kill {tokens[1]} tonight."
        elif keyword == "DIVINED" and len(tokens) >= 3:
            return f"I divined {tokens[1]} last night and he was the {tokens[2]}."
        elif keyword == "IDENTIFIED" and len(tokens) >= 3:
            return f"I identified {tokens[1]} as a medium last night and he was the {tokens[2]}."
        elif keyword == "GUARDED" and len(tokens) >= 2:
            return f"I guaded {tokens[1]} from werewolf last night."
        elif keyword == "VOTED" and len(tokens) >= 2:
            return f"I voted {tokens[1]} yesterday."
        elif keyword == "ATTACKED" and len(tokens) >= 2:
            return f"I attacked {tokens[1]} last night."
        else:
            print(f"[DEBUG] first_translate: Unrecognized protocol format: {protocol}")
            return None
    elif keyword == "REQUEST":
        tokens = protocol.split()
        # ProtocolMeanの__str__に合わせて解釈
        if len(tokens) >= 4 and tokens[2] == "DIVINATION":
            return f"I want {tokens[1]} to divine {tokens[3]}."
        elif len(tokens) >= 4 and tokens[2] == "GUARD":
            return f"I want {tokens[1]} to guard {tokens[3]} tonight."
        elif len(tokens) >= 4 and tokens[2] == "VOTE":
            return f"I want {tokens[1]} to vote {tokens[3]} tonight."
        elif len(tokens) >= 4 and tokens[2] == "ATTACK":
            return f"I want {tokens[1]} to assault {tokens[3]} tonight."
        elif len(tokens) >= 5 and tokens[2] == "ESTIMATE":
            return f"I want {tokens[1]} to consider that {tokens[3]} is the {tokens[4]}."
        elif len(tokens) >= 5 and tokens[2] == "CO" and tokens[4] != "ANY":
            return f"I want {tokens[1]} to coming out to be {tokens[3]}."
        elif len(tokens) >= 5 and tokens[2] == "COMINGOUT" and tokens[4] == "ANY":
            return f"I want {tokens[1]} to coming out your job now."
        elif len(tokens) >= 3 and tokens[1] == "ANY" and tokens[2] == "CO":
            print("村人初日初発言はこれのはず")
            return f"I want everyone to coming out your job now."
        else:
            print(f"[DEBUG] first_translate: Unrecognized REQUEST format: {protocol}")
            return None
    elif keyword == "INQUIRE":
        tokens = protocol.split()
        return f"Hey {tokens[1]}, I'm curious about {tokens[2:]} ."
    else:
        return None
