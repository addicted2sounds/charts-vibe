#!/bin/bash

aws cloudformation delete-stack --stack-name music-chart --endpoint-url=http://localhost:4566 --profile localstack
