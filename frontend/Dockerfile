FROM node:20-slim AS builder

WORKDIR /app
COPY package.json .
RUN npm install

COPY . .
ARG VITE_BACKEND_URL=http://localhost:8000
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA routing — redirect all 404s to index.html
RUN echo 'server { listen 3000; root /usr/share/nginx/html; location / { try_files $uri $uri/ /index.html; } }' \
    > /etc/nginx/conf.d/default.conf

EXPOSE 3000
