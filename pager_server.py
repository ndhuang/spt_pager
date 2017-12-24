from __future__ import print_function
import atexit
import logging
import shlex
import socket
import subprocess
import threading
# import dummy_threading as threading
import time

import config


class PagerController(object):
    def __init__(self, ip_addr = config.server_host, port = config.server_port,
                 timeout = config.server_timeout, 
                 pager_interval = config.pager_interval, 
                 enable = True):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.watchdog_timeout = 600
        self.sock.bind((ip_addr, port))
        self.threads = []
        self.pager_interval = pager_interval
        self.last_page = 0
        self.enabled = enable

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
                    self.threads[-1].name = cmd
                    self.threads[-1].start()
            except socket.timeout:
                pass
            if time.time() - self.watchdog_last > self.watchdog_timeout:
                self.page('Watchdog timed out')
            logging.debug('time since last watchdog: {:.00f}'.format(
              time.time() - self.watchdog_last))
            self._cleanup_threads()
        
        self.exit()

    def _cleanup_threads(self):
        i = 0
        while i < len(self.threads):
            t = self.threads[i]
            if not t.is_alive():
                self.threads.pop(i)
            else:
                i += 1

    def exit(self):
        logging.debug('Exiting')
        self.sock.close()

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def status(self):
        self._cleanup_threads()
        ret = 'Running commands:\n\t'
        ret += '\n\t'.join([t.name for t in self.threads])
        ret += '\nPager is '
        if self.enabled:
            ret += 'enabled'
            time_since_last = time.time() - self.last_page
            if time_since_last <= self.pager_interval:
                ret += ', but pager will not trigger for another {:.0f} seconds'.format(self.pager_interval - time_since_last)
        else:
            ret += 'disabled'
        return ret

    def watchdog(self):
        logging.debug('Updating watchdog timer')
        self.watchdog_last = time.time()
        return 'SUCCESS'
    
    def page(self, msg = ''):
        time_since_last = time.time() - self.last_page
        if self.enabled and time_since_last >= self.pager_interval:
            subprocess.check_call('espeak "{}"'.format(msg), shell = True)
            logging.debug('Paging on: {}'.format(msg))
            self.last_page = time.time()
            return 'SUCCESS'
        else:
            ret = 'Not paging: {:.0f} seconds since last page, waiting for {:.0f} seconds.'.format(time_since_last, self.pager_interval - time_since_last)
            logging.debug(ret)
            return ret

    @staticmethod
    def log(msg = ''):
        logging.debug('Logging: {}'.format(msg))
        return 'SUCCESS'

    def run_cmd(self, *args):
        conn, cmd = args
        cmd = shlex.split(cmd)
        try:
            good_cmd = getattr(self, cmd[0].lower())(*cmd[1:])
            if good_cmd:
                logging.debug('Responding with {}'.format(good_cmd))
                conn.send(good_cmd)
            else:
                conn.send(config.failure_msg)
        except Exception as err:
            logging.error("Command '{}' raised error\n'{:s}'".format(
              ' '.join(cmd), repr(err)))
        finally:
            conn.close()

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    pc = PagerController()
    atexit.register(pc.exit)
    pc.run()
