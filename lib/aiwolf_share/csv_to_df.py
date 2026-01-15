# import pandas as pd

# def prepare_dataframe(csv):
#     df = pd.read_csv(csv)
#     df["embedded"] = df["embedded"].map(lambda x: eval(x))
#     return df
import pandas as pd
from pathlib import Path  # pathlib をインポート


def prepare_dataframe(csv_filename: str):
    # このファイル(csv_to_df.py)自身の絶対パスを取得し、その親ディレクトリ(aiwolf_share)を得る
    # これが基準点となる
    base_dir = Path(__file__).resolve().parent

    # 基準点のディレクトリパスとファイル名を結合して、データファイルの絶対パスを作成
    # 例: "C:/.../lib/aiwolf_share" + "/" + "embedded.csv"
    csv_path = base_dir / csv_filename

    # 絶対パスを使ってファイルを読み込むので、もう迷わない
    df = pd.read_csv(csv_path)
    df["embedded"] = df["embedded"].map(lambda x: eval(x))  # ここを必ず追加
    return df
    return df
