FROM ubuntu:22.04
LABEL maintainer="ZRCL"

ENV DEBIAN_FRONTEND noninteractive

# common config
RUN apt-get update && apt-get -y install \
    make cmake build-essential sudo git \
    tcl8.6 tcl8.6-tdbc-sqlite3 \
    clang-15 llvm-15 lld ninja-build pkg-config \
    libpq-dev libyaml-cpp-dev wget bzip2 ca-certificates\
    && apt-get clean && rm -rf /var/lib/apt/lists/*



RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

# 设置 conda 环境变量
ENV PATH=/opt/conda/bin:$PATH

RUN mkdir -p /home && \
    groupadd chilo && \
    useradd -l -K UMASK=0000 -d /home -g chilo chilo && \
    chown chilo:chilo /home

RUN	echo "chilo:chilo" | chpasswd && usermod -a -G sudo chilo
RUN chmod +w /etc/sudoers && \
    echo "%chilo   ALL=(ALL:ALL)NOPASSWD:ALL" >> /etc/sudoers && \
    chmod -w /etc/sudoers

USER chilo
WORKDIR /home

# 搞定python环境
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
RUN cd ./ChiloDBFuzz/code/ && conda env create -f ./environment.yaml && conda clean -afy
# 设置默认环境
ENV CONDA_DEFAULT_ENV=ChiloDBFuzz
ENV PATH=/opt/conda/envs/ChiloDBFuzz/bin:$PATH
SHELL ["bash", "-c"]
RUN echo "conda activate ChiloDBFuzz" >> ~/.bashrc

#搞定AFL++
RUN git clone https://github.com/zrclzrcl/ChiloDBFuzz.git && \
    cd ChiloDBFuzz && git submodule update --init && \
    cd AFLplusplus && LLVM_CONFIG=llvm-config-15 make -j$(nproc)

# 构建sqlite
ARG CFLAGS="-DSQLITE_MAX_LENGTH=128000000 -DSQLITE_MAX_SQL_LENGTH=128000000 -DSQLITE_MAX_MEMORY=25000000 -DSQLITE_PRINTF_PRECISION_LIMIT=1048576 -DSQLITE_DEBUG=1 -DSQLITE_MAX_PAGE_COUNT=16384"
RUN git clone https://github.com/sqlite/sqlite sqlite3/ && cd sqlite3 && git checkout version-3.30.0 && mkdir bld
WORKDIR /home/sqlite3/bld
ENV CC=/home/ChilloDBFuzz/AFLplusplus/afl-cc
ENV CXX=/home/ChilloDBFuzz/AFLplusplus/afl-c++
ENV AFL_USE_ASAN=1
RUN ../configure && make -j && make sqlite3.c

RUN $CC $CFLAGS -I. -c \
    /home/sqlite3/test/ossfuzz.c -o /home/sqlite3/test/ossfuzz.o
RUN $CC $CFLAGS -I. -c \
    /home/sqlite3/test/ossshell.c -o /home/sqlite3/test/ossshell.o

RUN $CXX $CXXFLAGS \
    /home/sqlite3/test/ossfuzz.o /home/sqlite3/test/ossshell.o -o /home/ossfuzz \
   ./sqlite3.o -ldl -pthread

WORKDIR /home/ChilloDBFuzz/code