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


##############################################################################
# TODO
# ~~1. Documentation~~
# 2. Clean up properly (still unclear what's going on)
# 3. Start integrating sipcmd
# 4. Add logging to a file, and allow log level control from the command line
##############################################################################

class PagerController(object):
    '''
    Controller for the pager.  Clients connect to this process to issue
    commands to the pager.  This allows for centralized control, which
    prevents annoying behavior e.g. many pages in a short period of time.

    '''
    def __init__(self, ip_addr = config.server_host, port = config.server_port,
                 timeout = config.server_timeout, 
                 pager_interval = config.pager_interval, 
                 watchdog_timeout = config.watchdog_timeout,
                 enable = True):
        '''
        Most arguments are filled with default values from config.py.
        
        INPUTS
        ------
        ip_addr: str
            IP address or hostname of the machine running the server.
        port: int
            Port on which the server listens.
        timeout: float
            The main loop of the server listens for incoming connections
            for `timeout` seconds, before checking the watchdog timer.
            This number is a tradeoff between time resolution on triggering
            the watchdog alert vs. time spent waiting for connections.
            Values from 10-60 seconds should be fine.
        pager_interval: float
            The number of seconds that must pass between paging events.
            Page commands received before this amount of time are dropped,
            instead of queued for later paging.
        watchdog_timeout: float
            Allow this many seconds to elapse without receiving a heartbeat
            signal before triggering the watchdog alert.  This is intended
            for use by the GCP heartbeat signal.
        enable: bool (True)
            If True, the pager will be enabled upon startup.
        '''
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.watchdog_timeout = watchdog_timeout
        self.sock.bind((ip_addr, port))
        self.threads = []
        self.pager_interval = pager_interval
        self.last_page = 0
        self.enabled = enable

    def run(self):
        '''
        The main loop of the server.  Waits for incoming connections, 
        then passes the command to a worker thread.  After each connection
        is made (or the timeout is reached), the watchdog timer is checked.
        '''
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
                cmd = 'Watchdog timed out'
                self.threads.append(threading.Thread(
                                    target = self.page, args = (cmd,)))
                self.threads[-1].name = cmd
                self.threads[-1].start()
            logging.debug('time since last watchdog: {:.00f}'.format(
              time.time() - self.watchdog_last))
            self._cleanup_threads()
        
        self.exit()

    def _cleanup_threads(self):
        '''
        Check for dead threads in our list of threads.
        '''
        i = 0
        while i < len(self.threads):
            t = self.threads[i]
            if not t.is_alive():
                self.threads.pop(i)
            else:
                i += 1

    def exit(self):
        '''
        Ye olde cleanup function.
        '''
        logging.debug('Exiting')
        self.sock.close()

    def enable(self):
        '''
        Enable the pager.  Only affects calling, all other functionality 
        continues to operate normally.
        '''
        self.enabled = True

    def disable(self):
        '''
        Disable the pager.  Only affects calling, all other functionality 
        continues to operate normally.
        '''
        self.enabled = False

    def status(self):
        '''
        Return some information about the pager status.  This is passed back to
        the client that initiated the command.
        '''
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
        '''
        Update the watchdog timer.
        '''
        logging.debug('Updating watchdog timer')
        self.watchdog_last = time.time()
        return 'SUCCESS'
    
    def page(self, msg = ''):
        '''
        Trigger a page.  `msg` is converted to a voice message by espeak,
        and then (in principle) spoken to page recipients.
        '''
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
        '''
        Write `msg` to the log.
        Probably going to be removed in future versions.
        '''
        logging.debug('Logging: {}'.format(msg))
        return 'SUCCESS'

    def run_cmd(self, conn, cmd):
        '''
        Run a command.  This function blindly tries to run the first word
        of `cmd` as an instance method of PagerController.  If the method
        doesn't exist (or any other error occurs), a failure message is 
        returned to the client, and the error is logged.

        INPUTS
        ------
        conn: socket connection
            A connection object, as returned by socket.socket.listen.
        cmd: str
            The command to run.
        '''
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
