#!/bin/bash

cd app
docker stop hoarder
docker rm hoarder
docker build -t hoarder .
docker run -d --name hoarder -p 5000:5000 -p 5001:5001 hoarder

cd ../nginx
docker stop nginx_hoarder
docker rm nginx_hoarder
docker build -t nginx_hoarder .
docker run -d --name nginx_hoarder -p 80:80 --link hoarder:hoarder nginx_hoarder
