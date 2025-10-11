def init(seed):
    """
    fuzz的初始化函数，用于初始化整个变异器的状态等等。注意该函数在整个Fuzz过程中只运行一次。
    在这里将会读取配置文件，确定被测对象等等...
    :param seed: 由AFL++传来的一个随机种子，这里其实可以忽略seed的存在
    :return: 返回0，表示初始化成功
    """
    return 0

# def fuzz_count(buf):
#     """
#     能量调度函数，当AFL_CUSTOM_MUTATOR_ONLY=1时，该API不启用，因此可以不写了
#     :param buf:
#     :return:
#     """
#     return cnt

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
    :param add_buf: 被选中拼接的另一个SEED的内容，在此处被忽略了，应为定义了splice_optout函数
    :param max_size: 输出 buffer 最大允许长度，你必须确保返回的变异输入不超过这个长度
    :return: 变异后的结果
    """
    return mutated_out

def describe(max_description_length):
    """
    为变异生成一个描述，可选的部分，不启用也ok
    :param max_description_length:
    :return:
    """
    return "description_of_current_mutation"

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

#当AFL++停止或结束的时候调用该函数，进行清理
def deinit():  # optional for Python
    pass