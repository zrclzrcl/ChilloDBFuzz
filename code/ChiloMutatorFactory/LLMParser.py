
"""
用于调用LLM对SQL种子进行解析.
"""
import os
import time

from code.ChiloMutatorFactory.chilo_factory import ChiloFactory

def _get_constant_prompt(ori_sql, target_dbms, dbms_version):
    prompt = f"""
Instruction: You are a **DBMS fuzz testing expert**. Your task is to **identify and annotate all constants** in the given MySQL test case one by one.

---

### Annotation Format
Each constant should be annotated as:
[CONSTANT, number:X, type:<type>, ori:<original_value>]

Where:
- **CONSTANT** → marks this token as a constant mask.  
- **number:X** → index of the constant in this test case, starting from 1 and increasing sequentially.  
- **type** → the constant type recognized in the target DBMS (e.g., smallint(4), char, enum_storage_engine, geometry_text, sql_text, etc.).  
- **ori** → the literal value of the constant in the original SQL.

---

### Rules and Requirements

1. **Scope of constants**  
   Include: strings, numbers, date/time values, enum values, and text literals in SQL statements.  
   Exclude: table names, column names, aliases, function names, and SQL keywords.

2. **Type inference**  
   Infer the specific constant type based on context — do not use generic or vague labels.  
   Examples:  
   - `smallint(4)` default `'0000'` → `type:char`  
   - `ENGINE=MyISAM` → `type:enum_storage_engine`  
   - `ST_GeomFromText('LineString(...)')` → `type:geometry_text`  
   - `PREPARE ... FROM "SQL"` → `type:sql_text`

3. **Executability requirement**  
   The annotations are used for fuzzing mutation. After replacing constants with new values, the SQL must still be syntactically valid and executable.

4. **Numbering rule**  
   - Start numbering from **1**, in order of appearance.  
   - Continue numbering across multiple statements without resetting or duplication.

5. **Output format**  
   - The final annotated SQL **must** be wrapped in:  
     \n```sql\n(result)\n```  
   - Do **not** wrap explanations or other text in code blocks.  
   - The result should be a single complete SQL output, easily extractable.

---

### Examples
**Input:**
```sql
SET @previous_binlog_format__htnt542nh=@@GLOBAL.binlog_format; 
SET binlog_format=STATEMENT; 
SET default_storage_engine=ARCHIVE; 
CREATE TABLE t1 ( Period smallint(4) unsigned zerofill DEFAULT '0000' NOT NULL, Varor_period smallint(4) unsigned DEFAULT '0' NOT NULL ) ENGINE=archive; 
INSERT INTO t1 VALUES (9410,9412);
```
**Output:**
```sql
SET @previous_binlog_format__htnt542nh=@@GLOBAL.binlog_format;
SET binlog_format=[CONSTANT, number:1, type:enum_binlog_format, ori:STATEMENT];
SET default_storage_engine=[CONSTANT, number:2, type:enum_storage_engine, ori:ARCHIVE];
CREATE TABLE t1 ( 
Period smallint(4) unsigned zerofill DEFAULT [CONSTANT, number:3, type:char, ori:0000] NOT NULL, 
Varor_period smallint(4) unsigned DEFAULT [CONSTANT, number:4, type:char, ori:0] NOT NULL 
) ENGINE=[CONSTANT, type:enum_storage_engine, ori:archive];
INSERT INTO t1 VALUES ([CONSTANT, number:5, type:smallint(4), ori:9410], [CONSTANT, type:smallint(4), ori:9412]);
```
**Input:**
```sql
CREATE TABLE t1 ( fid INT NOT NULL AUTO_INCREMENT PRIMARY KEY, g GEOMETRY NOT NULL SRID 0, SPATIAL KEY(g) ) ENGINE=MyISAM; 
INSERT INTO t1 (g) VALUES (ST_GeomFromText('LineString(150 150, 150 150)')); 
```
**Output:**
```sql
CREATE TABLE t1 ( fid INT NOT NULL AUTO_INCREMENT PRIMARY KEY, g GEOMETRY NOT NULL SRID 0, SPATIAL KEY(g) ) ENGINE=MyISAM; 
INSERT INTO t1 (g) VALUES (ST_GeomFromText([CONSTANT, number:1, type:geometry_text, ori:LineString(150 150, 150 150)]));
```
Now, please annotate the following SQL statement, which is used to test {target_dbms} version {dbms_version}:
```sql
{ori_sql}
```
"""
    return prompt

def chilo_parser(chilo_factory: ChiloFactory):
    #这里需要单独启动一个线程，用于对SQL进行处理
    chilo_factory.parser_logger.info("解析器启动成功！")
    while True:
        #首先要尝试从工厂的待parse的队列中取一个
        all_start_time = time.time()
        llm_usd_time_all = 0
        up_token_all = 0
        down_token_all = 0
        llm_use_count = 0
        llm_format_error_count = 0
        chilo_factory.parser_logger.info("解析器正在等待解析任务~")
        parse_target = chilo_factory.wait_parse_list.get()
        chilo_factory.parser_logger.info(f"解析任务获取成功：seed_id:{parse_target['seed_id']}")
        #取一个之后，判断该目标是否已经被解析过
        if chilo_factory.all_seed_list.seed_list[parse_target['seed_id']].is_parsed:
            #说明已经被解析过了，则将这个种子加入待变异队列
            chilo_factory.parser_logger.info(f"seed_id:{parse_target['seed_id']} 已经被解析过，正在放入变异器生成队列")
            chilo_factory.wait_mutator_generate_list.put(parse_target)
            chilo_factory.parser_logger.info(f"seed_id:{parse_target['seed_id']} 放入变异器生成队列成功")
            tmp_seed_is_fuzz_flag_for_csv = 1
        else:
            #说明还没有被解析过，需要先进行解析...
            chilo_factory.parser_logger.info(f"seed_id:{parse_target['seed_id']} 没有被解析过，进入解析过程")
            need_parse_sql = chilo_factory.all_seed_list.seed_list[parse_target['seed_id']].seed_sql
            while True:
                parse_start_time = time.time()
                chilo_factory.parser_logger.info(f"seed_id:{parse_target['seed_id']} 调用LLM解析开始")
                prompt = _get_constant_prompt(need_parse_sql, chilo_factory.target_dbms, chilo_factory.target_dbms_version)
                parse_msg, up_token, down_token = chilo_factory.llm_tool_box.chat_llm(prompt)
                up_token_all += up_token
                down_token_all += down_token
                parser_end_time = time.time()
                llm_use_count += 1
                chilo_factory.parser_logger.info(
                    f"seed_id:{parse_target['seed_id']} LLM解析结束，用时：{parser_end_time - parse_start_time:.2f}s")
                llm_usd_time_all += parser_end_time - parse_start_time
                parse_msg = chilo_factory.llm_tool_box.get_sql_block_content(parse_msg)
                try:
                    parse_msg = parse_msg[0]
                    break
                except:
                    llm_format_error_count += 1
                    chilo_factory.parser_logger.warning(f"seed_id:{parse_target['seed_id']} LLM解析内容提取失败，LLM生成格式错误，重新解析...")
            chilo_factory.parser_logger.info(
                f"seed_id:{parse_target['seed_id']} LLM解析内容提取成功")
            save_parsed_sql_path = os.path.join(chilo_factory.parsed_sql_path, f"{parse_target['seed_id']}.txt")
            chilo_factory.parser_logger.info(
                f"seed_id:{parse_target['seed_id']} 解析结果存入文件中")
            with open(save_parsed_sql_path, "w", encoding="utf-8") as f:
                f.write(parse_msg)  #保存到文件中
            chilo_factory.parser_logger.info(
                f"seed_id:{parse_target['seed_id']} 解析结果存入文件成功")
            chilo_factory.all_seed_list.seed_list[parse_target['seed_id']].parser_content = parse_msg
            chilo_factory.all_seed_list.seed_list[parse_target['seed_id']].is_parsed = True
            #然后要将这个加入到待变异中
            chilo_factory.parser_logger.info(
                f"seed_id:{parse_target['seed_id']} 准备加入到变异器待生成队列中")
            chilo_factory.wait_mutator_generate_list.put(parse_target)
            tmp_seed_is_fuzz_flag_for_csv = 0
            chilo_factory.parser_logger.info(f"seed_id:{parse_target['seed_id']} 放入变异器生成队列成功")
            chilo_factory.parser_logger.info(f"-"*10)
        left_parser_queue_size = chilo_factory.wait_parse_list.qsize()
        all_end_time = time.time()
        chilo_factory.write_parser_csv(all_end_time, parse_target['seed_id'], parse_target['mutate_time'],
                                       tmp_seed_is_fuzz_flag_for_csv, llm_usd_time_all, up_token_all, down_token_all,
                                       llm_use_count, llm_format_error_count, all_end_time-all_start_time,
                                       chilo_factory.all_seed_list.seed_list[parse_target['seed_id']].chose_time,
                                       left_parser_queue_size)