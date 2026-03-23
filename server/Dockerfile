FROM node:20-alpine

WORKDIR /app

# Install deps first (layer caching)
COPY package*.json ./
RUN npm ci --production

# Copy source
COPY index.js .
COPY scenario_controller.js .

EXPOSE 8080

CMD ["node", "index.js"]
