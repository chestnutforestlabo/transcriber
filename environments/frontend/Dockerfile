FROM node:22

ARG UID=$(id -u)
ARG USER_NAME=${USER}

RUN useradd -m -u ${UID} -s /bin/bash ${USER_NAME}

WORKDIR /transcriber

COPY src/frontend/package.json src/frontend/yarn.lock ./src/frontend/
RUN cd src/frontend && yarn install --frozen-lockfile

COPY src/frontend ./src/frontend

USER ${USER_NAME}
CMD ["sh", "-c", "cd src/frontend && yarn start --host 0.0.0.0"]