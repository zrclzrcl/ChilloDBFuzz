"""
这个函数用于对已经解析结束的SQL，使用LLM
生成对应的变异器
"""
import time
from .chilo_factory import ChiloFactory


def  _get_constant_mutator_prompt(parsed_sql:str, target_dbms, dbms_version):
    prompt = f"""
Instruction: You are an **AGGRESSIVE DBMS fuzzing and mutation expert**. The input is a SQL test case with mutation masks. Your task is to generate a Python module that produces **CRASH-INDUCING** mutations.

---

## 🎯 Primary Objective

Generate SQL mutations that:
1. **Maximize crash likelihood** - Target known vulnerability patterns
2. **Explore edge cases** - Use boundary values, type confusion, extreme inputs
3. **High diversity** - Every call to `mutate()` should produce different output

---

## 📋 Input Mask Types

The input SQL contains 4 types of masks:

### 1. CONSTANT
Format: `[CONSTANT, number:X, type:<type>, ori:<value>]`

**Mutation Strategy**:
- **Boundary values**: 0, 1, -1, MAX_INT (9223372036854775807), MIN_INT (-9223372036854775808)
- **Overflow triggers**: MAX_INT + 1, MIN_INT - 1
- **Type-specific edges**:
  - Integers: 127, 128, 32767, 32768, 2147483647, 2147483648
  - Floats: 0.0, 1e308, -1e308, NaN, Infinity
  - Strings: '', 'a'*10000, special chars (NULL byte, unicode edges)
  - Blobs: x'', x'00', x'FF', randomblob(1000000)
- **Special values**: NULL
- **AFL-style mutations**: 
  - Bit flip on original value
  - Byte arithmetic (+1, -1, +128, -128)
  - Integer interesting values (see AFL)

### 2. OPERATOR
Format: `[OPERATOR, number:X, category:<category>, ori:<op>]`

**Mutation Strategy**:
- **Semantic substitution**: Replace with operators from the same category
  - Arithmetic: +, -, *, /, %
  - Comparison: >, <, >=, <=, =, !=, <>, IS, IS NOT
  - Logical: AND, OR
  - Bitwise: &, |, <<, >>
- **Cross-category**: Occasionally try operators from different categories (may cause errors, which is valuable for testing)

### 3. FUNCTION
Format: `[FUNCTION, number:X, category:<category>, ori:<func>]`

**Mutation Strategy**:
- **Same-category substitution**: Replace with functions from the same category
  - Aggregate: SUM → AVG, COUNT, MAX, MIN, TOTAL, GROUP_CONCAT
  - Scalar numeric: ABS → ROUND, CEILING, FLOOR, SIGN, SQRT
  - Scalar string: UPPER → LOWER, LENGTH, TRIM, SUBSTR, REPLACE
  - Datetime: datetime → date, time, julianday, strftime
- **Cross-category** (advanced): Try incompatible functions to trigger type errors
  - Example: SUM → UPPER (aggregate → string function)

### 4. KEYWORD
Format: `[KEYWORD, number:X, context:<context>, ori:<keyword_phrase>]`

**Mutation Strategy** (context-specific):

- **constraint**: NOT NULL ↔ UNIQUE ↔ PRIMARY KEY ↔ <empty>
- **conflict**: OR REPLACE ↔ OR IGNORE ↔ OR FAIL ↔ OR ABORT ↔ OR ROLLBACK ↔ <empty>
- **modifier**: DISTINCT ↔ ALL ↔ <empty>
- **join**: INNER ↔ LEFT ↔ CROSS ↔ <comma>
- **order**: ASC ↔ DESC
- **existence_check**: IF EXISTS ↔ IF NOT EXISTS ↔ <empty>

---

## 🧬 Advanced Mutation Techniques

### AFL-Style Binary Mutations (for CONSTANT)

Implement these strategies for numeric constants:

```python
# Bit flip
value = 1234
mutated = value ^ (1 << random.randint(0, 63))  # Flip one random bit

# Byte arithmetic
mutated = value + random.choice([1, -1, 128, -128, 256, -256])

# Interesting values (AFL's magic numbers)
interesting_8 = [-128, -1, 0, 1, 16, 32, 64, 100, 127]
interesting_16 = [-32768, -129, 128, 255, 256, 512, 1000, 1024, 4096, 32767]
interesting_32 = [-2147483648, -100663046, -32769, 32768, 65535, 65536, 100663045, 2147483647]
```

### Vulnerability-Driven Mutations (for ALL types)

**Known {target_dbms} vulnerability patterns** to incorporate:

1. **Extreme numeric values** (CONSTANT):
   - Window functions with huge frame ranges: 999999999
   - printf format width: %999999999d
   - Large blob allocations: randomblob(2147483647)

2. **Type confusion** (OPERATOR + CONSTANT):
   - CAST with incompatible types
   - Arithmetic on incompatible types
   - Example: CAST(9223372036854775808 AS INTEGER)

3. **Recursive bombs** (KEYWORD + CONSTANT):
   - WITH RECURSIVE with large iteration counts
   - Nested subqueries (depth > 100)

4. **Conflict resolution edge cases** (KEYWORD):
   - OR REPLACE with PRIMARY KEY violations
   - OR IGNORE with UNIQUE constraint violations

---

## 📝 Implementation Requirements

### Module Structure

Generate a complete Python module with:

```python
import random
import struct

# Mask definitions
MASKS = {{
    1: {{'type': 'CONSTANT', 'ori': 10, 'sql_type': 'integer'}},
    2: {{'type': 'OPERATOR', 'ori': '+', 'category': 'arithmetic'}},
    # ... all masks
}}

def mutate() -> str:
    \"\"\"
    Generate one mutated SQL statement.
    Returns: Complete SQL string with all masks replaced.
    \"\"\"
    # Implementation here
    pass
```

### Mutation Logic

**For each call to `mutate()`**:

1. **Select masks to mutate**: Randomly choose 30-70% of masks (at least 1)
2. **Choose mutation mode** for selected masks:
   - 40% - Fixed candidates (boundary values, same-category substitutions)
   - 40% - AFL-style binary mutations (for CONSTANT)
   - 20% - Random/creative mutations (cross-category, extreme values)
3. **Replace masks**: 
   - Selected masks → mutated values
   - Unselected masks → original values
4. **Return valid SQL**: Ensure proper quoting for strings, correct syntax

### Code Quality

- Use **only Python standard library** (random, struct, re, etc.)
- **No side effects**: No prints, no file I/O, no network calls
- **No top-level execution**: No `if __name__ == "__main__":`
- **Error handling**: Handle edge cases gracefully
- **Comments**: Explain mutation choices

---

## 🎯 Target: {target_dbms} version {dbms_version}

### DBMS-Specific Considerations

- SQLite supports: `OR IGNORE`, `OR REPLACE`, etc.
- Window functions: ROWS BETWEEN, RANGE BETWEEN
- FTS3/FTS5 virtual tables: MATCH queries
- Built-in functions: randomblob(), zeroblob(), printf()

---

## 📥 Input SQL

```sql
{parsed_sql}
```

---

## 📤 Output Format

Provide the complete Python module inside a code block:

```python
(entire module here)
```

**Do NOT include**:
- Explanations outside the code block
- Example usage or test code
- Comments explaining the task (only implementation comments)

---

## 🚀 Now Generate

Create a Python module that implements aggressive, crash-inducing mutations for the above SQL targeting {target_dbms} version {dbms_version}.

**Remember**:
- High diversity (different output each time)
- Include AFL-style binary mutations (bit flip, interesting values)
- Target known vulnerability patterns
- Balance fixed candidates (40%), AFL mutations (40%), and random mutations (20%)
"""
    return prompt

def chilo_mutator_generator(my_chilo_factory: ChiloFactory):
    my_chilo_factory.mutator_generator_logger.info("变异器生成器启动成功")
    while True:
        all_start_time = time.time()
        all_up_token = 0
        all_down_token = 0
        llm_count = 0
        llm_error_count = 0
        my_chilo_factory.mutator_generator_logger.info("接收变异器生成任务中~")
        generate_target = my_chilo_factory.wait_mutator_generate_list.get()    #拿一个需要生成变异器的
        my_chilo_factory.mutator_generator_logger.info(f"变异器生成任务接收完毕 任务目标   seed_id：{generate_target['seed_id']}    变异次数：{generate_target['mutate_time']}")
        mutate_time = generate_target['mutate_time']
        parsed_sql = my_chilo_factory.all_seed_list.seed_list[generate_target['seed_id']].parser_content   #拿出对应的已经解析过的内容
        prompt = _get_constant_mutator_prompt(parsed_sql, my_chilo_factory.target_dbms, my_chilo_factory.target_dbms_version)  #构建提示词
        while True:
            start_time = time.time()
            my_chilo_factory.mutator_generator_logger.info(
                f"seed_id：{generate_target['seed_id']}  准备调用LLM，生成变异器")
            mutator_code, up_token, down_token = my_chilo_factory.llm_tool_box.chat_llm(prompt)    #调用LLM
            end_time = time.time()
            all_up_token += up_token
            all_down_token += down_token
            llm_count += 1
            my_chilo_factory.mutator_generator_logger.info(
                f"seed_id：{generate_target['seed_id']}  生成变异器调用结束，用时：{end_time - start_time:.2f}s")
            mutator_code = my_chilo_factory.llm_tool_box.get_python_block_content(mutator_code)  #获取python代码
            try:
                mutator_code = mutator_code[0]
                break
            except:
                #证明输出格式错误
                llm_error_count += 1
                my_chilo_factory.mutator_generator_logger.info(
                    f"seed_id：{generate_target['seed_id']}  LLM生成变异器时格式错误！准备再次生成")

        my_chilo_factory.mutator_generator_logger.info(
            f"seed_id：{generate_target['seed_id']}  LLM生成变异器代码提取成功，准备放入待修复队列")
        my_chilo_factory.fix_mutator_list.put({"seed_id" : generate_target['seed_id'], "mutate_time" : mutate_time, "mutator_code": mutator_code})
        my_chilo_factory.mutator_generator_logger.info(
            f"seed_id：{generate_target['seed_id']}  变异器放入修复队列成功")
        my_chilo_factory.mutator_generator_logger.info("-"*10)
        all_end_time = time.time()
        my_chilo_factory.write_mutator_generator_csv(all_end_time, generate_target['seed_id'], all_end_time-all_start_time,
                                                     end_time-start_time, all_up_token, all_down_token, llm_count,
                                                     llm_error_count, my_chilo_factory.fix_mutator_list.qsize())