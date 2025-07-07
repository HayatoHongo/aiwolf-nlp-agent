import subprocess
import re

def run_and_record_result(times=100, result_file="results.txt"):
    for i in range(times):
        print(f"第{i+1}局开始")
        # 启动 main.py，捕获标准输出
        proc = subprocess.run(
            ["python", "src/main.py"],  # 路径根据你的实际情况调整
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8"
        )
        output = proc.stdout
        # 查找胜利方
        m = re.search(r"winSide=(\w+)", output)
        if m:
            winner = m.group(1)
            with open(result_file, "a", encoding="utf-8") as f:
                f.write(f"{winner}\n")
            print(f"本局胜利方：{winner}，已记录")
        else:
            print("未找到胜利方信息，输出如下：")
            print(output)

run_and_record_result(times=100)