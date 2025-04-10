# 构建阶段
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --silent --omit=dev
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --chown=appuser:appgroup . .
ENV NODE_ENV=production
RUN npm run build
RUN npm cache clean --force
RUN chown -R appuser:appgroup /app

# 生产阶段
FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN mkdir -p /var/cache/nginx /var/log/nginx
RUN rm -rf /var/run && mkdir -p /var/run/nginx
RUN chown -R appuser:appgroup \
    /usr/share/nginx/html \
    /var/cache/nginx \
    /var/log/nginx \
    /var/run/nginx
RUN chmod -R 755 /var/run/nginx

USER appuser
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD curl --fail http://127.0.0.1:8080 || exit 1
CMD ["nginx", "-g", "daemon off;"]
