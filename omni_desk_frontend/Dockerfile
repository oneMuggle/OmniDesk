# Development stage
FROM node:20-alpine AS development
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["npm", "start"]

# Production stage
# Builder part
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Final image part
FROM nginx:stable-alpine
# Increase header buffer to handle large JWT tokens (14KB+ with permissions)
RUN sed -i '/http {/a\    large_client_header_buffers 4 32k;' /etc/nginx/nginx.conf
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Run nginx as non-root — create cache dirs and set permissions before switching user
RUN mkdir -p /var/cache/nginx/client_temp /var/cache/nginx/proxy_temp /var/cache/nginx/fastcgi_temp /var/cache/nginx/uwsgi_temp /var/cache/nginx/scgi_temp && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html
# Ensure PID dir is writable by nginx user
RUN mkdir -p /run && chown nginx:nginx /run
USER nginx
EXPOSE 80
