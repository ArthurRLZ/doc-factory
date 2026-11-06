# --- ETAPA 1: Build da aplicação ---
FROM node:20-alpine AS build

WORKDIR /app

# Copia os arquivos de dependências
COPY package*.json ./

# Instala todas as dependências (incluindo as de desenvolvimento)
RUN npm install

# Copia o restante do código-fonte
COPY . .

# Executa o build de produção (gera a pasta /app/dist)
RUN npm run build

# --- ETAPA 2: Servir os arquivos com Nginx ---
FROM nginx:alpine

# Copia os arquivos estáticos gerados no build para a pasta padrão do Nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Copia a configuração personalizada do Nginx para suportar o React Router
COPY nginx.config /etc/nginx/conf.d/default.conf

# Expõe a porta 80 do container
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]