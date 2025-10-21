FROM ubuntu:22.04
LABEL maintainer="ZRCL"

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get -y install \
    make cmake build-essential sudo git \
    tcl8.6 tcl8.6-tdbc-sqlite3 \
    clang-15 llvm-15 lld ninja-build pkg-config \
    libpq-dev libyaml-cpp-dev wget bzip2 ca-certificates \
    python3 python3-pip python3-dev vim curl gnupg\
    && python3 -m pip install --upgrade pip \
    && python3 -m pip install --no-cache-dir \
        Flask==3.0.3 \
        gunicorn==22.0.0 \
        annotated-types==0.7.0 \
        anyio==4.11.0 \
        certifi==2025.10.5 \
        colorama==0.4.6 \
        distro==1.9.0 \
        h11==0.16.0 \
        httpcore==1.0.9 \
        httpx==0.28.1 \
        idna==3.11 \
        jiter==0.11.0 \
        openai==2.3.0 \
        pydantic==2.12.1 \
        pydantic-core==2.41.3 \
        pyyaml==6.0.3 \
        sniffio==1.3.1 \
        tqdm==4.67.1 \
        typing-extensions==4.15.0 \
        typing-inspection==0.4.2 \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

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

RUN git clone https://github.com/zrclzrcl/ChiloDBFuzz.git

#搞定AFL++
RUN cd /home/ChiloDBFuzz && git submodule update --init && \
    cd AFLplusplus && LLVM_CONFIG=llvm-config-15 make -j$(nproc)

# 构建sqlite
ARG CFLAGS="-DSQLITE_MAX_LENGTH=128000000 -DSQLITE_MAX_SQL_LENGTH=128000000 -DSQLITE_MAX_MEMORY=25000000 -DSQLITE_PRINTF_PRECISION_LIMIT=1048576 -DSQLITE_DEBUG=1 -DSQLITE_MAX_PAGE_COUNT=16384"

RUN git clone https://github.com/sqlite/sqlite sqlite3/ && cd sqlite3 && git checkout version-3.30.0 && mkdir bld
WORKDIR /home/sqlite3/bld
ENV CC=/home/ChiloDBFuzz/AFLplusplus/afl-cc
ENV CXX=/home/ChiloDBFuzz/AFLplusplus/afl-c++
# ENV AFL_USE_ASAN=1
RUN ../configure && make -j && make sqlite3.c

RUN $CC $CFLAGS -I. -c \
    /home/sqlite3/test/ossfuzz.c -o /home/sqlite3/test/ossfuzz.o
RUN $CC $CFLAGS -I. -c \
    /home/sqlite3/test/ossshell.c -o /home/sqlite3/test/ossshell.o

RUN $CXX $CXXFLAGS \
    /home/sqlite3/test/ossfuzz.o /home/sqlite3/test/ossshell.o -o /home/ossfuzz \
   ./sqlite3.o -ldl -pthread

#搞定disco
WORKDIR /home/ChiloDBFuzz/ChiloDisco/frontend
RUN npm ci && npm run build

WORKDIR /home/ChiloDBFuzz/code