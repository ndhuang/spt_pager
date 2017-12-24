import argparse
import logging
logging.basicConfig(level = logging.DEBUG)
import socket
import config

cmd_usage = '''Command to execute.  In general, any instance method of PagerController can be executed on the server this way, but the following commands are most likely to be of interest to most users:

page 'message': trigger a page with a given message
enable: enable the pager
disable: disable the pager
log 'message': log a message in the pager log, without triggering a page.

Unfortunately, all whitespace in commands wil be replaced with ascii spaces
'''

def send_cmd(sock, cmd):
    logging.debug('Sending: {}'.format(cmd))
    sock.send(cmd)
    response = sock.recv(4096)
    if response == config.failure_msg:
        logging.error('Command failed, check server log')
    else:
        logging.info(response)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 
                                     'Client for controlling the pager.')
    parser.add_argument('cmd', nargs = '+', type = str, help = cmd_usage)
    parser.add_argument('--server', default = config.server_host,
                        help = 'Address of the server host')
    parser.add_argument('--port', '-p', default = config.server_port, 
                        type = int, help = 'Port the server is listening on')
    parser.add_argument('--timeout', default = config.client_timeout,
                        help = 'Timeout to wait for server connection')
    args = parser.parse_args()
    if len(args.cmd) == 1:
        cmd = args.cmd[0]
    else:
        cmd = '{} "{}"'.format(args.cmd[0], ' '.join(args.cmd[1:]))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(args.timeout)
    sock.connect((args.server, args.port))
    send_cmd(sock, cmd)
    sock.close()
