#!/usr/bin/env python
#
# Paramiko Expect Demo
#
# Written by Fotis Gimian
# http://github.com/fgimian
#
# This script demonstrates the SSHClientInteraction clast in the paramiko
# expect library
#
import time
import os
import re
import sys
import platform
import traceback
import paramiko
from paramiko_expect import SSHClientInteraction
 
from utils.cmd_logger import CmdLogger
from utils.conn_Info import RootConnInfo, AdminConnInfo, get_password, get_port
 
RE_EXP = {
        'ansi escape': re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]) '),
        'more prompt': re.compile('\.\.\.more\? y=\[yes\]', re.MULTILINE),
        'root prompt': re.compile("^\s*[b']*root@.*# "),
        'last login': re.compile("\s*Last login:.* "),
        'valid NE prompt chars': re.compile('([a-zA-Z0-9-_+~!@#$%^&*.,:`]+#\s*$)'),
}
 
class SSH_Conn_Failure(Exception):
    def __init__(self, host:str, user:str, port:int, err, message="SSH connection failed"):
        self.host = host
        self.port = port
        self.message = f'{message}-{err}: {host}@{user} (via {port})'
        print(self.message)
        super().__init__(self.message)
        sys.exit()
 
 
def ping_test(hostname:str)-> None:
    """
    Generic utility function to test for reachability to hostname. Raises
    SSH_Conn_Failure if the hostname is not reachable, else None
 
    The utility is OS agnostic.
    :param hostname: IP or DNS host name
    :return:
    """
    # Test if the utility is running on Windows and set the
    # appropriate ping test option. If not Windows it is assumed
    # we're running on a Unix, Linux or mac Osx
    if platform.system().lower() == "windows":
        option = '-n'
    else:
        option = '-c'
    # Ping hostname
    response = os.system(f'ping {option} 1 ' + hostname)
    if response == 0:
        print(hostname, f'is up: {response}')
    else:
        SSH_Conn_Failure(hostname, '', -1 , '', message='Host not reachable')
 
class SSH_Connection:
    def __init__(self, host: str, user:str, port: int=None, log_action='replace',
                 rcv_decoding: str='ascii', timeout=30):
        """
        Class that provide the logic need to open and maintain an SSH connection suitable for
        the execution of non-interactive shell, execute, commands or interactive shell command
        operation via channels.
        Note: In normal operation to environment variables are required to be set
            NE_Root_Password
            NE_Admin_Password
 
        :param host: NE host IP address
        :param user: User login string - [root | admin]
        :param port: Optional - normally set automatically based on user string and environment variables
        :param log_action: Optional - log_action: [replace | append | clone]
        :param rcv_decoding: Optional - Codec type used to decode NE responses
        """
        ping_test(host)
 
        self.user = user
        self.host = host
        self.session = None
        self.port = port
        self.rcv_decoding = rcv_decoding     # channel rcv data decoding type
        self.timeout=timeout
        self.root_prompt = 'root.*# '
        self.domain = 'root'
 
        # ssh Connection object
        @property
        def ssh(self):
            return self.__ssh
 
        @ssh.getter
        def ssh(self):
            return self.__ssh
 
        @ssh.setter
        def ssh(self, value):
            self.__ssh = value
 
        @property
        def port(self):
            return self.__port
 
        @port.getter
        def port(self):
            return self.__port
 
        @port.setter
        def port(self, value):
            self.__port = value
 
        @property
        def user(self):
            return self.__user
 
        @user.setter
        def user(self, value):
            # Ensure the correct port is set when user set user name
            self.__user = value
            self._set_port()
 
        @user.getter
        def user(self):
            return self.__user
 
        # Create command logger class to record all actions and responses for all hosts. If the user
        # passed in an already created CmdLogger object just use it.
        if isinstance(log_action, CmdLogger) is False:
            self.logger = CmdLogger(self.host, action=log_action)
        else:
            self.logger = log_action
 
        # Set self.port based on user string
        self._set_port()
 
 
    def __del__(self):
        # Close the SSH connection and dump file
        try:
            self.closeConnection()
        except:
            pass
 
 
    def openConnection(self):
        try:
            # Create a new SSH client object
            self.session = paramiko.SSHClient()
 
            # Set SSH key parameters to auto accept unknown hosts
            self.session.load_system_host_keys()
            self.session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            start_time = time.monotonic()
 
            # Connect to the host
            self.session.connect(hostname=self.host, username=self.user, password=get_password(self.user), port=self.port, timeout=self.timeout)
 
        except TimeoutError as err:
            # Connection failure
            cmd_duration = round(time.monotonic() - start_time, 4)
            self.logger.log_cmd(f'connect(port={self.port}, \
                                    username={self.user}, password=****)', 'na', f'Connection Failed: {err}',
                                cmd_duration, self.domain)
            SSH_Conn_Failure(self.host, self.user, self.port, err)
        except Exception:
            traceback.print_exc()
        finally:
            # Log connection status
            cmd_duration = round(time.monotonic() - start_time, 4)
            self.logger.log_cmd(f'connect(port={self.port}, \
                                    username={self.user}, password=****)', 'na', f'Connected: {self.host}',
                                cmd_duration, self.domain)
 
    def closeConnection(self):
        try:
            self.session.close()
            # Dump this hosts Cmd_log dictionary as a JSON file for later processing
            self.logger.cmd_log_2_json()
        except:
            pass
 
    def _set_port(self)-> None:
        """
        set self.port to the value associated with the Admin or Root
        port values associated with the NE users.
 
        NOTE: If the port was supplied by user on object creation, self.port
                was set already and no action is needed by this function
 
        :return: None - sets self.port
        """
        if self.port is not None:
            pass
        self.port = get_port(self.user)
 
    def shell(self, timeout: int=30, display: bool=False) -> SSHClientInteraction:
        """
        Creates an interactive shell within the current session
        :param timeout: Command response timeout
        :param display: If True displays command stdout on user terminal
        :return: SSHClientInteraction interactive shell object
        """
 
        # Create a client interaction class which will interact with the host
        interact = SSHClientInteraction(self.session, timeout=timeout, display=display)
        # Run the first command and capture the cleaned output, if you want
        # the output without cleaning, simply grab current_output instead.
        interact.expect(self.root_prompt)
 
        return interact
