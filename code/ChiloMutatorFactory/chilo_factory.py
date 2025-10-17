"""
chillo的工厂！

主要定义了FUZZ过程中需要用到的一系列API函数，并封装好~
"""
import csv
import importlib.util
import queue
import os
import time

import yaml

from . import llm_tool
from . import seed
from . import ChiloMutator
from . import logger

class ChiloFactory:
    """
    用于管理整个工厂的类
    """
    def __init__(self, config_file_path="./config.yaml"):
        """
        类初始化，需要根据配置文件初始化整个工厂的参数
        :param config_file_path: 给定的配置文件路径，默认为当前文件夹的config.yaml
        """
        self.start_time = time.time()
        self.config_file_path = config_file_path

        with open(self.config_file_path, "r", encoding="utf-8") as f:   #读配置文件
            config = yaml.safe_load(f)

        self.main_log_path = config["LOG"]["MAIN_LOG_PATH"]   #主日志
        self.parser_log_path = config["LOG"]["PARSER_LOG_PATH"]   #解析器日志
        self.mutator_generator_log_path = config["LOG"]["MUTATOR_GENERATOR_LOG_PATH"] #变异器生成器日志
        self.structural_mutator_log_path = config["LOG"]["STRUCTURAL_MUTATOR_LOG_PATH"]   #结构化变异器日志
        self.mutator_fixer_log_path = config["LOG"]["MUTATOR_FIXER_LOG_PATH"]
        self.llm_log_path = config["LOG"]["LLM_LOG_PATH"]

        self.target_dbms = config["TARGET"]["DBMS"]     #目标DBMS
        self.target_dbms_version = config["TARGET"]["DBMS_VERSION"] #目标版本
        self.wait_parse_list = queue.Queue()   #等待SQL解析的队列
        self.wait_mutator_generate_list = queue.Queue()    #等待变异器生成的队列
        self.wait_exec_mutator_list = queue.Queue() #等待执行的队列
        self.structural_mutator_list = queue.Queue()    #等待结构性变异的队列
        self.fix_mutator_list = queue.Queue()
        self.parsed_sql_path = config["FILE_PATH"]["PARSED_SQL_PATH"]
        self.generated_mutator_path = config["FILE_PATH"]["GENERATED_MUTATOR_PATH"]
        self.structural_mutator_path = config["FILE_PATH"]["STRUCTURAL_MUTATE_PATH"]   #结构化变异的文件路径
        self.mutator_fix_tmp_path = config["FILE_PATH"]["MUTATOR_FIX_TMP_PATH"]
        self.mutator_pool = ChiloMutator.ChiloMutatorPool(self.generated_mutator_path)  #一个变异器池
        self.all_seed_list = seed.AFLSeedList() #收到的所有seed的列表
        self.fix_mutator_try_time = config["OTHERS"]["FIX_MUTATOR_TRY_TIME"]

        #下面是CSV文件
        self.mutator_fixer_csv_path = config["CSV"]["MUTATOR_FIXER_CSV_PATH"]
        self.structural_mutator_csv_path = config["CSV"]["STRUCTURAL_MUTATOR_CSV_PATH"]
        self.parser_csv_path = config["CSV"]["PARSER_CSV_PATH"]
        self.main_csv_path = config["CSV"]["MAIN_CSV_PATH"]
        self.mutator_generator_csv_path = config["CSV"]["MUTATOR_GENERATOR_CSV_PATH"]

        self.init_file_path()  # 初始化所有文件路径

        self.main_logger = logger.setup_thread_logger("MainMutator", self.main_log_path)
        self.parser_logger = logger.setup_thread_logger("Parser", self.parser_log_path)
        self.mutator_generator_logger = logger.setup_thread_logger("MutatorGenerator", self.mutator_generator_log_path)
        self.structural_mutator_logger = logger.setup_thread_logger("StructuralMutator", self.structural_mutator_log_path)
        self.mutator_fixer_logger = logger.setup_thread_logger("MutatorFixer", self.mutator_fixer_log_path)
        self.llm_logger = logger.setup_thread_logger("LLM", self.llm_log_path)

        self.llm_tool_box = llm_tool.LLMTool(config["LLM"]["API_KEY"], config["LLM"]["MODEL"],
                                             config["LLM"]["BASE_URL"], self.llm_logger)  # LLM工具


    def init_file_path(self):
        """
        根据配置文件中的文件路径，准备并初始化好文件
        :return: 无返回值
        """

        if not os.path.exists(self.parsed_sql_path):
            # 路径不存在，创建文件夹
            os.makedirs(self.parsed_sql_path, exist_ok=True)
        else:
            # 路径存在，检查是否为空
            if os.path.isdir(self.parsed_sql_path) and os.listdir(self.parsed_sql_path):
                # 目录不为空，终止程序
                exit(1)

        # 检查并处理 generated_mutator_path
        if not os.path.exists(self.generated_mutator_path):
            # 路径不存在，创建文件夹
            os.makedirs(self.generated_mutator_path, exist_ok=True)
        else:
            # 路径存在，检查是否为空
            if os.path.isdir(self.generated_mutator_path) and os.listdir(self.generated_mutator_path):
                # 目录不为空，终止程序
                exit(1)

        if not os.path.exists(self.structural_mutator_path):
            # 路径不存在，创建文件夹
            os.makedirs(self.structural_mutator_path, exist_ok=True)
        else:
            # 路径存在，检查是否为空
            if os.path.isdir(self.structural_mutator_path) and os.listdir(self.structural_mutator_path):
                # 目录不为空，终止程序
                exit(1)

        llm_log_dir =  os.path.dirname(self.llm_log_path)
        main_log_dir =  os.path.dirname(self.main_log_path)
        parser_log_dir =  os.path.dirname(self.parser_log_path)
        mutator_generator_log_dir =  os.path.dirname(self.mutator_generator_log_path)
        structural_mutator_log_dir =  os.path.dirname(self.structural_mutator_log_path)
        mutator_fix_tmp_dir =  os.path.dirname(self.mutator_fix_tmp_path)
        mutator_fixer_log_dir =  os.path.dirname(self.mutator_fixer_log_path)
        mutator_fixer_csv_dir =  os.path.dirname(self.mutator_fixer_csv_path)
        main_csv_dir =  os.path.dirname(self.main_csv_path)
        structural_mutator_csv_dir =  os.path.dirname(self.structural_mutator_csv_path)
        parser_csv_dir =  os.path.dirname(self.parser_csv_path)
        mutator_generator_csv_dir =  os.path.dirname(self.mutator_generator_csv_path)
        os.makedirs(main_log_dir, exist_ok=True)  # 不存在就自动创建
        os.makedirs(parser_log_dir, exist_ok=True)  # 不存在就自动创建
        os.makedirs(mutator_generator_log_dir, exist_ok=True)  # 不存在就自动创建
        os.makedirs(structural_mutator_log_dir, exist_ok=True)  # 不存在就自动创建
        os.makedirs(mutator_fix_tmp_dir, exist_ok=True)
        os.makedirs(mutator_fixer_log_dir, exist_ok=True)
        os.makedirs(llm_log_dir, exist_ok=True)
        os.makedirs(mutator_fixer_csv_dir, exist_ok=True)
        os.makedirs(structural_mutator_csv_dir, exist_ok=True)
        os.makedirs(parser_csv_dir, exist_ok=True)
        os.makedirs(main_csv_dir, exist_ok=True)
        os.makedirs(mutator_generator_csv_dir, exist_ok=True)

        with open(self.parser_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["real_time", "relative_time", "seed_id",
                             "need_mutate_count", "is_parsed", "LLM_use_time",
                             "up_token", "down_token", "LLM_count", "LLM_format_error_count",
                             "all_use_time", "select_count","left_parser_queue_count"])

        with open(self.mutator_fixer_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["real_time", "relative_time", "seed_id", "mutator_id",
                             "need_mutate_count", "all_use_time",  "all_llm_count",
                             "syntax_use_time","syntax_error_count", "syntax_format_error_time",
                             "syntax_llm_use_time","syntax_llm_count","syntax_up_token",
                             "syntax_down_token","sematic_use_time", "semantic_mask_error_count",
                             "semantic_random_error_count","semantic_error_count",
                             "semantic_error_llm_use_time",
                             "semantic_error_llm_count","semantic_llm_format_error",
                             "semantic_up_token", "semantic_down_token","left_fix_queue_count"])

        with open(self.structural_mutator_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["real_time", "relative_time", "seed_id", "new_seed_id",
                             "all_use_time", "llm_up_token", "llm_down_token", "llm_count",
                             "llm_format_error_count", "llm_use_time",
                             "left_structural_mutate_queue_count"])

        with open(self.main_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["real_time", "relative_time", "fuzz_count_seed_number",
                             "fuzz_seed_number", "is_by_ramdom", "fuzz_use_time","now_seed_id",
                             "real_fuzz_seed_id", "real_mutator_id","left_wait_exec_queue_count",
                             "ori_mutate_out_size", "real_mutate_out_size", "is_cut"])
        with open(self.mutator_generator_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["real_time", "relative_time", "seed_id", "use_all_time", "llm_use_time",
                             "llm_up_token", "llm_down_token", "llm_count",
                             "llm_error_count", "left_mutator_generate_queue_count"])
    def write_mutator_generator_csv(self, real_time, seed_id,
                                    use_all_time, llm_use_time, llm_up_token, llm_down_token,
                                    llm_count, llm_error_count, left_mutator_generate_queue_count):
        """
        向变异器生成器CSV中插入一行
        :param real_time: 输入插入时的真实时间
        :param seed_id: 当前种子ID
        :param use_all_time: 生成变异器所用的全部时间
        :param llm_use_time: LLM调用所用时间
        :param llm_up_token: LLM上传token
        :param llm_down_token: LLM补全token
        :param llm_count: LLM调用次数
        :param llm_error_count: LLM出错次数
        :param left_mutator_generate_queue_count: 待生成变异器队列个数
        :return: 无
        """
        with open(self.mutator_generator_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([real_time, real_time-self.start_time,
                             seed_id, use_all_time,
                             llm_use_time, llm_up_token, llm_down_token,
                             llm_count, llm_error_count, left_mutator_generate_queue_count])

    def write_main_csv(self, real_time, fuzz_count_seed_number,
                       fuzz_seed_number, is_by_ramdom,fuzz_use_time, now_seed_id,
                       real_fuzz_seed_id, real_mutator_id,left_wait_exec_queue_count, ori_mutate_out_size,
                       real_mutate_out_size, is_cut):
        """
        向主CSV里面写入一行
        :param real_time: 插入的真实时间
        :param fuzz_count_seed_number: 当前fuzz_count调用的次数
        :param fuzz_seed_number: 当前fuzz被调用的次数
        :param is_by_ramdom: 当前fuzz的结果是否为随机变异器生成的
        :param fuzz_use_time: 本次fuzz所用时间
        :param now_seed_id: 当前本应fuzz的种子
        :param real_fuzz_seed_id: 当前实际被fuzz的种子
        :param real_mutator_id: 当前的变异器id
        :param left_wait_exec_queue_count: 待变异的任务列表剩余数量
        :param ori_mutate_out_size: 变异原始输出大小
        :param real_mutate_out_size: 真正的变异后大小
        :param is_cut:  是否过长被截断
        :return:
        """
        with open(self.main_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([real_time, real_time-self.start_time , fuzz_count_seed_number,
                             fuzz_seed_number, is_by_ramdom, fuzz_use_time,
                             now_seed_id, real_mutator_id, real_fuzz_seed_id, left_wait_exec_queue_count,
                             ori_mutate_out_size,
                             real_mutate_out_size, is_cut])

    def write_parser_csv(self, real_time, seed_id, need_mutate_count, is_parsed, llm_time,
                         up_token, down_token,  llm_count,
                         llm_format_error_count, all_time, select_count,
                         left_parser_queue_count):
        """
        向parser的csv中写入一行
        :param left_parser_queue_count: 队列中排队的个数
        :param llm_format_error_count: 调用输出格式错误测试
        :param llm_count: 调用LLM总次数
        :param down_token: 补全token数
        :param up_token: 上传token数
        :param real_time: 当前真实时间
        :param seed_id: 当前parser被选中的id
        :param need_mutate_count: 被决定的变异的次数
        :param is_parsed: 是否已经被解析了
        :param llm_time: LLM调用所用时间
        :param all_time: 完整过程所用时间
        :param select_count: 当前种子被选中的次数
        :return: 无
        """
        with open(self.parser_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([real_time, real_time - self.start_time, seed_id,
                             need_mutate_count, is_parsed, llm_time, up_token,
                             down_token,llm_count, llm_format_error_count, all_time, select_count,
                             left_parser_queue_count])

    def write_mutator_fixer_csv(self,real_time, seed_id,  all_use_time, mutator_id, need_mutate_count,
                                all_llm_count, syntax_use_time, syntax_error_count, syntax_format_error_time,
                                syntax_llm_use_time,syntax_llm_count,syntax_up_token, syntax_down_token,
                                sematic_use_time, semantic_mask_error_count, semantic_random_error_count,
                                semantic_error_count,semantic_error_llm_use_time,
                                semantic_error_llm_count,
                                semantic_llm_format_error,semantic_up_token, semantic_down_token,left_fix_queue_count ):
        """
        向mutator_fixer的csv中写入一行
        :param need_mutate_count: 需要进行变异的次数
        :param mutator_id: 分配的变异器id
        :param left_fix_queue_count: 队列中剩下的等待fix的个数
        :param real_time: 当前时间
        :param seed_id: 种子di
        :param all_use_time: 整个修复所花费的时间
        :param all_llm_count: 总计调用llm的次数
        :param syntax_use_time: 语法修复所用时间
        :param syntax_error_count: 语法错误出现的次数
        :param syntax_format_error_time: 语法修复过程中LLM格式输出错误的次数
        :param syntax_llm_use_time: 语法修复中LLM所用的时间
        :param syntax_llm_count: 语法修复中LLM调用次数
        :param syntax_up_token: 语法修复中上传总token
        :param syntax_down_token: 语法修复中补全总token
        :param sematic_use_time: 语义修复所用时间
        :param semantic_mask_error_count: 语义掩码错误出现的次数
        :param semantic_random_error_count: 语义随机错误出现的次数
        :param semantic_error_count: 语义错误次数
        :param semantic_error_llm_use_time: 修复语义错误LLM所用时间
        :param semantic_error_llm_count: 修复语义错误LLM的调用次数
        :param semantic_llm_format_error: 修复语义错误时LLM格式错误次数
        :param semantic_up_token: 语义修复上传总token
        :param semantic_down_token: 语义修复补全总token
        :return:
        """
        with open(self.mutator_fixer_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([real_time, real_time-self.start_time, seed_id, mutator_id, need_mutate_count, all_use_time,  all_llm_count, syntax_use_time,syntax_error_count, syntax_format_error_time,syntax_llm_use_time,syntax_llm_count,syntax_up_token, syntax_down_token,sematic_use_time, semantic_mask_error_count, semantic_random_error_count, semantic_error_count, semantic_error_llm_use_time,semantic_error_llm_count,semantic_llm_format_error,semantic_up_token, semantic_down_token,left_fix_queue_count])

    def write_structural_mutator_csv(self, real_time, seed_id, new_seed_id,
                                     all_use_time, llm_up_token, llm_down_token, llm_count,
                                     llm_format_error_count, llm_use_time,left_structural_mutate_queue_count):
        """
        向structural_mutator写入一行
        :param real_time: 数据插入时间
        :param seed_id: 种子的id
        :param new_seed_id: 结构化变异后的种子id
        :param all_use_time: 结构化变异的总时间
        :param llm_up_token: 上传总token
        :param llm_down_token: 补全总token
        :param llm_count: LLM调用次数
        :param llm_format_error_count: LLM生成格式错误
        :param llm_use_time: LLM调用所用时间
        :param left_structural_mutate_queue_count: 等待结构化变异的队列剩余个数
        :return:
        """
        with open(self.structural_mutator_csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([real_time, real_time-self.start_time, seed_id,
                             new_seed_id, all_use_time, llm_up_token, llm_down_token,
                             llm_count, llm_format_error_count, llm_use_time,
                             left_structural_mutate_queue_count])



    def add_one_seed_to_parse_list(self, seed_buf, mutate_time):
        """
        添加一个种子到待解析列表中
        :param mutate_time: 要变异的次数
        :param seed_buf: 要加入的种子的buf
        :return: 无返回值
        """

        #先将一个种子加入到总列表中，顺便看看是否重复
        is_already_in_list, seed_id = self.all_seed_list.add_seed_to_list(seed_buf)
        self.main_logger.info(f"已将该种子加入到总队列中，该种子的是否为新种子：{is_already_in_list}，该种子编号为：{seed_id}")
        self.all_seed_list.add_one_seed_chose_time_by_index(seed_id) #添加一次被选择次数
        self.main_logger.info(
            f"种子编号：{seed_id} 被选择次数：{self.all_seed_list.seed_list[seed_id].chose_time}")

        if self.all_seed_list.seed_list[seed_id].chose_time % 10 == 0:
            self.main_logger.info(f"种子编号：{seed_id} 达到结构化变异标准，进行结构化变异")
            #说明进行一次结构性变异
            self.structural_mutator_list.put({"seed_id":seed_id , "mutate_time":mutate_time})
            self.main_logger.info(f"种子编号：{seed_id} 已放入结构化变异队列等待变异，变异次数为{mutate_time}")
            return 0

        self.main_logger.info(f"种子编号：{seed_id} 准备进入解析队列")
        #然后直接加入到待parse中
        self.wait_parse_list.put({"seed_id":seed_id , "mutate_time":mutate_time})
        self.main_logger.info(f"种子编号：{seed_id} 已进入解析队列，变异次数为：{mutate_time}")
        return 0

    def mutate_once(self):
        """
        在fuzz中调用这个函数，用于返回一个待执行的变异器。
        优先从待执行队列中获取；若队列为空，则从变异器池中随机选择一个。
        :return: 变异器对象或队列中的任务；若两者都不可用则返回None
        是否为随机选择的
        """
        mutator: ChiloMutator.ChiloMutator | None = None
        # 首先尝试从待执行的队列中非阻塞地取出一个
        is_first_time = True
        while True:
            if is_first_time:
                self.main_logger.info("准备执行一次待变异任务队列中的变异任务")
                is_first_time = False
            try:
                mutator = self.wait_exec_mutator_list.get_nowait()
                self.main_logger.info("从任务列表中获取任务成功！")
                is_by_random = False
            except queue.Empty:
                # 队列为空，改为从变异器池中随机选择一个
                self.main_logger.info("从任务列表为空，准备从变异池随机选择")
                mutator = self.mutator_pool.random_select_mutator()
                self.main_logger.info("变异池随机选择成功！")
                is_by_random = True
            if mutator is not None:
                break
            self.main_logger.warning("变异池与任务列表均为空！进入等待！！")
            mutator = self.wait_exec_mutator_list.get()
            break
        assert mutator is not None
        self.main_logger.info(f"变异器任务加载完毕，变异的目标种子id:{mutator.seed_id}，变异器编号为：{mutator.mutator_id}")
        #下一步就要根据mutator去加载模块，并调用启动了
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
                raise AttributeError(f"错误码：1203 {filepath} 中未找到 mutate() 函数")

        self.main_logger.info(
            f"正在等待调用 变异的目标种子id:{mutator.seed_id}，变异器编号为：{mutator.mutator_id}")
        mutate_testcase = call_mutate_from_file(mutator.file_name)
        self.all_seed_list.seed_list[mutator.seed_id].mutate_time += 1
        self.main_logger.info(
            f"调用变异完成，为该种子的第{self.all_seed_list.seed_list[mutator.seed_id].mutate_time}次变异 变异的目标种子id:{mutator.seed_id}，变异器编号为：{mutator.mutator_id}")
        return mutate_testcase.encode("utf-8"), is_by_random, mutator.seed_id, mutator.mutator_id




