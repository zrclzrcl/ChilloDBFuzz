import time

from .chilo_factory import ChiloFactory

def _get_structural_prompt(sql, target_dbms, dbms_version):
    prompt = f"""
Please perform structural mutations on the given test case according to the following requirements:
Task objectives:
1. Apply structural mutations to the SQL test case I provide and generate new SQL test cases.
2. Each test case should contain multiple SQL statements and include only SQL statements (no non-SQL content).

Mutation requirements:
1. Reordering: You may change the execution order of the original SQL statements to explore differences in execution dependencies.
2. Addition/deletion: You may add or remove some SQL statements. Any added SQL statements must be syntactically correct, semantically reasonable, and directly executable on the database.
3. Complexity enhancement: Generated SQL should, whenever possible, include complex constructs (e.g., deeply nested queries, CTEs, triggers, transaction blocks, temporary tables, etc.).
4. Database specificity: Prefer using keywords, functions, or features specific to {target_dbms} version {dbms_version} (for example, unique system functions, optimizer hints, stored procedure syntax, etc.).
5. Crash-exploration focus: The goal is to produce SQL structures that are more likely to trigger crashes or anomalous behaviors in the database, rather than mere syntactic perturbations.
6. The output must be pure SQL content.
7. After mutation, you must validate the generated test case to ensure syntactic and semantic correctness.
8. Execution-time constraint (fuzzing safety): Each generated test case must be short-running and suitable for automated fuzzing. Do NOT include infinite loops, unbounded waits, or constructs that can block indefinitely. Avoid long-running operations; Each test executes quickly and deterministically.

Output format:
1. Return the mutated SQL test case wrapped as: \n```sql\n(generated test case)\n``` (using newline + triple-backtick + "sql" as shown).
2. Each SQL statement must end with a semicolon (`;`).

Input test case:
```sql
{sql}
```

Now, based on the above requirements, perform structural mutation on the provided SQL test case. Target DBMS: {target_dbms} (version {dbms_version}).
"""
    return prompt

def structural_mutator(my_chilo_factory: ChiloFactory):
    """
    实现SQL的结构性变异
    :return: 无返回值
    """
    structural_count = 0
    my_chilo_factory.structural_mutator_logger.info("结构化变异器已启动！")
    system_prompt = "You are a database fuzzing expert whose role is to generate complex SQL test cases that can trigger database exceptions or crashes. Based on the original test cases I provide, you will produce new SQL test cases via structured mutations to maximize the likelihood of exposing potential vulnerabilities or causing crashes in the target DBMS."
    while True:
        structural_mutate_start_time = time.time()
        structural_count += 1
        all_up_token = 0
        all_down_token = 0
        llm_count = 0
        llm_error_count = 0
        llm_use_time = 0
        my_chilo_factory.structural_mutator_logger.info("结构化变异器等待任务中")
        need_structural_mutate = my_chilo_factory.structural_mutator_list.get()  #拿出一个需要结构化变异的
        target_seed_id = need_structural_mutate["seed_id"]
        my_chilo_factory.structural_mutator_logger.info(f"结构化变异器接收到变异任务，seed_id：{target_seed_id}")
        seed_sql = my_chilo_factory.all_seed_list.seed_list[target_seed_id].seed_sql
        prompt = _get_structural_prompt(seed_sql, my_chilo_factory.target_dbms, my_chilo_factory.target_dbms_version)   #获取提示词
        while True:
            structural_mutate_llm_start_time = time.time()
            my_chilo_factory.structural_mutator_logger.info(f"seed_id：{target_seed_id}，准备调用LLM进行结构化变异")
            after_mutate_testcase,up_token, down_token = my_chilo_factory.llm_tool_box.chat_llm(prompt, system_prompt)
            all_up_token += up_token
            all_down_token += down_token
            llm_count += 1
            structural_mutate_llm_end_time = time.time()
            llm_use_time += structural_mutate_llm_end_time - structural_mutate_llm_start_time
            my_chilo_factory.structural_mutator_logger.info(f"seed_id：{target_seed_id}，调用LLM结束，用时：{structural_mutate_llm_end_time-structural_mutate_llm_start_time:.2f}s")
            after_mutate_testcase = my_chilo_factory.llm_tool_box.get_sql_block_content(after_mutate_testcase)  # 提取内容
            try:
                after_mutate_testcase = after_mutate_testcase[0]
                break
            except:
                #说明生成格式出现错误，需要从新生成
                llm_error_count += 1
                my_chilo_factory.structural_mutator_logger.info(f"seed_id：{target_seed_id}，LLM生成格式错误，正在从新生成")
                continue
            #作为新的种子加入到列表中

        my_chilo_factory.structural_mutator_logger.info(f"seed_id：{target_seed_id}，正在加入到种子池中")
        _, new_seed_id = my_chilo_factory.all_seed_list.add_seed_to_list(after_mutate_testcase.encode("utf-8"))
        with open(f"{my_chilo_factory.structural_mutator_path}{structural_count}_{target_seed_id}_{new_seed_id}.txt", "w", encoding="utf-8") as f:
            f.write(after_mutate_testcase)
        my_chilo_factory.structural_mutator_logger.info(f"seed_id：{target_seed_id}，变异后，新的seed_id为：{new_seed_id}，已保存到文件{structural_count}_{target_seed_id}_{new_seed_id}.txt")
        my_chilo_factory.wait_parse_list.put({"seed_id": new_seed_id, "mutate_time": need_structural_mutate["mutate_time"]})
        my_chilo_factory.structural_mutator_logger.info(f"seed_id：{new_seed_id}，已加入待解析任务队列")
        my_chilo_factory.structural_mutator_logger.info("-" * 10)
        structural_mutate_end_time = time.time()
        my_chilo_factory.write_structural_mutator_csv(structural_mutate_end_time, target_seed_id, new_seed_id, structural_mutate_end_time-structural_mutate_start_time,
                                                      all_up_token, all_down_token, llm_count, llm_error_count, llm_use_time, my_chilo_factory.structural_mutator_list.qsize())

        