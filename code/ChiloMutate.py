import time

from ChiloMutatorFactory import chilo_factory as cf
import threading
from ChiloMutatorFactory import LLMParser,LLMMutatorGenerater,LLMStructuralMutator,mutator_fixer


chilo_factory: cf.ChiloFactory | None = None
fuzz_count_number = 0
fuzz_number = 0

def init(seed):
    """
    fuzz的初始化函数，用于初始化整个变异器的状态等等。注意该函数在整个Fuzz过程中只运行一次。
    在这里将会读取配置文件，确定被测对象等等...
    :param seed: 由AFL++传来的一个随机种子，这里其实可以忽略seed的存在
    :return: 返回0，表示初始化成功
    """

    global chilo_factory
    chilo_factory = cf.ChiloFactory()   #首先初始化整个工厂（读配置文件）
    chilo_factory.main_logger.info("Chilo工厂初始化成功！")
    
    # 计算总线程数
    total_threads = (chilo_factory.parser_thread_count + 
                    chilo_factory.mutator_generator_thread_count + 
                    chilo_factory.structural_mutator_thread_count + 
                    chilo_factory.fixer_thread_count)
    chilo_factory.main_logger.info(f"Chilo工厂准备启动{total_threads}个子线程")
    
    # 启动多个Parser线程
    chilo_factory.main_logger.info(f"Chilo工厂启动解析器中~（共{chilo_factory.parser_thread_count}个线程）")
    parser_threads = []
    for i in range(chilo_factory.parser_thread_count):
        parser_t = threading.Thread(target=LLMParser.chilo_parser, args=(chilo_factory,))
        parser_t.start()
        parser_threads.append(parser_t)
        chilo_factory.main_logger.info(f"解析器[线程{i}]启动成功")
    
    # 启动多个Mutator Generator线程
    chilo_factory.main_logger.info(f"Chilo工厂启动变异器生成器中~（共{chilo_factory.mutator_generator_thread_count}个线程）")
    generator_threads = []
    for i in range(chilo_factory.mutator_generator_thread_count):
        generator_t = threading.Thread(target=LLMMutatorGenerater.chilo_mutator_generator, args=(chilo_factory,))
        generator_t.start()
        generator_threads.append(generator_t)
        chilo_factory.main_logger.info(f"变异器生成器[线程{i}]启动成功")
    
    # 启动多个Structural Mutator线程
    chilo_factory.main_logger.info(f"Chilo工厂启动结构化变异器中~（共{chilo_factory.structural_mutator_thread_count}个线程）")
    structural_threads = []
    for i in range(chilo_factory.structural_mutator_thread_count):
        structural_t = threading.Thread(target=LLMStructuralMutator.structural_mutator, args=(chilo_factory,))
        structural_t.start()
        structural_threads.append(structural_t)
        chilo_factory.main_logger.info(f"结构化变异器[线程{i}]启动成功")
    
    # 启动多个Fixer线程
    chilo_factory.main_logger.info(f"Chilo工厂启动变异器修复器中~（共{chilo_factory.fixer_thread_count}个线程）")
    fixer_threads = []
    for i in range(chilo_factory.fixer_thread_count):
        fixer_t = threading.Thread(target=mutator_fixer.fix_mutator, args=(chilo_factory, i))
        fixer_t.start()
        fixer_threads.append(fixer_t)
        chilo_factory.main_logger.info(f"变异器修复器[线程{i}]启动成功")
    
    chilo_factory.main_logger.info("初始化完成，结束初始化~")


    return 0

def fuzz_count(buf):
    """
    能量调度函数，决定一个种子调用多少次的fuzz()
    注意，在这里调度的时候，还实现了完成对当前种子的TOKEN解析和变异器生成~yooo~~
    :param buf: 当前种子
    :return: 变异次数
    """
    global fuzz_count_number
    fuzz_count_number += 1
    mutate_time = 64
    #应该采用队列的设计，先放入工厂的队列中，等待加工
    global chilo_factory
    chilo_factory.main_logger.info("进入fuzz_count~")
    chilo_factory.main_logger.info("准备将buf中种子加入到待解析队列中~")
    chilo_factory.add_one_seed_to_parse_list(buf, mutate_time)
    chilo_factory.main_logger.info("该种子fuzz_count处理完成")
    return mutate_time   #为快速迭代，目前写死为64

def splice_optout():
    """
    标记函数，当定义了这个函数的时候，则AFL++在非确定性变异阶段不启用随机拼接
    :return: 无返回值
    """
    pass

def fuzz(buf, add_buf, max_size):
    """
    主要的变异API，AFL++在每轮变异中将调用一次这个函数
    在这个函数中，应该完成对于一个种子的变异，并返回变异后的结果
    :param buf: 当前队列中的SEED的内容
    :param add_buf: 被选中拼接的另一个SEED的内容，在此处被忽略了，因为定义了splice_optout函数
    :param max_size: 输出 buffer 最大允许长度，你必须确保返回的变异输入不超过这个长度
    :return: 变异后的结果
    """
    fuzz_start_time = time.time()
    global chilo_factory
    global fuzz_number
    global fuzz_count_number
    fuzz_number += 1
    is_cut = False
    #思路：
    #其实整个变异的返回值的获取，就是读文件，将文件内容作为返回值即可
    #这里应该启用一次LLM生成的程序，并将程序生成的SQL测试用例作为返回值，这样可以不用记录次数...
    #但这里还有一个问题
    #那就是两种变异并不是每次都用
    #因此在这一次函数的调用中，如何确定本次是结构+TOKEN 还是仅结构呢....这是一个问题
    #不管了，先把TOKEN的写出来吧

    #下一步呢，其实变异阶段有两部分，分别是掩码解析和掩码变异... 到这里已经完成了解析，直接变异就好

    #这里应该只需要做一件事就行，那就是启动LLM生成的变异程序，并获得一个SQL！
    chilo_factory.main_logger.info("进入fuzz阶段~")
    chilo_factory.main_logger.info("准备调用mutator生成")
    mutated_out,is_random, seed_id, mutator_id, is_error_occur, is_from_structural_mutator = chilo_factory.mutate_once()
    chilo_factory.main_logger.info("变异完成")
    # 确保类型正确
    if isinstance(mutated_out, str):
        mutated_out = bytearray(mutated_out, "utf-8", errors="ignore")
        # 检查并截断

    ori_mutate_out_size = len(mutated_out)

    if len(mutated_out) > max_size:
        is_cut = True
        mutated_out = mutated_out[:max_size]
        chilo_factory.main_logger.warning("由于变异结果过长，被迫进行截断")
    real_mutate_out_size = len(mutated_out)
    now_seed_id = chilo_factory.all_seed_list.index_of_seed_buf(buf)

    fuzz_end_time = time.time()
    chilo_factory.write_main_csv(fuzz_end_time, fuzz_count_number, fuzz_number,
                                 is_random, fuzz_end_time - fuzz_start_time, now_seed_id, seed_id, mutator_id,
                                 chilo_factory.wait_exec_mutator_list.qsize(), ori_mutate_out_size,
                                 real_mutate_out_size, is_cut, is_error_occur, is_from_structural_mutator)
    return mutated_out

#当AFL++停止或结束的时候调用该函数，进行清理
def deinit():  # optional for Python
    chilo_factory.main_logger.info("FUZZ结束！祝您早日找到CVE！！")
    pass
# def describe(max_description_length):
#     """
#     为变异生成一个描述，可选的部分，不启用也ok
#     :param max_description_length:
#     :return:
#     """
#     return "description_of_current_mutation"

# def post_process(buf):
#     """
#     在变异后的测试用例即将发送给被测DBMS前，将调用这个函数
#     这个函数的目的应该是对测试用例进行补充，例如ZIP格式需要加入特殊的头信息等等
#     对于DBMS而言，应该不需要，因此该方法会被注释
#     :param buf:
#     :return:
#     """
#     return out_buf

#下面三个函数都是修剪相关的函数，即得到最小化输入，在DBMS模糊测试中不需要，因此被注释
# def init_trim(buf):
#     return cnt
#
# def trim():
#     return out_buf
#
# def post_trim(success):
#     return next_index


#下面两个函数都是自定义havoc变异及其概率，在启动AFL_CUSTOM_MUTATOR_ONLY=1时，该函数将不起作用，因此被注释
# def havoc_mutation(buf, max_size):
#     return mutated_out
#
# def havoc_mutation_probability():
#     return probability # int in [0, 100]

#下面的函数是种子选择的函数，
# def queue_get(filename):
#     return True

# #下面是用于发送测试用例的函数，在本次设计中采用wrapper设计，不需要该函数
# def fuzz_send(buf):
#     pass

# # 有新的种子加入测试用例后会调用这个函数，可以对种子进行处理，但本方法不需要该函数
# def queue_new_entry(filename_new_queue, filename_orig_queue):
#
#     return False

# #返回一个字符串，用于描述变异方法的，不需要
# def introspection():
#     return string

