FROM node:20-slim

WORKDIR /app
COPY package.json .
RUN npm install

COPY marginfi_reader.js .

EXPOSE 8002

CMD ["node", "marginfi_reader.js"]
