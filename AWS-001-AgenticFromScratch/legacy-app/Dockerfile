FROM node:22-alpine
WORKDIR /app
COPY package.json ./
COPY src ./src
ENV PORT=8081
EXPOSE 8081
USER node
CMD ["node", "src/server.js"]
