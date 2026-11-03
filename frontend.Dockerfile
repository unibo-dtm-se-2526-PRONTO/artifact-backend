# The Vue frontend on the Vite dev server, built by docker compose.
FROM node:24-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host: listen on every interface.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
