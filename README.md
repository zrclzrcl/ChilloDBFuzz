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