# ChiloDBFuzz
（目前正在开发中！）
    
（dev-ing）
## 简体中文
基于LLM与掩码变异生成测试用例的DBMS模糊测试工具。

## 如何使用

### docker镜像准备
ChiloDBFuzz的镜像需要从dockerfile构建，下面是具体的构建命令。（首先您要确定本机的docker已经被正确安装）

根据被测对象不同，构建命令略有区别，请根据被测对象进行选择。

SQLite：
```bash
cd {repo_path}
cd ./docker/sqlite
docker build -t chilodbfuzz:sqlite .
```

### docker容器启动
```bash
#下面语句请在主机终端1运行
docker run -it --privileged -p 5173:5173 --name sqlite_chilofuzz_test chilodbfuzz:sqlite /bin/bash
# 请首先编写config.yaml以及fuzz_config.yaml
vim ./config.yaml
echo core | sudo tee /proc/sys/kernel/core_pattern

#下面请在主机终端2运行
docker exec -it sqlite_chilofuzz_test bash
cd ../ChiloDisco/ && python3 app.py  #启动ChiloDisco后端

#下面请在主机终端3运行
docker exec -it sqlite_chilofuzz_test bash
cd ../ChiloDisco/frontend/ && npm run dev -- --host 0.0.0.0

#下面请在主机终端1运行
python3 start_fuzz.py
```