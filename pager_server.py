from __future__ import print_function
import atexit
import logging
import shlex
import socket
import threading
# import dummy_threading as threading
import time


class PagerController(object):
    def __init__(self, ip_addr, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(60.)
        self.watchdog_timeout = 600
        self.sock.bind((ip_addr, port))
        self.threads = []

    def run(self):
        self.sock.listen(1)
        exit = False
        self.watchdog_last = time.time()
        while not exit:
            try:
                conn, addr = self.sock.accept()
                logging.debug('Connection from {}:{}'.format(*addr))
                cmd = conn.recv(4096)
                logging.debug("Received '{}'".format(cmd))
                if cmd == 'exit':
                    logging.debug('Received exit')
                    exit = True
                else:
                    self.threads.append(threading.Thread(target = self.run_cmd,
                                                         args = (conn, cmd)))
                    self.threads[-1].start()
            except socket.timeout:
                pass
            if time.time() - self.watchdog_last > self.watchdog_timeout:
                self.page('Watchdog timed out')
            logging.debug('time since last watchdog: {:.00f}'.format(time.time() - self.watchdog_last))
        self.exit()

    def exit(self):
        logging.debug('Exiting')
        self.sock.close()

    def watchdog(self):
        logging.debug('Updating watchdog timer')
        self.watchdog_last = time.time()
        return 'SUCCESS'
    
    @staticmethod
    def page(msg):
        time.sleep(10)
        logging.debug('Paging on: {}'.format(msg))
        return 'SUCCESS'

    @staticmethod
    def log(msg):
        logging.debug('Logging: {}'.format(msg))
        return 'SUCCESS'

    def run_cmd(self, *args):
        conn, cmd = args
        cmd = shlex.split(cmd)
        try:
            good_cmd = getattr(self, cmd[0])(*cmd[1:])
            if good_cmd:
                logging.debug('Responding with {}'.format(good_cmd))
                conn.send(good_cmd)
            else:
                conn.send('FAIL')
        except Exception as err:
            logging.error("Command '{}' raised error\n'{:s}'".format(' '.join(cmd),
                                                                     repr(err)))
        finally:
            conn.close()

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    pc = PagerController('localhost', 1027)
    atexit.register(pc.exit)
    pc.run()
