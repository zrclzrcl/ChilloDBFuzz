import time

from .chilo_factory import ChiloFactory

def _get_structural_prompt(sql, target_dbms, dbms_version):
    prompt = f"""
You are an expert in database fuzzing whose goal is to **TRIGGER CRASHES AND BUGS** in {target_dbms} version {dbms_version}. Perform aggressive structural mutations on the provided SQL test case to maximize the likelihood of exposing vulnerabilities, edge cases, and crash-inducing behaviors.

🎯 PRIMARY OBJECTIVE: Generate SQL that is **HIGHLY LIKELY TO CRASH** or trigger anomalous behaviors, NOT just syntactically correct variations.

📋 AGGRESSIVE MUTATION STRATEGIES (Apply 3-5 of these):

1. **EXTREME COMPLEXITY INJECTION**:
   - Add 5-10 levels of deeply nested subqueries
   - Use recursive CTEs with large recursion depths (e.g., RECURSIVE with UNION ALL, 100+ iterations)
   - Combine multiple window functions (ROW_NUMBER, RANK, LAG, LEAD, NTILE) in complex expressions
   - Create circular dependencies between views/tables if possible
   - Mix correlated and non-correlated subqueries in unexpected places

2. **TYPE CONFUSION & CONVERSION CHAOS**:
   - Force implicit type conversions between incompatible types (e.g., CAST(geometry AS int), CAST(NULL AS custom_type))
   - Mix string, numeric, date, binary, and NULL types in arithmetic operations
   - Use UNION with mismatched column types
   - Apply aggregate functions on incompatible types
   - Create computed columns with ambiguous type inference

3. **BOUNDARY & EDGE CASE EXPLOITATION**:
   - Use extreme values: INT_MAX, INT_MIN, very large floats (1e308), negative zeros
   - Empty strings, single quotes, NULL bytes (\\x00), unicode edge cases
   - Zero-length arrays, empty JSON/XML, malformed structures
   - Division by zero, modulo by zero, negative array indices
   - Overflow-inducing arithmetic (e.g., MAX_INT + 1, factorial of large numbers)

4. **ADVANCED SQL FEATURES (DBMS-SPECIFIC)**:
   - **{target_dbms} specific functions**: Use obscure built-in functions, system functions, version-specific features
   - **Window functions**: Complex PARTITION BY with multiple columns, ORDER BY with edge cases, RANGE/ROWS frame specifications
   - **JSON/XML operations**: Deeply nested paths, malformed JSON/XML, type mismatches in path expressions
   - **Full-text search**: Complex text search queries with unicode, special characters, phrase matching edge cases
   - **Aggregate functions**: Nested aggregates, custom aggregates, GROUP BY with HAVING complexity, ROLLUP/CUBE/GROUPING SETS
   - **Collation/Character sets**: Mix different collations, character set conversions, binary vs case-insensitive comparisons
   - **Triggers**: Cascading triggers, multi-level trigger chains, trigger timing edge cases (BEFORE/AFTER/INSTEAD OF)
   - **Views**: Materialized views, updateable views, views referencing views with circular-like patterns
   - **Indexes**: Partial indexes, expression-based indexes, multi-column indexes with edge cases
   - **Constraints**: Complex CHECK constraints, deferred constraints, constraint violations in edge cases

5. **CUSTOM FUNCTIONS & STORED PROCEDURES**:
   - Create user-defined functions (UDF) with recursive calls
   - Define stored procedures with complex control flow (nested loops, exception handlers)
   - Use triggers with cascading actions
   - Create functions that call themselves or other functions recursively
   - Mix deterministic and non-deterministic functions

6. **TRANSACTION & CONCURRENCY EDGE CASES**:
   - BEGIN/COMMIT/ROLLBACK with nested transactions
   - SAVEPOINT with edge cases (rolling back to non-existent savepoints)
   - Mix DDL and DML in transactions
   - Use LOCK TABLES with conflicting lock types
   - Create temporary tables inside transactions and drop them ambiguously

7. **SCHEMA MANIPULATION CHAOS**:
   - ALTER TABLE with incompatible type changes
   - DROP and CREATE same object in rapid succession
   - Add constraints that conflict with existing data
   - Rename tables/columns while they're being referenced
   - Create indexes on expressions that might fail

8. **EXTREME DATA GENERATION**:
   - INSERT with SELECT generating 1000+ rows
   - Self-joins creating cartesian products
   - Generate series with extreme ranges
   - Use CROSS JOIN to create exponential row explosions (controlled to avoid timeout)

9. **EXPRESSION COMPLEXITY**:
   - 10+ levels of CASE WHEN nesting
   - Complex boolean expressions with AND/OR/NOT, precedence ambiguity
   - Arithmetic expressions with mixed operators and parentheses
   - String concatenation with NULL handling edge cases
   - Pattern matching with backtracking-heavy regex

10. **ERROR-PRONE PATTERNS**:
    - Access non-existent columns/tables and catch errors
    - Out-of-bounds array/string access
    - Invalid format strings in date/number formatting
    - Circular foreign key references
    - Self-referencing views or recursive definitions

⚠️ CRITICAL CONSTRAINTS:
1. **Execution time**: Keep operations fast (<1 second). Avoid actual infinite loops, but create complex-enough structures that approach time limits.
2. **Syntactic validity**: Generated SQL MUST be syntactically correct for {target_dbms} version {dbms_version}.
3. **Pure SQL**: Output only SQL statements, no comments or explanations in the code block.
4. **Semicolon termination**: Each statement ends with `;`.

🎲 MUTATION INTENSITY: **HIGH**
- Perform **RADICAL transformations**, not minor tweaks
- Add 5-15 new SQL statements
- Combine multiple mutation strategies
- Maximize structural complexity while maintaining executability

📤 OUTPUT FORMAT:
Return ONLY the mutated SQL wrapped as:
```sql
(your mutated SQL here)
```

📥 INPUT TEST CASE:
```sql
{sql}
```

🚀 NOW GENERATE: Apply 3-5 mutation strategies to create a **CRASH-INDUCING** SQL test case for {target_dbms} version {dbms_version}. Be aggressive, creative, and target known database vulnerability patterns!
"""
    return prompt

def structural_mutator(my_chilo_factory: ChiloFactory):
    """
    实现SQL的结构性变异
    :return: 无返回值
    """
    structural_count = 0
    my_chilo_factory.structural_mutator_logger.info("结构化变异器已启动！")
    system_prompt = """You are an AGGRESSIVE database security researcher and fuzzing expert specializing in crash discovery. Your mission is to generate EXTREME SQL test cases that exploit edge cases, boundary conditions, and known vulnerability patterns in database systems. You have deep knowledge of:
- DBMS implementation bugs and historical CVEs
- Type system vulnerabilities and implicit conversion edge cases  
- Query optimizer weaknesses and plan generation bugs
- Memory corruption patterns in SQL engines
- Concurrency and transaction isolation anomalies
- Parser and lexer edge cases

Your generated SQL should be MAXIMALLY COMPLEX and target crash-prone areas. Prioritize creativity and aggressiveness over conservatism. Every test case should push the DBMS to its limits."""
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
        my_chilo_factory.wait_exec_structural_list.put({"seed_id": new_seed_id, "is_from_structural_mutator": True, "mutate_content": after_mutate_testcase})
        my_chilo_factory.structural_mutator_logger.info(f"seed_id：{new_seed_id}，已加入等待执行结构化变异队列")
        my_chilo_factory.structural_mutator_logger.info("-" * 10)
        structural_mutate_end_time = time.time()
        my_chilo_factory.write_structural_mutator_csv(structural_mutate_end_time, target_seed_id, new_seed_id, structural_mutate_end_time-structural_mutate_start_time,
                                                      all_up_token, all_down_token, llm_count, llm_error_count, llm_use_time, my_chilo_factory.structural_mutator_list.qsize())

        