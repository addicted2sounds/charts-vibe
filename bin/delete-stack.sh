#!/bin/bash

aws cloudformation delete-stack --stack-name charts-vibe --endpoint-url=http://localhost:4566 --profile localstack
