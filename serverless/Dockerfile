FROM node:20-slim

RUN apt-get update -y && apt-get install -y openssl python3 make g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY prisma ./prisma
RUN npx prisma generate

COPY . .
RUN npm run build

EXPOSE 3001
CMD ["sh", "-c", "export DATABASE_URL=\"$(echo \"$DATABASE_URL\" | sed 's/#/%23/g')\" && npm start"]
