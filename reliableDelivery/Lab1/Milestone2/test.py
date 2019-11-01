import threading
import time
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='(%(threadName)-9s) %(message)s',)


class salam:
    def __init__(self):
        self.t1 = threading.Timer(5, self.f)

    def f(self):
        print('slm')

    def st(self):
        logging.debug('starting timers...')
        self.t1.start()
        time.sleep(3)
        print(self.t1.is_alive())
        time.sleep(3)
        print(self.t1.is_alive())
        # self.t1.cancel()
        # self.t1.join()


if __name__ == '__main__':

    slm = salam()
    slm.st()
