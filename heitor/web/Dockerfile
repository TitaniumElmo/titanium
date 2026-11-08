# Interface do Elmo: o Vite monta o site estático; o nginx serve.
# As variáveis VITE_* entram NA MONTAGEM (o Railway passa as variáveis do serviço como build args).
FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_API_URL
ARG VITE_EMPRESA
ARG VITE_URL_PLANILHA
ARG VITE_CONTA_SERVICO
RUN npm run build

FROM nginx:1.27-alpine
# O Railway diz a porta em $PORT; o nginx lê o modelo e troca ${PORT} ao subir.
ENV PORT=8080
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /web/dist /usr/share/nginx/html
