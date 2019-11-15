#!/usr/bin/env python3
# if you want to change default DNS server in Windows for all applications,
# you should consider the following command
### netsh interface ip set dns "mydns" static 127.0.0.1 primary

# if you want to do the same in Linux,
# you should edit /etc/resolv.conf file and add your dns proxy address
# and probably this
# https://askubuntu.com/questions/157154/how-do-i-include-lines-in-resolv-conf-that-wont-get-lost-on-reboot#221955

import random
import socket
import socketserver
import struct

import socks

DEFAULT_LOCAL_DNS_SERVER_IP_ADDRESS = '127.0.0.1'
DEFAULT_DNS_SERVER_PORT = 53
DEFAULT_TIMEOUT = 20  # set timeout 5 second

DNS_SERVERS = ['8.8.8.8',
               '8.8.4.4',
               '208.67.222.222',
               '208.67.220.220',
               ]


def get_arguments():
    from argparse import ArgumentParser

    parser = ArgumentParser(description='Use this tool to proxy your DNS requests through a local DNS TCP proxy.')
    parser.add_argument('--ip',
                        dest='ip',
                        default=DEFAULT_LOCAL_DNS_SERVER_IP_ADDRESS,
                        required=False,
                        help='An IP address for the local DNS server to bind to. Default is ' +
                             DEFAULT_LOCAL_DNS_SERVER_IP_ADDRESS)
    parser.add_argument('--port',
                        dest='port',
                        default=DEFAULT_DNS_SERVER_PORT,
                        required=False,
                        help='UDP port of the local DNS server. Default is ' + str(DEFAULT_DNS_SERVER_PORT))
    parser.add_argument('--relay',
                        dest='relay',
                        required=False,
                        help='Use this option if you want to tunnel your DNS requests from your local DNS server '
                             'through an additional SOCKS proxy. '
                             'The option should be given in the following format: "socks5://127.0.0.1:1080".')
    parser.add_argument('--target-dns-ip',
                        dest='dns_ip',
                        default=DNS_SERVERS[random.randint(0, len(DNS_SERVERS) - 1)],
                        required=False,
                        help='Specify a custom DNS server to use after all redirects have been done. Default servers '
                             'is one of the following: ' + "; ".join(DNS_SERVERS))
    parser.add_argument('--target-dns-port',
                        dest='dns_port',
                        default=DEFAULT_DNS_SERVER_PORT,
                        required=False,
                        help='Specify a UDP port for the targeted DNS server. '
                             'Default is ' + str(DEFAULT_DNS_SERVER_PORT))
    return parser.parse_args()


class ThreadedUDPServer(socketserver.ThreadingMixIn,
                        socketserver.UDPServer):
    # Ctrl-C will cleanly kill all spawned threads
    daemon_threads = True
    # much faster rebinding
    allow_reuse_address = True

    def __init__(self, local_dns_address,
                 request_handler):
        socketserver.UDPServer.__init__(self, local_dns_address, request_handler)


class ThreadedUDPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        query_data = self.request[0]
        udp_sock = self.request[1]
        addr = self.client_address

        global target_dns_ip
        global target_dns_port
        response = query_dns_by_tcp(target_dns_ip, target_dns_port, query_data)
        if response:
            # udp dns packet no length
            udp_sock.sendto(response[2:], addr)


def query_dns_by_tcp(dns_ip, dns_port, query_data):
    # make TCP DNS Frame
    tcp_frame = struct.pack('!h', len(query_data)) + query_data

    try:
        global socks_proxy
        if socks_proxy:
            s = socks.socksocket()
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(DEFAULT_TIMEOUT)  # set socket timeout
        s.connect((dns_ip, dns_port))
        s.send(tcp_frame)
        data = s.recv(2048)
    except:
        if s:
            s.close()
        return

    if s:
        s.close()
    return data


if __name__ == "__main__":
    options = get_arguments()
    local_dns_server_ip = options.ip
    local_dns_server_port = int(options.port)

    target_dns_ip = options.dns_ip
    target_dns_port = int(options.dns_port)

    socks_proxy = options.relay
    if socks_proxy:
        socks_type = socks_proxy.split(':')[0]
        socks_ip = socks_proxy.split('//')[1].split(':')[0]
        socks_port = int(socks_proxy.split(':')[2])
        print(
                    'Starting local DNS relay on udp://{dns_ip}:{dns_port} '
                    '--> {socks_type}://{socks_ip}:{socks_port} '
                    '--> tcp://{target_dns_ip}:{target_dns_port}'.format(
                                dns_ip=local_dns_server_ip,
                                dns_port=local_dns_server_port,
                                socks_type=socks_type,
                                socks_ip=socks_ip,
                                socks_port=socks_port,
                                target_dns_ip=target_dns_ip,
                                target_dns_port=target_dns_port))
        if socks_type == 'socks5':
            socks.set_default_proxy(socks.PROXY_TYPE_SOCKS5, socks_ip, socks_port)
        elif socks_type == 'socks4':
            socks.set_default_proxy(socks.PROXY_TYPE_SOCKS4, socks_ip, socks_port)
        elif socks_type == 'http':
            raise Exception("HTTP proxy is not supported")

    try:
        dns_server = ThreadedUDPServer((local_dns_server_ip, local_dns_server_port),
                                       ThreadedUDPRequestHandler)
        if not socks_proxy:
            print(
                        'Starting DNS proxy on udp://{dns_server_ip}:{dns_server_port} '
                        '--> tcp://{target_dns_ip}:{target_dns_port}'.format(
                                    dns_server_ip=local_dns_server_ip,
                                    dns_server_port=local_dns_server_port,
                                    target_dns_ip=target_dns_ip,
                                    target_dns_port=target_dns_port))
        dns_server.serve_forever()
    except ConnectionRefusedError:
        print('Local DNS relay failed to establish a connection. Is the proxy address correct?')
    except PermissionError:
        print('Permission denied. You should check whether you have root/SYSTEM account to bind on the 53/udp port')
    except KeyboardInterrupt:
        print('\n\nInterrupted')
        exit(1)
    except Exception as e:
        print('Unexpected error: {e}'.format(e=e))
        exit(1)
