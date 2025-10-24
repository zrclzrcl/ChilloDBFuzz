import time

from .chilo_factory import ChiloFactory

def _get_structural_prompt(sql, target_dbms, dbms_version):
    prompt = f"""
You are an **ELITE database security researcher** specializing in {target_dbms} v{dbms_version} crash discovery. Your mission is to generate **CRASH-INDUCING SQL** by learning from REAL historical vulnerabilities.

🎯 PRIMARY OBJECTIVE: Generate SQL that is **HIGHLY LIKELY TO CRASH** {target_dbms} v{dbms_version}, NOT just syntactically complex variations.

---

## 📚 LEARN FROM REAL CRASHES (Few-Shot Examples)

These are ACTUAL SQL patterns that triggered crashes in SQLite. Study them and generate SIMILAR patterns:

### Example 1: CVE-2019-8457 - Window Function Stack Overflow
**Trigger Pattern**: Extreme window frame range causes stack overflow
```sql
CREATE TABLE t1(x INTEGER);
INSERT INTO t1 VALUES(1),(2),(3);
SELECT max(x) OVER (
    ORDER BY x 
    ROWS BETWEEN 1 PRECEDING AND 1000000000 FOLLOWING
) FROM t1;
```
**Why it crashes**: SQLite allocates an array for 1 billion rows, malloc fails, NULL pointer dereference
**Key pattern**: Window function + extreme ROWS BETWEEN range

### Example 2: CVE-2020-13871 - FTS3 Use-After-Free
**Trigger Pattern**: FTS3 virtual table with complex MATCH query
```sql
CREATE VIRTUAL TABLE t1 USING fts3(content TEXT);
INSERT INTO t1 VALUES('test data ' || randomblob(100000));
SELECT * FROM t1 WHERE t1 MATCH 'a*' || 'b*' || 'c*' || 'd*' || 'e*';
```
**Why it crashes**: Complex wildcard pattern with large data causes memory corruption
**Key pattern**: FTS virtual table + wildcard explosion + large data

### Example 3: CVE-2022-35737 - Printf Format String Array Overflow
**Trigger Pattern**: Extreme format width in printf
```sql
SELECT printf('%.*c', 2147483647, 'x');
SELECT printf('%999999999d', 123);
```
**Why it crashes**: Width specifier causes integer overflow in buffer allocation
**Key pattern**: printf() + extreme width specifier

### Example 4: CVE-2020-13632 - Recursive CTE Infinite Loop
**Trigger Pattern**: Badly designed recursive CTE
```sql
WITH RECURSIVE c(x) AS (
    SELECT 1
    UNION ALL
    SELECT x+1 FROM c WHERE x < 100000
)
SELECT sum(x) FROM c;
```
**Why it crashes**: Stack overflow from deep recursion, or excessive memory allocation
**Key pattern**: WITH RECURSIVE + large iteration count

### Example 5: Integer Overflow in Expression
**Trigger Pattern**: Arithmetic overflow in constant folding
```sql
SELECT CAST(9223372036854775807 AS INTEGER) + 1;
SELECT CAST('9223372036854775808' AS INTEGER);
SELECT 9223372036854775807 * 2;
```
**Why it crashes**: Integer overflow handling bug, signed/unsigned confusion
**Key pattern**: MAX_INT arithmetic operations

### Example 6: Type Confusion in UNION
**Trigger Pattern**: Mismatched types in UNION with aggressive CAST
```sql
SELECT CAST(randomblob(1000000) AS INTEGER)
UNION ALL
SELECT CAST('not a number' AS INTEGER)
UNION ALL
SELECT CAST(1e308 AS INTEGER);
```
**Why it crashes**: Type conversion edge cases, buffer overflow in CAST implementation
**Key pattern**: UNION + aggressive CAST + extreme values

### Example 7: Nested Aggregate Complexity
**Trigger Pattern**: Deeply nested aggregates with window functions
```sql
SELECT 
    SUM(AVG(MAX(x))) OVER (
        PARTITION BY COUNT(y) 
        ORDER BY TOTAL(z)
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )
FROM (
    SELECT randomblob(1000) as x, randomblob(1000) as y, randomblob(1000) as z
    FROM generate_series(1, 1000)
);
```
**Why it crashes**: Complex aggregate nesting confuses query optimizer, memory corruption
**Key pattern**: Nested aggregates + window functions + large data

### Example 8: Trigger Cascading Chaos
**Trigger Pattern**: Recursive trigger invocations
```sql
CREATE TABLE t1(x INT);
CREATE TRIGGER trig1 AFTER INSERT ON t1 BEGIN
    INSERT INTO t1 SELECT x+1 FROM t1 WHERE x < 100;
END;
INSERT INTO t1 VALUES(1);
```
**Why it crashes**: Trigger recursion depth limit bypass, stack overflow
**Key pattern**: Self-referencing trigger + recursive INSERT

---

## 🎯 YOUR MISSION: Apply These Patterns

Based on the above REAL crash examples, perform **VULNERABILITY-DRIVEN** mutations on the input SQL:

📋 CRASH-INDUCING MUTATION STRATEGIES (Apply 3-5):

1. **WINDOW FUNCTION ATTACKS** (模仿 CVE-2019-8457):
   - Add window functions with extreme ROWS BETWEEN ranges (e.g., 999999999 FOLLOWING)
   - Combine multiple window functions in nested expressions
   - Use RANGE BETWEEN with extreme values
   - Mix window functions with large data generation (randomblob, generate_series)
   - Example pattern: `SELECT func(x) OVER (ROWS BETWEEN 1000000000 PRECEDING AND 1000000000 FOLLOWING)`

2. **VIRTUAL TABLE EXPLOITATION** (模仿 CVE-2020-13871):
   - Create FTS3/FTS5 virtual tables
   - Insert large blobs or text data (randomblob(100000+))
   - Use complex MATCH queries with wildcard explosion ('a*' || 'b*' || ... repeat 100+ times)
   - Example pattern: `CREATE VIRTUAL TABLE t USING fts3(x); ... SELECT * FROM t WHERE MATCH 'pattern*'`

3. **PRINTF/FORMAT STRING ATTACKS** (模仿 CVE-2022-35737):
   - Inject printf() calls with extreme format width specifiers
   - Use %.*c, %999999999d, %2147483647s patterns
   - Combine with randomblob or long strings
   - Example pattern: `SELECT printf('%.*c', 2147483647, 'x')`

4. **RECURSIVE CTE BOMBS** (模仿 CVE-2020-13632):
   - Add WITH RECURSIVE with large iteration limits (50000+)
   - Create recursive structures with UNION ALL
   - Combine with aggregates or complex expressions
   - Example pattern: `WITH RECURSIVE c AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x<100000) SELECT * FROM c`

5. **INTEGER OVERFLOW TRIGGERS** (模仿 Example 5):
   - Use MAX_INT (9223372036854775807) in arithmetic operations
   - CAST extreme string values to INTEGER
   - Arithmetic: MAX_INT + 1, MAX_INT * 2, etc.
   - Example pattern: `SELECT CAST(9223372036854775807 AS INTEGER) + 1`

6. **TYPE CONFUSION & CAST CHAOS** (模仿 Example 6):
   - Force CAST between incompatible types (blob→int, float→text, etc.)
   - Use UNION with mismatched column types
   - Combine extreme values with CAST (1e308, randomblob(1000000))
   - Example pattern: `SELECT CAST(randomblob(100000) AS INTEGER) UNION ALL SELECT CAST(1e308 AS INTEGER)`

7. **AGGREGATE NESTING ATTACKS** (模仿 Example 7):
   - Nest multiple aggregates (SUM(AVG(MAX(...))))
   - Combine with window functions
   - Use large data sources (randomblob, generate_series)
   - Example pattern: `SELECT SUM(AVG(x)) OVER (...) FROM (SELECT randomblob(1000) FROM ...)`

8. **TRIGGER RECURSION** (模仿 Example 8):
   - Create self-referencing triggers
   - AFTER INSERT/UPDATE triggers that modify the same table
   - Cascading trigger chains
   - Example pattern: `CREATE TRIGGER t AFTER INSERT ON x BEGIN INSERT INTO x SELECT ...; END`

9. **MEMORY STRESS PATTERNS**:
   - Use randomblob() with extreme sizes (100000+)
   - Generate large result sets (CROSS JOIN, generate_series)
   - String concatenation bombs ('x' || 'x' || ... repeat many times)
   - Example pattern: `SELECT randomblob(2147483647)` or `SELECT 'a' || 'b' || ... (repeat 10000 times)`

10. **CONSTRAINT VIOLATION PATTERNS**:
   - Combine OR REPLACE/OR IGNORE with constraint conflicts
   - Foreign key cascading with circular references
   - CHECK constraints that reference complex expressions
   - Example pattern: `INSERT OR REPLACE INTO t PRIMARY KEY violations`

⚠️ CRITICAL CONSTRAINTS:
1. **Execution time**: Keep operations fast (<1 second). Avoid actual infinite loops, but create complex-enough structures that approach time limits.
2. **Syntactic validity**: Generated SQL MUST be syntactically correct for {target_dbms} version {dbms_version}.
3. **Pure SQL**: Output only SQL statements, no comments or explanations in the code block.
4. **Semicolon termination**: Each statement ends with `;`.

---

## 🎲 MUTATION GUIDELINES

**Intensity**: **EXTREME** - This is {target_dbms} v{dbms_version}, apply patterns from the crash examples above

**What to do**:
1. **Study the 8 crash examples** at the top - these are REAL CVEs
2. **Identify 3-5 patterns** that can be applied to the input SQL
3. **Combine patterns** for maximum crash potential (e.g., window function + extreme values + type confusion)
4. **Add 5-20 new SQL statements** that implement these patterns
5. **Keep the original SQL's tables/data** but transform the queries aggressively

**What to prioritize**:
- ✅ Window functions with extreme ranges (999999999)
- ✅ printf() with extreme format widths (%2147483647d)
- ✅ WITH RECURSIVE with large iterations (50000+)
- ✅ CAST with incompatible types + extreme values
- ✅ FTS3/FTS5 virtual tables with wildcard explosions
- ✅ randomblob() with extreme sizes (1000000+)
- ✅ Self-referencing triggers
- ✅ Integer overflow arithmetic (MAX_INT + 1)

**What to avoid**:
- ❌ Simple value changes (that's for constant mutation)
- ❌ Minor tweaks (we want RADICAL transformation)
- ❌ Generic complexity without crash potential
- ❌ Patterns NOT based on the examples above

---

## 📥 INPUT TEST CASE

Transform this SQL using crash-inducing patterns:

```sql
{sql}
```

---

## 📤 OUTPUT FORMAT

Return ONLY the mutated SQL wrapped as:

```sql
(your crash-inducing mutated SQL here)
```

**No explanations, no comments, just pure SQL.**

---

## 🚀 NOW GENERATE

Apply 3-5 crash-inducing patterns from the examples above to transform the input SQL into a {target_dbms} v{dbms_version} crash trigger. 

**Remember**: You're not just making it complex - you're applying REAL vulnerability patterns that ACTUALLY crashed SQLite!
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
        structural_mutate_success = False
        while True:
            structural_mutate_llm_start_time = time.time()
            my_chilo_factory.structural_mutator_logger.info(f"seed_id：{target_seed_id}，准备调用LLM进行结构化变异")
            after_mutate_testcase,up_token, down_token = my_chilo_factory.llm_tool_structural_mutator.chat_llm(prompt, system_prompt)
            all_up_token += up_token
            all_down_token += down_token
            llm_count += 1
            structural_mutate_llm_end_time = time.time()
            llm_use_time += structural_mutate_llm_end_time - structural_mutate_llm_start_time
            my_chilo_factory.structural_mutator_logger.info(f"seed_id：{target_seed_id}，调用LLM结束，用时：{structural_mutate_llm_end_time-structural_mutate_llm_start_time:.2f}s")
            after_mutate_testcase = my_chilo_factory.llm_tool_structural_mutator.get_sql_block_content(after_mutate_testcase)  # 提取内容
            try:
                after_mutate_testcase = after_mutate_testcase[0]
                structural_mutate_success = True
                break
            except:
                #说明生成格式出现错误，需要从新生成
                llm_error_count += 1
                my_chilo_factory.structural_mutator_logger.warning(f"seed_id：{target_seed_id}，LLM生成格式错误（第{llm_error_count}次），正在重新生成")
                # 检查是否超过最大重试次数
                if llm_error_count >= my_chilo_factory.llm_format_error_max_retry:
                    my_chilo_factory.structural_mutator_logger.error(
                        f"seed_id：{target_seed_id}，格式错误次数超过上限{my_chilo_factory.llm_format_error_max_retry}，使用原始SQL")
                    after_mutate_testcase = seed_sql  # 使用原始SQL作为fallback
                    structural_mutate_success = True  # 标记为成功以继续流程
                    break
                continue

        # 只有成功才加入种子池
        if not structural_mutate_success:
            my_chilo_factory.structural_mutator_logger.warning(f"seed_id：{target_seed_id}，结构化变异失败，跳过")
            continue  # 跳过后续处理，继续下一个任务

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

        