import pandas as pd 

def prepare_dataframe(csv):
    df = pd.read_csv(csv)
    df["embedded"] = df["embedded"].map(lambda x: eval(x))
    return df