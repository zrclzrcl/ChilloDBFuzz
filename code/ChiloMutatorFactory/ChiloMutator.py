"""
用于保存生成的变异器的类
其中包括三个类

1. 变异器池
2. 一个变异器
3. 一个任务队列
"""
import random
from typing import List


#先定义变异器

class ChiloMutator:
    def __init__(self, file_path, seed_id, mutator_id, mutator_index):
        """
        初始化一个变异器池，其中具有一些属性
        """
        self.seed_id = seed_id
        self.mutator_id = mutator_id
        self.mutator_index = mutator_index
        self.file_name = f"{file_path}{seed_id}_{mutator_id}.py"
        self.is_error = False   #是否在最终的FUZZ出现了错误
        self.last_error_count = 0   #如果出现了最终FUZZ错误则加1...不过好像没啥用

class ChiloMutatorPool:
    def __init__(self, file_path):
        """
        初始化一个变异器池，用于保存所有变异器
        """
        self.mutator_list:List[ChiloMutator] = []
        self.next_mutator_index = 0
        self.file_path = file_path

    def add_mutator(self, seed_id, mutator_id):
        self.mutator_list.append(ChiloMutator(self.file_path, seed_id, mutator_id, self.next_mutator_index))
        self.next_mutator_index += 1
        return self.next_mutator_index - 1



    def random_select_mutator(self):
        """
        从变异器池中随机选择一个
        :return: 返回的变异器对象
        """
        if self.next_mutator_index == 0:    #说明还没有变异器呢，要稍微等一会
            return None
        else:
            num = random.randint(0, self.next_mutator_index - 1)
            return self.mutator_list[num]

