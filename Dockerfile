FROM alpine
RUN apk add python
COPY plz-out/src/bot/bot.pex