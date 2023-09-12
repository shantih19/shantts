FROM alpine
RUN apk add python3
COPY /bot.pex /root/bot.pex
ENTRYPOINT [ "python3", "/root/bot.pex" ]