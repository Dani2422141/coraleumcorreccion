FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
# npm ci instala exactamente las versiones de package-lock.json (builds reproducibles).
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
