#!/bin/bash

mkdir -p ssl

openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes -subj "/C=RU/ST=Moscow/L=Moscow/O=Wazir/OU=IT/CN=localhost"

echo "SSL сертификаты созданы в папке ssl/"
echo "ВНИМАНИЕ: Это самоподписанные сертификаты только для разработки!"
echo "Для продакшена используйте Let's Encrypt или другие CA"
