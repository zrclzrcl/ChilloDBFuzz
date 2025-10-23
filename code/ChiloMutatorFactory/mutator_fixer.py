import importlib.util
import os
import time
import traceback
from typing import List

from . import chilo_factory
from .ChiloMutator import ChiloMutator


def get_fix_syntax_prompt(err_code, err_msg):
    prompt = f"""
You are an expert in repairing Python code. The following code is used for SQL mutation but encountered an error during execution.  
Please analyze the error and fix the code so that it can be invoked successfully and the mutate() function can execute properly to generate mutation results.

Requirements:
1. Preserve the original logic of the code;
2. Only fix the parts related to the error;
3. Ensure that mutate() can be correctly called;
4. The code must be directly runnable, without any explanatory comments or descriptions;
5. The generated result must be enclosed within ```python\n (your fixed code)\n```, and there should be only one such code block for automated extraction.

Error message:
{err_msg}

Erroneous code:
```python
{err_code}
```
"""
    return prompt

def get_fix_semantics_prompt(masked_sql, err_code, err_msg):
    err_msg_str =  '\n'.join(err_msg)
    prompt = f"""
You are a DBMS fuzzing expert and a Python code repair specialist.
Your task is to fix the following Python code used for mutating SQL statements, **without rewriting its overall logic structure**.

### Task Background
This code is designed to:
Identify masked parts in SQL statements and perform two types of mutations:
1. **Deterministic mutation**: select one appropriate value from a predefined candidate list;
2. **Random mutation**: perform AFL-style random replacements to generate abnormal values and increase crash likelihood;
3. The code must include a method named `mutate()` that can be called dynamically from external modules.

During each mutation round, a subset of masks should be randomly selected for mutation, while unselected masks must retain their original values (from the `ori` field).

Mask format:
[CONSTANT, number:<n>, type:<type>, ori:<original_value>]

Example:
INSERT INTO t1 VALUES ([CONSTANT, number:1, type:smallint(4), ori:9410], [CONSTANT, number:2, type:smallint(4), ori:9412]);
---
### Possible Semantic Issues
You should fix the following **semantic errors**, rather than rewriting the entire code:
1. **Mask not properly replaced** – the generated SQL still contains `[CONSTANT, ...]` placeholders;
2. **Insufficient randomness** – more than 25% of the generated SQL statements are too similar or identical;
3. **Random logic bias** – the number of selected masks per mutation round is constant or unevenly distributed;
4. **Minor logical issues** – such as missing type handling or incorrect string concatenation.
---
### Repair Objectives
- Modify only the necessary logic to correct semantic errors;
- Keep original function names, variable names, structure, and calling conventions;
- Ensure that the output SQL no longer contains any mask placeholders;
- Improve the diversity of random mutations (e.g., by enhancing random selection, mutation range, or candidate variety);
- Do not change the overall program structure or external interface.
---
### Input Context
Original masked SQL to be mutated:
{masked_sql}

Original code:
{err_code}

Detected semantic issues:
{err_msg_str}
---
### Output Requirements
When providing the repaired code, **place the entire fixed program inside the following code block**:
```python
(repaired full code)
```
Do not include explanations, comments, or any non-code text inside the code block;
Do not rewrite the entire program — fix only the semantic errors while keeping the existing structure.
"""
    return prompt
def call_mutate_from_file(filepath):
    """动态加载指定的Python文件并调用 mutate() 函数"""
    filepath = os.path.abspath(filepath)
    module_name = os.path.splitext(os.path.basename(filepath))[0]  # 例如 mu_1_1

    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # 执行文件内容，加载为模块对象

    if hasattr(module, "mutate"):
        return module.mutate()  # 调用 mutate 函数并返回结果
    else:
        raise AttributeError(f"错误码：1203 该变异器中未找到 mutate() 函数")

def fix_mutator(my_chilo_factory: chilo_factory.ChiloFactory, thread_id=0):
    """
    用于修复变异器的线程方法
    :param my_chilo_factory: 传递过来的实例化chilo工厂
    :param thread_id: 线程ID，用于区分不同的fixer线程
    :return: 无返回值
    """
    # 验证一共有如下的几个流程
    # 1. 可正确调用
    # 2. 调用生成的测试用例中不包括任何掩码
    # 3. 多次生成的结果不同，具有随机性
    # 4. 每有一个条件不满足，就要从新的修复
    my_chilo_factory.mutator_fixer_logger.info(f"变异器修复器[线程{thread_id}]已启动~")
    
    # 为每个线程创建独立的临时文件路径
    thread_tmp_path = my_chilo_factory.mutator_fix_tmp_path.replace(".py", f"_thread{thread_id}.py")
    
    while True: #每次循环处理一个
        all_start_time = time.time()
        syntax_fix_use_time_all = 0
        syntax_fix_use_time_llm = 0
        llm_use_count = 0
        syntax_error_count = 0
        syntax_llm_format_error_count = 0
        syntax_llm_count = 0
        syntax_fix_up_token_all = 0
        syntax_fix_down_token_all = 0
        sematic_fix_use_time_all = 0
        sematic_mask_error_count = 0
        sematic_random_error_count = 0
        semantic_error_count = 0
        semantic_error_llm_use_time = 0
        semantic_error_llm_count = 0
        semantic_llm_format_error = 0
        semantic_up_token_all = 0
        semantic_down_token_all = 0
        at_last_is_all_correct = True
        my_chilo_factory.mutator_fixer_logger.info(f"[线程{thread_id}]等待接收变异器修复任务")
        need_fix = my_chilo_factory.fix_mutator_list.get()  #先从队列中取一个用来修复
        fix_seed_id = need_fix["seed_id"]
        fix_mutate_time = need_fix["mutate_time"]
        fix_mutator_code = need_fix["mutator_code"]
        my_chilo_factory.mutator_fixer_logger.info(f"[线程{thread_id}]接收到变异器修复任务，seed_id：{fix_seed_id}，变异次数：{fix_mutate_time}")
        while True: #用于检测修复的循环
            # 先保存到临时文件（使用线程独立的临时文件）
            my_chilo_factory.mutator_fixer_logger.info(
                f"[线程{thread_id}]seed_id：{fix_seed_id}，等待写入临时文件")
            with open(thread_tmp_path, "w", encoding="utf-8") as f:
                f.write(fix_mutator_code)  # 保存到文件
            my_chilo_factory.mutator_fixer_logger.info(
                f"[线程{thread_id}]seed_id：{fix_seed_id}，已写入至临时文件")
            # 准备调用运行一下
            fix_reason = []
            try:
                my_chilo_factory.mutator_fixer_logger.info(
                    f"[线程{thread_id}]seed_id：{fix_seed_id}，准备试运行")
                mutate_result = [call_mutate_from_file(thread_tmp_path) for _ in range(my_chilo_factory.fix_mutator_try_time)]
                # 这里证明至少语法没问题，那就检测并修复修复语义
                sematic_fix_start_time = time.time()
                my_chilo_factory.mutator_fixer_logger.info(
                    f"seed_id：{fix_seed_id}，试运行成功，语法正确，准备检验语义正确性")
                is_semantics_correct: List[None | bool] = [None, None]
                #语义判断
                #首先是判断，输出的东西中不能含有掩码
                my_chilo_factory.mutator_fixer_logger.info(
                    f"seed_id：{fix_seed_id}，正在进行掩码输出语义检测")
                for each_mutate_result in mutate_result:
                    if "CONSTANT" in each_mutate_result:
                        fix_reason.append("The generated mutated SQL statement still includes mask placeholders.")
                        is_semantics_correct[0] = False
                        sematic_mask_error_count += 1
                        break
                if is_semantics_correct[0] is None:
                    is_semantics_correct[0] = True

                my_chilo_factory.mutator_fixer_logger.info(
                    f"seed_id：{fix_seed_id}，正在进行随机性语义检测")
                #接下来就判断输出的内容的随机性
                if len(set(mutate_result)) < my_chilo_factory.fix_mutator_try_time/4:
                    #说明超过一半都是一样的，那可不行
                    is_semantics_correct[1] = False
                    sematic_random_error_count += 1
                    fix_reason.append("The generated return values lack sufficient randomness, with more than 25% of the results being identical.")
                else:
                    is_semantics_correct[1] = True

                my_chilo_factory.mutator_fixer_logger.info(
                    f"seed_id：{fix_seed_id}，语义检测结果为：{is_semantics_correct}")
                if all(is_semantics_correct) or semantic_error_count >= my_chilo_factory.semantic_fix_max_time:
                    #进入到这里，说明有两个可能性：修复次数超过最大尝试次数，表示放弃
                    #另一个可能性：完全正确
                    if all(is_semantics_correct):
                        #说明语法完全正确
                        my_chilo_factory.mutator_fixer_logger.info(
                            f"seed_id：{fix_seed_id}，生成的变异器语义正确！经过{syntax_error_count}次语法修复 + {semantic_error_count}次语义修复")
                        at_last_is_all_correct = True
                    else:
                        my_chilo_factory.mutator_fixer_logger.info(
                            f"seed_id：{fix_seed_id}，生成的变异器语义不正确！但以及达到了最高修复次数上限 经过{syntax_error_count}次语法修复 + {semantic_error_count}次语义修复")
                        at_last_is_all_correct = False
                    #语义完全正确，则跳出循环

                    sematic_fix_end_time = time.time()
                    sematic_fix_use_time_all += sematic_fix_end_time - sematic_fix_start_time
                    break
                else:
                    semantic_error_count += 1
                    #将语义问题向LLM反馈，并修复
                    my_chilo_factory.mutator_fixer_logger.info(
                        f"seed_id：{fix_seed_id}，正在进行变异器语义修复")
                    semantics_prompt = get_fix_semantics_prompt(my_chilo_factory.all_seed_list.seed_list[fix_seed_id].parser_content, fix_mutator_code, fix_reason)
                    while True:
                        semantics_fix_start_time = time.time()
                        my_chilo_factory.mutator_fixer_logger.info(
                            f"seed_id：{fix_seed_id}，准备调用LLM进行第 {semantic_error_count} 次语义修复")
                        semantics_fix_result, semantic_up_token, semantic_down_token = my_chilo_factory.llm_tool_box.chat_llm(semantics_prompt)
                        llm_use_count += 1
                        semantic_error_llm_count += 1
                        semantics_fix_result = my_chilo_factory.llm_tool_box.get_python_block_content(semantics_fix_result)
                        semantic_up_token_all += semantic_up_token
                        semantic_down_token_all += semantic_down_token
                        my_chilo_factory.mutator_fixer_logger.info(
                            f"seed_id：{fix_seed_id}，调用LLM进行第 {semantic_error_count} 次语义修复结束，用时{time.time()-semantics_fix_start_time:.2f}s")
                        try:
                            fix_mutator_code = semantics_fix_result[0]
                            break
                        except:
                            my_chilo_factory.mutator_fixer_logger.warning(
                                f"seed_id：{fix_seed_id}，调用LLM进行第 {semantic_error_count} 次语义修复时格式错误，准备重试")
                            semantic_llm_format_error += 1
                            continue
                    sematic_fix_end_time = time.time()
                    sematic_fix_use_time_all += sematic_fix_end_time - semantics_fix_start_time
                    continue
            except Exception as e:
                syntax_fix_start_time = time.time()
                syntax_error_count += 1
                my_chilo_factory.mutator_fixer_logger.info(
                    f"seed_id：{fix_seed_id}，试运行失败，出现语法错误，准备进行第 {syntax_error_count} 次语法修复")
                error_trace = traceback.format_exc()
                # 出问题那就是语法有问题，调用LLM修复
                fix_syntax_prompt = get_fix_syntax_prompt(fix_mutator_code, error_trace)
                while True:
                    syntax_fix_start_time_llm = time.time()
                    my_chilo_factory.mutator_fixer_logger.info(
                        f"seed_id：{fix_seed_id}，等待调用LLM修复第 {syntax_error_count} 次语法问题")
                    llm_syntax_fix, syntax_fix_up_token, syntax_fix_down_token = my_chilo_factory.llm_tool_box.chat_llm(fix_syntax_prompt, "You are an expert in debugging and repairing Python code. Fix the given Python code based on the user's requirements.")
                    llm_use_count += 1
                    syntax_llm_count += 1
                    syntax_fix_up_token_all += syntax_fix_up_token
                    syntax_fix_down_token_all += syntax_fix_down_token
                    llm_syntax_fix = my_chilo_factory.llm_tool_box.get_python_block_content(llm_syntax_fix)
                    syntax_fix_end_time_llm = time.time()
                    my_chilo_factory.mutator_fixer_logger.info(
                        f"seed_id：{fix_seed_id}，调用LLM修复第 {syntax_error_count} 次语法问题结束，用时：{syntax_fix_end_time_llm - syntax_fix_start_time_llm:.2f}s")
                    syntax_fix_use_time_llm += syntax_fix_end_time_llm - syntax_fix_start_time_llm
                    semantic_error_llm_use_time += syntax_fix_end_time_llm - syntax_fix_start_time_llm
                    try:
                        fix_mutator_code = llm_syntax_fix[0]
                        my_chilo_factory.mutator_fixer_logger.info(
                            f"seed_id：{fix_seed_id}，第 {syntax_error_count} 次语法修复成功，准备进行下一轮检测")
                        syntax_fix_end_time = time.time()
                        syntax_fix_use_time_all += syntax_fix_end_time - syntax_fix_start_time
                        break
                    except:
                        #出问题，表示输出格式有问题，从新来
                        syntax_llm_format_error_count += 1
                        my_chilo_factory.mutator_fixer_logger.warning(
                            f"seed_id：{fix_seed_id}，第 {syntax_error_count} 次语法修复失败，LLM返回格式错误，准备进行下一轮尝试")

        #到这里说明语法语义都没问题了
        #先获取一个mutator_id（使用锁保护，确保线程安全）
        my_chilo_factory.mutator_fixer_logger.info(
            f"[线程{thread_id}]seed_id：{fix_seed_id}，语法语义修复结束，准备进行FUZZ任务发布")
        
        with my_chilo_factory.mutator_id_lock:
            now_mutator_id = my_chilo_factory.all_seed_list.seed_list[fix_seed_id].next_mutator_id
            my_chilo_factory.all_seed_list.seed_list[fix_seed_id].next_mutator_id += 1
        
        my_chilo_factory.mutator_fixer_logger.info(
            f"[线程{thread_id}]seed_id：{fix_seed_id}，本次对应的mutator_id为{now_mutator_id}")
        
        save_mutator_path = os.path.join(my_chilo_factory.generated_mutator_path,
                                         f"{fix_seed_id}_{now_mutator_id}.py")
        with open(save_mutator_path, "w", encoding="utf-8") as f:
            f.write(fix_mutator_code)  # 保存到文件
        my_chilo_factory.mutator_fixer_logger.info(
            f"[线程{thread_id}]seed_id：{fix_seed_id}，mutator_id：{now_mutator_id} 已保存到文件")

        # 构建一个变异器（使用锁保护mutator_pool操作）
        with my_chilo_factory.mutator_pool_lock:
            mutator_index = my_chilo_factory.mutator_pool.add_mutator(fix_seed_id, now_mutator_id)
        
        mutator_add_in_exec = my_chilo_factory.mutator_pool.mutator_list[mutator_index]
        my_chilo_factory.mutator_fixer_logger.info(
            f"[线程{thread_id}]seed_id：{fix_seed_id}，mutator_id：{now_mutator_id} 变异器构造完成")

        for i in range(fix_mutate_time):
            my_chilo_factory.wait_exec_mutator_list.put(mutator_add_in_exec)    #构建待执行任务
        my_chilo_factory.mutator_fixer_logger.info(
            f"[线程{thread_id}]seed_id：{fix_seed_id}，mutator_id：{now_mutator_id} 任务发布成功，变异次数：{fix_mutate_time}")
        my_chilo_factory.mutator_fixer_logger.info(
            f"[线程{thread_id}]"+"-"*10)
        left_fix_queue_size = my_chilo_factory.fix_mutator_list.qsize()
        all_end_time = time.time()
        my_chilo_factory.write_mutator_fixer_csv(all_end_time, fix_seed_id, all_end_time-all_start_time,
                                          now_mutator_id, fix_mutate_time, llm_use_count, syntax_fix_use_time_all,
                                          syntax_error_count, syntax_llm_format_error_count, syntax_fix_use_time_llm,
                                          syntax_llm_count, syntax_fix_up_token_all, syntax_fix_down_token_all,
                                          sematic_fix_use_time_all, sematic_mask_error_count, sematic_random_error_count,
                                          semantic_error_count, semantic_error_llm_use_time, semantic_error_llm_count,
                                          semantic_llm_format_error, semantic_up_token_all, semantic_down_token_all, left_fix_queue_size, at_last_is_all_correct)
