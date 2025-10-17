"""
这个函数用于对已经解析结束的SQL，使用LLM
生成对应的变异器
"""
import time
from ChiloMutatorFactory.chilo_factory import ChiloFactory


def  _get_constant_mutator_prompt(parsed_sql:str, target_dbms, dbms_version):
    prompt = f"""
Instruction: You are a DBMS fuzzing and SQL mutation expert. The input below is a test case annotated with "constant mutation masks" (mask format defined below). Your job is to produce a Python module that is import-safe and exposes a single callable mutation interface:

    mutate() -> str

Important module constraints (must be obeyed):
- The produced Python code must be importable without side effects. **Do NOT** include any top-level executable code such as `if __name__ == "__main__":`, command-line parsing, or code that runs on import.
- **Do NOT** print to stdout, write files, or perform network I/O. The module must be pure (it may use module-level constants or helper functions).
- `mutate()` must accept **no required arguments** (no parameters) and must return a single `str` containing one fully mutated, executable SQL test case (possibly many statements separated by `;`) with **no masks remaining**.
- Use **Python 3.12** and **only standard library** modules.
- Keep code concise, well-commented, and robust (handle errors internally and raise meaningful exceptions if something is wrong).

Target test case (for testing {target_dbms} version {dbms_version}):
{parsed_sql}

Constant mask format (appearing in the input):
[CONSTANT, number:<n>, type:<type>, ori:<original_value>]
Example:
INSERT INTO t1 VALUES ([CONSTANT, number:1, type:smallint(4), ori:9410], [CONSTANT, number:2, type:smallint(4), ori:9412]);

Task & Requirements (precise and enforceable):

1. Parsing:
   - Parse every mask in `{parsed_sql}` and capture its `number`, `type`, `ori`, and the token's SQL context (e.g., INSERT value, WHERE predicate, LIMIT, function argument, comparison, etc.).
   - Do not change schema identifiers (table/column names), only replace masks with concrete values.

2. Mutation candidates:
   - For each mask produce at least **8 diverse, context-aware candidates** based on the annotated `type`, `ori`, and SQL position.
   - Candidate categories should include (but are not limited to): boundary values, out-of-range, negatives, zero, NULL (only when valid in context), empty string, very long strings, SQL-injection-like payloads (escaped so the resulting SQL is syntactically valid), malformed dates, floating-point edge cases, binary/hex values where appropriate, LIKE patterns, control chars, type-conversion triggers, AFL-style binary mutations, and semantic special values (e.g., MAX_INT, MIN_INT).

3. Two mutation modes per mask:
   - Deterministic: select one candidate from the candidate list (useful for reproducible tests).
   - Random: produce AFL-style / random-bit mutated values (to increase crash discovery).

4. mutate() behavior:
   - Each call to `mutate()` must randomly select **at least one** mask to replace with a non-`ori` candidate; masks not selected must be replaced by their `ori` value (no masks left).
   - `mutate()` must return a complete SQL string (type `str`) with **all masks replaced** and syntactically valid for the annotated types (numbers unquoted, strings quoted and escaped, dates parsable, etc.).
   - Preserve original comments and statement separators; do not inject or remove semicolons or comments.
   - Ensure high variation across multiple `mutate()` calls (i.e., probability of repeating the exact same output should be low).
   - `mutate()` must not perform side effects (no file writes, no prints).

5. Implementation constraints and quality:
   - Only use standard library (e.g., `re`, `random`, `datetime`, `json`, `itertools`, `math`, `binascii`).
   - Provide a modular mutation-strategy factory: a function that, given a mask's `type`/`ori`/context, returns the candidate list and a function to generate random variants.
   - Include inline comments explaining mutation choices and any context assumptions.
   - Include minimal but sufficient error checking; if the input masks cannot be parsed, raise a descriptive Exception (do not crash silently).

6. Output format for your reply when you produce the code:
   - Provide **only** the Python module inside a single fenced code block labeled `python`:
     ```python
     (entire module text here)
     ```
   - Do **not** include any additional explanatory text inside the code block. Any human-readable explanation must be outside the code block (but when the LLM is used programmatically you can require it to return only the code block to facilitate automated extraction).

7. Notes for implementer:
   - The `call_mutate_from_file(filepath)` loader in the caller will import this module and call `mutate()` with no arguments; ensure the function signature matches exactly.
   - Avoid deterministic seeding unless used only to produce reproducible "deterministic" candidates; for the random mode rely on `random` module without global seeding.
   - Keep the module size reasonable and avoid heavy complexity; focus on high-quality candidate generation and correct replacement semantics.

Now, produce the Python module that satisfies all the above constraints.
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
        my_chilo_factory.mutator_generator_logger.info(f"变异器生成任务接收完毕 任务目标   seed_id：{generate_target["seed_id"]}    变异次数：{generate_target['mutate_time']}")
        mutate_time = generate_target["mutate_time"]
        parsed_sql = my_chilo_factory.all_seed_list.seed_list[generate_target["seed_id"]].parser_content   #拿出对应的已经解析过的内容
        prompt = _get_constant_mutator_prompt(parsed_sql, my_chilo_factory.target_dbms, my_chilo_factory.target_dbms_version)  #构建提示词
        while True:
            start_time = time.time()
            my_chilo_factory.mutator_generator_logger.info(
                f"seed_id：{generate_target["seed_id"]}  准备调用LLM，生成变异器")
            mutator_code, up_token, down_token = my_chilo_factory.llm_tool_box.chat_llm(prompt)    #调用LLM
            end_time = time.time()
            all_up_token += up_token
            all_down_token += down_token
            llm_count += 1
            my_chilo_factory.mutator_generator_logger.info(
                f"seed_id：{generate_target["seed_id"]}  生成变异器调用结束，用时：{end_time - start_time:.2f}s")
            mutator_code = my_chilo_factory.llm_tool_box.get_python_block_content(mutator_code)  #获取python代码
            try:
                mutator_code = mutator_code[0]
                break
            except:
                #证明输出格式错误
                llm_error_count += 1
                my_chilo_factory.mutator_generator_logger.info(
                    f"seed_id：{generate_target["seed_id"]}  LLM生成变异器时格式错误！准备再次生成")

        my_chilo_factory.mutator_generator_logger.info(
            f"seed_id：{generate_target["seed_id"]}  LLM生成变异器代码提取成功，准备放入待修复队列")
        my_chilo_factory.fix_mutator_list.put({"seed_id" : generate_target["seed_id"], "mutate_time" : mutate_time, "mutator_code": mutator_code})
        my_chilo_factory.mutator_generator_logger.info(
            f"seed_id：{generate_target["seed_id"]}  变异器放入修复队列成功")
        my_chilo_factory.mutator_generator_logger.info("-"*10)
        all_end_time = time.time()
        my_chilo_factory.write_mutator_generator_csv(all_end_time, generate_target["seed_id"], all_end_time-all_start_time,
                                                     end_time-start_time, all_up_token, all_down_token, llm_count,
                                                     llm_error_count, my_chilo_factory.fix_mutator_list.qsize())