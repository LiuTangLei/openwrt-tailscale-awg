FROM alpine:3.22
RUN apk add --no-cache python3 curl openssl iproute2 iptables kmod util-linux bash dash shellcheck procps
WORKDIR /repo
CMD ["python3", "asus/tests/test_manager.py"]
