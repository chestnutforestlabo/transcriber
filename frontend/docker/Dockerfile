FROM node:22

ARG USER_NAME=sakaya
ARG UID=1004
ENV UID=${UID}

# yarnのインストール（root権限で実行）
RUN apt-get update && \
    apt-get install -y curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | gpg --dearmor > /etc/apt/keyrings/yarn-archive-keyring.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/yarn-archive-keyring.gpg] https://dl.yarnpkg.com/debian/ stable main" > /etc/apt/sources.list.d/yarn.list && \
    apt-get update && \
    apt-get install -y yarn

# ユーザーの作成とディレクトリの設定
RUN useradd -m -u ${UID} -s /bin/bash ${USER_NAME} && \
    mkdir -p /transcriber && \
    chown -R ${USER_NAME}:${USER_NAME} /transcriber

WORKDIR /transcriber

USER ${USER_NAME}

CMD ["sh", "-c", "cd frontend && yarn install && yarn start --host"]