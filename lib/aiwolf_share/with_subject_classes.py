# 類似度の閾値はl83で設定している


import breakdown # remarkを要素に分割/flag
import embedding # 文章をembedding
from breakdown import get_list # remarkを要素に分割/flag
from embedding import get_embedding, cos_sim # embeddingの取得/cos類似度
from csv_to_df import prepare_dataframe

# dataframeの設定
df = prepare_dataframe("embedded.csv")

class Sentence:
    def __init__(self, verb, agent, role, team, sub):
        self.sub = sub
        self.verb = verb
        self.agent = agent
        self.role = role
        self.team = team


class Comment:
    def __init__(self, remark, talker, me):
        self.remark = remark
        self.talker = talker
        self.me = me
        self.flag = None

    def remark_to_protocol(self, ruizido_check=False, check_gpt=False):
        """
        大元のメソッド. Commentのインスタンスに対して呼び出すと、remarkがプロトコルに変換され、flagが立つ
        """
        vectorlist = self.remark_to_vectors(check_gpt)

        if ruizido_check:
            df_ruizido = df.copy()
            for i in vectorlist:
                df_ruizido["similarity"] = df_ruizido["embedded"].apply(lambda x: cos_sim(x, i))

                # df_ruizido["similarity"]が高い順に
                df_ruizido = df_ruizido.sort_values("similarity", ascending=False)
                print(df_ruizido.iloc[:5, :])

        return self.vectors_to_protocols(vectorlist)

    def remark_to_vectors(self, check_gpt):
        """
        gptの処理を呼び出して、remarkを要素に分割し、各要素をembeddingしたリストを返す
        flagも設定する
        check_gptがtrueの場合、gptの出力を表示する
        """
        return_from_gpt = get_list(self.talker, self.remark, self.me)
        sentences = return_from_gpt[0]
        self.flag = return_from_gpt[1]

        if check_gpt:
            print(return_from_gpt)
        # 各要素をembeddingしたリスト
        return [get_embedding(sentence) for sentence in sentences]

    def ruizido(self, vector):
        """
        入力文の要素の一つをembedしたベクトルと、データフレームのembedded列のベクトルとの類似度を計算し、最も類似度が高い文のindexを返す
        """
        similarity_list = [] #一旦、類似度だけを格納しておくためのリスト
        for i in df["embedded"]:
            similarity_list.append(cos_sim(i, vector))

        index = similarity_list.index(max(similarity_list))
        max_sim = max(similarity_list)


        #最大の類似度と、その文のindexを返す
        return (max_sim, index)

    #最終的なリストの作成
    #from send import Sentence

    def vectors_to_protocols(self, vectorlist): #vectorlistはto_vectors(talker, comment)の返り値
        protocol_list = []
        for i in vectorlist:

            # 類似度が0.67未満のものは無視
            if self.ruizido(i)[0] < 0.67:
                continue

            verb = df.loc[self.ruizido(i)[1], "Verb"]
            agent = df.loc[self.ruizido(i)[1], "Agent"]
            role = df.loc[self.ruizido(i)[1], "Role"]
            team = df.loc[self.ruizido(i)[1], "Team"]
            sub = df.loc[self.ruizido(i)[1], "Subject"]


            sentence = Sentence(verb, agent, role, team, sub)


            # 重複するprotocolを省く
            unnecessary = 0
            for protocol in protocol_list:
                if protocol.verb == sentence.verb and protocol.agent == sentence.agent and protocol.role == sentence.role and protocol.team == sentence.team:
                    unnecessary = 1
            if unnecessary == 0:
                protocol_list.append(sentence)

        return protocol_list



