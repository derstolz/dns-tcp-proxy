#!/bin/bash
pip3 install -r requirements.txt &&
rm -rf /usr/bin/dns-tcp-proxy 2>/dev/null &&
link dns-tcp-proxy.py /usr/bin/dns-tcp-proxy &&
echo "OK"
