FROM ghcr.io/cirruslabs/flutter:3.44.8 AS build
ARG TARGET=lib/main_admin.dart
WORKDIR /src
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get
COPY . .
RUN flutter build web --release -t "$TARGET"

FROM nginx:1.27.5-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/build/web /usr/share/nginx/html
EXPOSE 8080
