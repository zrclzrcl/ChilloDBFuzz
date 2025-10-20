import os
import yaml

def main():

    #1. 读取fuzz_config文件
    with open("./fuzz_config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    target_dbms = config["TARGET_DBMS"]
    output_dir = config["OUTPUT_DIR"]
    input_dir = config["INPUT_DIR"]
    fuzzer_path = config["FUZZER_PATH"]
    fuzz_time = config["FUZZ_TIME"]
    chilo_mutator_path = config["CHILO_MUTATOR_PATH"]

    can_fuzz_dbms_list = ["SQLite"]

    if target_dbms not in can_fuzz_dbms_list:
        raise Exception(f"Unsupported DBMS, plz check fuzz_config.yaml. TARGET_DBMS must in {can_fuzz_dbms_list}")

    #2. 设置系统环境（FOR AFL++）
    os.environ["AFL_CUSTOM_MUTATOR_ONLY"] = "1" #只使用客制化变异器
    os.environ["AFL_DISABLE_TRIM"] = "1"    #禁用剪裁
    os.environ["AFL_FAST_CAL"] = "1"    #禁用初期多次执行种子时的路径校准
    os.environ["PYTHONPATH"] = chilo_mutator_path
    os.environ["AFL_PYTHON_MODULE"] = "ChiloMutate"


    #3. 启动FUZZ
    if target_dbms == "SQLite":
        if fuzz_time < 0:
            cmd = f"{fuzzer_path} -i {input_dir} -o {output_dir} -- /home/ossfuzz @@"
        else:
            cmd = f"{fuzzer_path} -i {input_dir} -o {output_dir} -V {fuzz_time}  -- /home/ossfuzz @@"
    else:
        raise Exception(f"Unsupported DBMS, plz check fuzz_config.yaml. TARGET_DBMS must in {can_fuzz_dbms_list}")

    os.system(cmd)


if __name__ == "__main__":
    main()