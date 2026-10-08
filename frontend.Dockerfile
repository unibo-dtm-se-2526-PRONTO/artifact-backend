# The Vue frontend (../artifact-frontend), served by the Vite dev server. It is
# built from the frontend folder by docker compose: see the frontend service.
FROM node:24-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host: listen on every interface, or the port published by the container
# would not reach the server.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
