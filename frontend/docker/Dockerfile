FROM node:22

ARG USER_NAME=sakaya
ARG UID=1004
ENV UID=${UID}

RUN apt-get update && \
    apt-get install -y curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg \
      | gpg --dearmor > /etc/apt/keyrings/yarn-archive-keyring.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/yarn-archive-keyring.gpg] \
      https://dl.yarnpkg.com/debian/ stable main" \
      > /etc/apt/sources.list.d/yarn.list && \
    apt-get update && \
    apt-get install -y yarn && \
    yarn global add concurrently

RUN useradd -m -u ${UID} -s /bin/bash ${USER_NAME} && \
    mkdir -p /transcriber && \
    chown -R ${USER_NAME}:${USER_NAME} /transcriber

WORKDIR /transcriber/frontend
RUN mkdir -p /transcriber/frontend/node_modules && \
    chown ${USER_NAME}:${USER_NAME} /transcriber/frontend/node_modules

VOLUME ["/transcriber/frontend/node_modules"]

# 依存関係インストール用ファイルを先にコピー
COPY package.json ./

# 依存関係のインストール
RUN yarn install --frozen-lockfile

# ソースコードをコピー
COPY . .

USER ${USER_NAME}
CMD ["sh", "-c", "yarn install && yarn start --host"]