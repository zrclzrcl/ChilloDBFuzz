"""
LLM调用相关的封装好的函数
"""
import re
import time
import threading

from openai import OpenAI
import logging
class LLMTool:
    # 类级别的共享计数器（所有实例共享）
    _global_request_count = 0
    _global_count_lock = threading.Lock()
    
    def __init__(self, llm_api_key, llm_model, base_url, logger:logging.Logger):
        """
        初始化函数
        :param llm_api_key: LLM的APIKey
        :param llm_model: 选择的LLM模型
        :param base_url: LLM的baseURL
        """
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.base_url = base_url
        self.logger = logger
        
        # 复用 OpenAI client 实例，提高性能
        self.client = OpenAI(
            api_key=self.llm_api_key,
            base_url=self.base_url,
        )
        self.logger.info(f"LLM工具已实例化 (模型: {llm_model})")

    def chat_llm(self, prompt: str, system_prompt = "You are a DBMS fuzzing expert. Carefully reason step-by-step following the user's instructions, then provide the result."):
        """
        :param prompt:      提示词字典，需要按照{role}
        :return:                  调用LLM后LLM返回的结果
        """
        # 使用类级别的全局计数器，所有LLM实例共享
        with LLMTool._global_count_lock:
            LLMTool._global_request_count += 1
            count_now = LLMTool._global_request_count
        
        self.logger.info(f"LLM 第{count_now}次请求准备开始 (模型: {self.llm_model})")
        start_time = time.time()
        while True:
            try:
                # 复用 client 实例（OpenAI SDK 内部已做线程安全处理）
                response = self.client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                )
                self.logger.info(f"LLM工具已实例化，第{count_now}次请求成功并结束，用时：{time.time()-start_time:.2f}s")
                return response.choices[0].message.content, response.usage.prompt_tokens, response.usage.completion_tokens
            except Exception as e:
                self.logger.info(f"LLM工具已实例化，第{count_now}次请求失败！错误信息：{e}")
                self.logger.info(f"正在重试第{count_now}次请求")
                continue

    def get_sql_block_content(self, all_content: str):
        """
        从字符串中提取所有 ```sql ... ``` 代码块内的内容并返回列表。

        支持的形式例如：
            ```sql
            SELECT * FROM t;
            ```
        也支持多于 3 个反引号的 fence（比如 ````sql ... ````）以及 SQL 大小写变体。

        参数:
            all_content: 包含一个或多个 markdown 风格代码块的文本

        返回:
            List[str] - 每个匹配到的 sql 代码块内容
        """
        # 匹配格式：开头若干反引号（3 个或更多），可有空格，语言标识 sql（大小写不敏感），可跟换行或空格，
        # 然后捕获任意内容，直到出现同样数量的反引号结束。
        pattern = re.compile(
            r'(?P<fence>`{3,})\s*sql(?:\r?\n)?(?P<code>[\s\S]*?)(?P=fence)',
            flags=re.IGNORECASE
        )

        results = []
        for m in pattern.finditer(all_content):
            code = m.group('code')
            # 去掉开头和结尾的多余空行，但保留内部缩进和换行
            code = code.strip('\n')
            results.append(code)
        return results

    def get_python_block_content(self, all_content: str):
        """
        从字符串中提取所有 ```python ... ``` 代码块内的内容并返回列表。

        支持的形式例如：
            ```python
            print("hello")
            ```

        也支持多于 3 个反引号的 fence（比如 ````python ... ````），语言标识大小写不敏感。

        参数:
            all_content: 包含一个或多个 markdown 风格代码块的文本

        返回:
            List[str] - 每个匹配到的 python 代码块内容
        """
        pattern = re.compile(
            r'(?P<fence>`{3,})\s*python(?:\r?\n)?(?P<code>[\s\S]*?)(?P=fence)',
            flags=re.IGNORECASE
        )

        results = []
        for m in pattern.finditer(all_content):
            code = m.group('code')
            # 去掉开头和结尾的多余空行，但保留内部缩进和换行
            code = code.strip('\n')
            results.append(code)
        return results

