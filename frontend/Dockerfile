FROM node:22-alpine

WORKDIR /app
COPY package*.json .npmrc ./
RUN npm install
COPY . .
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

EXPOSE 3000
ENV PORT=3000
CMD ["node", "build"]
