# 构建阶段
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --chown=appuser:appgroup . .
ENV NODE_ENV=production
RUN DISABLE_ESLINT_PLUGIN=true npm run build
RUN npm cache clean --force

# 生产阶段
FROM nginx:alpine
RUN apk --no-cache add curl
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
RUN addgroup -S appgroup && adduser -S appuser -G appgroup && \
    mkdir -p /var/cache/nginx /var/log/nginx /var/run/nginx && \
    chown -R appuser:appgroup \
        /usr/share/nginx/html \
        /var/cache/nginx \
        /var/log/nginx \
        /var/run/nginx && \
    chmod -R 755 /var/run/nginx

USER appuser
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD curl --fail http://127.0.0.1:80 || exit 1
CMD ["nginx", "-g", "daemon off;"]
