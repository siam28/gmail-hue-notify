__author__ = 'siam'

import threading, email, re
import imaplib2
import os
import sys
import time
from phue import Bridge

class Idler(object):
    # Method executed upon thread initilization
    def __init__(self, connection, bridge):
        # Print messages:
        debugmsg('Idler: __init__() entered')

        self.thread = threading.Thread(target=self.idle_loop)
        self.M = connection
        self.B = bridge

        # stopWaitingEvent stores a boolean value and has 3 methods: set(), clear(), and wait()
        # wait() will pause execution where it is called until stopWaitingEvent is set
        # The idle callback and kill methods will be calling set()
        self.stopWaitingEvent = threading.Event()

        # Initialize key variables:
        self.killNow = False  # stops execution of thread to allow proper closing of connection
        self.timeout = False  # timeout flag
        self.newMail = False  # new mail flag
        self.error = False
        self.IDLEArgs = ''  # IDLE return arguments

        result, data_unseen = self.M.search(None, 'UnSeen')  # get the unseen email IDs
        self.curr_unseen_id_list = data_unseen[0].split()  # list of currently unseen email IDs (strings) | empty list if none
        self.prev_unseen_id_list = self.curr_unseen_id_list  # list of previously unseen email IDs (strings) | initialized to current list

        debugmsg('Idler: __init__() exited')

    # Method executed when thread is started
    def start(self):
        self.thread.start()

    def join(self):
        self.thread.join()

    # Main idler loop:
    def idle_loop(self):
        debugmsg('Idler: idle_loop() entered')

        # while loop to restart the imapwait() method once it finishes
        while not self.killNow:
            self.stopWaitingEvent.clear()  # clear stopWaitingEvent boolean value (initialize)

            # Callback when the IMAP server responds to idle
            def _idlecallback(args):
                result, arg, exc = args
                if result is None:
                    print("There was an error during IDLE:", str(exc))
                    self.error = True
                    self.stopWaitingEvent.set()  # sets stopWaitingEvent boolean value to continue
                else:
                    self.error = False
                    self.stopWaitingEvent.set()  # sets stopWaitingEvent boolean value to continue

            server_timeout = 20
            self.M.idle(timeout=60*server_timeout, callback=_idlecallback)

            self.stopWaitingEvent.wait()  # now we wait until _idlecallback sets stopWaitingEvent

            # At this point, we've resumed execution and self.IDLEArgs has now been filled.
            # We have had either a timeout or server has notified of some change

            if not self.killNow:  # skips a chunk of code to sys.exit() more quickly.
                if not self.error:
                    result, data_unseen = self.M.search(None, 'UnSeen')
                    self.curr_unseen_id_list = data_unseen[0].split()  # list of unseen email IDs (as strings)
                    n_unseen = len(self.curr_unseen_id_list)  # number of unseen emails

                    if n_unseen > 0:  # if there is 1 or more unseen email(s)...
                        # sorted, integer list of current unseen emails
                        curr_unseen_id_list_sort_int = sorted(map(int, self.curr_unseen_id_list))

                        #  sorted, integer list of previous unseen emails
                        prev_unseen_id_list_sort_int = sorted(map(int, self.prev_unseen_id_list))

                        if curr_unseen_id_list_sort_int == prev_unseen_id_list_sort_int:
                            self.newMail = False
                            self.timeout = True
                            debugmsg('No new e-mails')
                        elif len(curr_unseen_id_list_sort_int) - len(prev_unseen_id_list_sort_int) > 0:
                            # theoretically, this difference should be 1 if there is new email
                            self.newMail = True
                            self.timeout = False
                            debugmsg('New e-mail detected')
                            # id(s) of new-email(s):
                            new_email_ids = [x for x in curr_unseen_id_list_sort_int if
                                             x not in set(prev_unseen_id_list_sort_int)]
                            newest_new_email_id = max(new_email_ids)
                        else:
                            # print "|--> No new e-mail detected!"
                            self.newMail = False
                            self.timeout = True
                        self.prev_unseen_id_list = self.curr_unseen_id_list  # set previous unseen ID list to current for next comparison
                    elif n_unseen == 0:
                        self.newMail = False
                        self.timeout = True
                        self.prev_unseen_id_list = []  # set previous unseen ID list to current for next comparison
                        debugmsg('No new e-mails')
                else:
                    print "There was an error during IDLE. Killing thread..."
                    self.timeout = False
                    self.newMail = False
                    self.killNow = True

                # now there has either been a timeout or a new message -- Do something...
                if self.newMail:
                    new_email_nimee = 0
                    result, data_msgs = self.M.fetch(newest_new_email_id, '(RFC822)')
                    sender = ''
                    sender_address = ''

                    for response_part in data_msgs:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_string(response_part[1])
                            sender = msg['from'].split()[-1]
                            sender_address = re.sub(r'[<>]','',sender)


                    if sender_address in ("special@email.com", "special2@email.com"):
                        new_email_nimee += 1
                        # print "|-> New e-mail from my love: %d" % new_email_nimee

                    # BR Light Parameters:
                    n_trans_br = 1  # number of transitions
                    trains_int_br = 3  # fade time | [=] seconds

                    if new_email_nimee > 0:
                        # print "My love sent me an e-mail. Lights will breathe special color"
                        command_c1_br = {'on': True, 'transitiontime': trains_int_br * 10, 'bri': 80,
                                         'xy': [0.1693, 0.0421]}
                    else:
                        # print "No new e-mail from my love. Regular color will be used."
                        command_c1_br = {'on': True, 'transitiontime': trains_int_br * 10, 'bri': 80,
                                         'xy': [0.6495, 0.3087]}

                    self.one_color_hue_breathe("BR1", command_c1_br, trains_int_br, n_trans_br)
                    self.one_color_hue_breathe("LR5", command_c1_br, trains_int_br, n_trans_br)
                elif self.timeout:
                    print "Timeout or no new e-mail"

        debugmsg('Idler: idle_loop() exited')

    # Method executed when thread is killed
    def kill(self):
        self.killNow = True  # stops the while loop in run()
        self.timeout = True  # keeps imapwait() nice
        self.stopWaitingEvent.set()  # allow wait() method to return and let execution continue

    # Method executed to breathe the lights
    def one_color_hue_breathe(self, light, command_c1, transition_int, n_transitions):
        light_state = self.B.get_light(light)['state']  # retrieve light state
        if light_state.get('on'):
            # print "%s light is on!" % light
            light_state_pre = light_state.copy()  # copy state
            light_state_pre['transitiontime'] = transition_int * 10  # transition time to new color
            light_state_pre.pop("colormode", None)
            light_state_pre.pop("reachable", None)
            for x in range(0, n_transitions):
                # print "|-> Transition: %d of %d. " % (x, n_transitions - 1)
                self.B.set_light(light, command_c1)
                time.sleep(transition_int + 1)
                self.B.set_light(light, light_state_pre)
                time.sleep(transition_int + 1)
#        else:
#            print "%s light is off!" % light


def debugmsg(msg, newline=1):
    global DEBUG
    if DEBUG:
        if newline:
            print ' '
        print msg

DEBUG = True  # debugmsg() prints the parameter passed if DEBUG is True
debugmsg('DEBUG is ENABLED')

while True:
    try:
        M = imaplib2.IMAP4_SSL("imap.gmail.com")  # IMAP connection to gmail
        gmail_address = "me@gmail.com"
        gmail_pw = "gmailpassword"

        print "Logging in as %s and selecting the Inbox..." % gmail_address
        M.login(gmail_address, gmail_pw)  # log in
        M.select("INBOX", readonly=True)  # select the Inbox and open in read-only mode (escapes AUTH state)

        # Hue:
        b = Bridge('192.168.W.XYZ')  # Hue Bridge IP
        b.connect()  # connect to Hue Bridge

        # Start the idler thread:
        idler = Idler(M, b)
        idler.start()

        while True and not idler.error:
            # print "Idler new e-mail: %s" % idler.newMail
            time.sleep(60)  # prevent code from  completion..

    except:  # (imaplib2.IMAP4.abort, imaplib2.IMAP4.error) as e:
        print("Disconnected.  Trying again.")
    finally:
        print("Logging out and killing thread...")
        M.logout()
        M.close()
        idler.kill()
        idler.join()
        time.sleep(60)
