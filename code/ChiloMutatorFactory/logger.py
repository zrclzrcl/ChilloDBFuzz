import logging

def setup_thread_logger(thread_name, file_path):
    """
    为每个线程创建独立日志文件
    :param file_path: 文件保存地址
    :param thread_name: 线程名或标识
    """
    logger = logging.getLogger(thread_name)
    logger.setLevel(logging.INFO)

    # 防止重复添加 handler（尤其是线程重复启动）
    if logger.hasHandlers():
        return logger

    # 每个线程一个独立日志文件
    file_handler = logging.FileHandler(file_path, mode='a', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    return logger