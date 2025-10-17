import hashlib
from typing import List


class AFLSeed:
    def __init__(self, seed_id, seed_buf):
        """
        初始化函数，用于初始化一个种子类
        :param seed_id: 种子的id
        :param seed_buf: 种子的二进制内容
        """
        self.seed_id = seed_id  # 种子的id
        self.seed_buf = seed_buf  # 原始二进制内容
        self.seed_sql = seed_buf.decode('utf-8', errors='ignore')  # 种子的sql
        self.seed_sha = hashlib.sha1(seed_buf).hexdigest()  # 哈希结果，作为指纹
        self.chose_time = 0     # 该种子被选中的次数  （调用fuzz_count）
        self.mutate_time = 0    # 该种子被变异的次数（调用fuzz）
        self.is_parsed = False      # 表明该种子是否已经被解析了
        self.parser_content = None  # 该种子的解析结果
        self.next_mutator_id = 0


class AFLSeedList:
    def __init__(self):
        self.seed_list: List[AFLSeed] = []
        self.seed_sha_map = {}   # 用于快速查找：sha1 -> index
        self.next_seed_id = 0    # 下一个种子id，下一个id-1就是当前最大的id

    def add_seed_to_list(self, seed_buf):
        """
        添加一个种子到列表中，
        :param seed_buf: 想要添加的新种子的buf
        :return: 添加的这个种子的下标，以及是否为新种子
        """
        tmp_seed_sha = hashlib.sha1(seed_buf).hexdigest()
        seed_index = self.seed_sha_map.get(tmp_seed_sha, -1)

        if seed_index == -1:
            # 说明是一个新的种子，需要重新添加
            new_seed = AFLSeed(self.next_seed_id, seed_buf)
            self.seed_sha_map[new_seed.seed_sha] = len(self.seed_list)
            self.seed_list.append(new_seed)
            self.next_seed_id += 1
            return False, new_seed.seed_id
        else:
            # 说明是个已经存在的种子，直接返回下标即可
            return True, seed_index

    def index_of_seed_buf(self, seed_buf):
        """
        在种子列表中找指定种子的下标
        :param seed_buf: 指定种子的二进制buf内容
        :return: 元素下标，下标为-1时表示没找到
        """
        tmp_seed_sha = hashlib.sha1(seed_buf).hexdigest()
        return self.seed_sha_map.get(tmp_seed_sha, -1)

    def add_one_seed_chose_time(self, seed_buf):
        """
        通过给定的种子buf内容，增加该种子的一次被选择次数
        :param seed_buf: 给定的种子内容
        :return: 无返回值
        :exception: 错误码1201 给定的种子不存在于总列表中
        """
        seed_index = self.index_of_seed_buf(seed_buf)
        if seed_index != -1:
            # 说明在列表里，可以添加一次被选中的次数
            self.seed_list[seed_index].chose_time += 1
        else:
            raise Exception("错误码：1201   执行中出现了未在列表中的种子被选择作为当前变异的种子！")

    def add_one_seed_chose_time_by_index(self, seed_index):
        """
        根据给定的种子在总列表中的index来增加一次被选择次数
        :param seed_index: 给定的种子index
        :return: 无返回值
        :exception 错误1201，给定的index错误
        """
        if self.next_seed_id > seed_index >= 0:
            self.seed_list[seed_index].chose_time += 1
        else:
            raise Exception("错误码：1201   执行中出现了未在列表中的种子被选择作为当前变异的种子！(给定index错误)")

    def add_one_seed_mutate_time(self, seed_buf):
        """
        根据种子buf添加一个种子的变异次数
        :param seed_buf: 给定的种子内容
        :return: 无返回值
        :exception 1202 执行中出现了未在列表中的种子被变异
        """
        seed_index = self.index_of_seed_buf(seed_buf)
        if seed_index != -1:
            self.seed_list[seed_index].mutate_time += 1
        else:
            raise Exception("错误码：1202   执行中出现了未在列表中的种子被选择进行变异！")

    def add_one_seed_mutate_time_by_index(self, seed_index):
        """
        根据给定的种子在总列表中的index来增加一次被变异次数
        :param seed_index: 给定的种子index
        :return: 无返回值
        :exception 错误1202，给定的index错误
        """
        if self.next_seed_id > seed_index >= 0:
            self.seed_list[seed_index].mutate_time += 1
        else:
            raise Exception("错误码：1202   执行中出现了未在列表中的种子被选择进行变异！(给定index错误)")
