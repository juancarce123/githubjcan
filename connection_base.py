#!/usr/bin/env python
#
# Paramiko Expect Demo
#
# Written by Fotis Gimian
# http://github.com/fgimian
#
# This script demonstrates the SSHClientInteraction class in the paramiko
# expect library
#
 
import re
import time
# https://ktbyers.github.io/netmiko/docs/netmiko/
# https://github.com/ktbyers/netmiko/blob/develop/EXAMPLES.md
from netmiko import ConnectHandler
from netmiko.exceptions import ReadTimeout, NetmikoTimeoutException, NetmikoAuthenticationException
from utils.conn_Info import get_port, get_password
from utils.cmd_logger import CmdLogger
 
# ToDo provide login support for PSS4 prompt, simple # (e.g. 135.104.217.32)
PROMPT_STRINGS = {'admin': r'\s*\S+#\s*$',
                  'more': '\.\.\.more\? y=\[yes\]',
                  # 'root': "^\s*root@.*",
                  'root': ".*#.*",
                  'telnet login': '.*login.*',
                  'telnet': '.*#.*',
                  'dbgCutThru': 'dbgCut>',
    }
RE_EXP = {
        'ansi': re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]) '),
        'admin': re.compile(PROMPT_STRINGS['admin']),
        'more': re.compile(PROMPT_STRINGS['more'], re.MULTILINE),
        'root': re.compile(".*root@.*"),
        'telnet': re.compile(PROMPT_STRINGS['telnet']),
        'admin more': re.compile(f"{PROMPT_STRINGS['admin']}|{PROMPT_STRINGS['more']}", re.MULTILINE),
        'last login': re.compile("\s*Last login:.* "),
        'telnet login': re.compile(PROMPT_STRINGS['telnet login']),
        'valid prompt chars': re.compile('([a-zA-Z0-9-_+~!@#$%^&*.,:`]+#\s*$)'),
}
 
class SSH_Conn_Failure(Exception):
    def __init__(self, host:str, user:str, port:int, err, message="SSH connection failed"):
        self.host = host
        self.port = port
        self.message = f'{message}-{err}: {host}@{user} (via {port})'
        print(self.message)
        super().__init__(self.message)
 
class SSH_Cmd_Response_Failure(Exception):
    def __init__(self, host:str, cmd:str, err, message="SSH command response failure"):
        self.host = host
        self.cmd = cmd
        self.message = f'{message}-{err}: {host} - {cmd})'
        print(self.message)
        super().__init__(self.message)
 
 
class Connection:
    def __init__(self, host: str, user: str, log_action='open', timeout: float=30.0, read_timeout: float=60.0,
                 session_log: str=None, response_return="\n"):
        self.host=host
        self.user=user
        self.port = get_port(user)
        self.timeout = timeout      # ssh connection timeout
        self.read_timeout = read_timeout  # send_command respond timeout
        self.domain = 'root'
        self.response_return=response_return
 
        # Create command logger class to record all actions and responses for all hosts. If the user
        # passed in an already created CmdLogger object just use it.
        if isinstance(log_action, CmdLogger) is False:
            self.logger = CmdLogger(self.host, action=log_action)
        else:
            # Set logger to already created CmdLogger object the user passed in. We will be sharing the
            # log file already present
            self.logger = log_action
 
        try:
            self.ssh = ConnectHandler(device_type='linux',
                                        host=host,
                                        port=self.port ,
                                        username=user,
                                        password=get_password(user),
                                        timeout=timeout,
                                        session_log=session_log,
                                        response_return=response_return)
            self._default_prompt = f"{PROMPT_STRINGS[self.user]}|{PROMPT_STRINGS['more']}|{self.ssh.base_prompt}"
            self._default_hostname = self.ssh.send_command('hostname', read_timeout=read_timeout,
                                                           expect_string=self._default_prompt)
 
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as err:
            self._default_prompt = ''
            self.ssh = None
            self.logger.log_cmd(f'{user} Host connection failed', 'na', err, 0.0, self.domain)
            SSH_Conn_Failure(host, user, self.port, err,
                                        message="SSH - TCP connection to device failed.")
            return
 
 
        try:
            self._home_prompt=self.ssh.base_prompt       # For users that inherit the class and login other machines
                                                         # to determine if they have returned home
        except AttributeError:
            raise
 
        # Set the self.logger.timezone_ME parameter to make the log information more useful
        self.get_TZ()
 
        # Update globals
        self._update_globs('root')
 
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
 
 
    def __del__(self):
        # Close the SSH connection and dump file
        try:
            self.ssh.disconnect()
        except:
            pass
 
    def _update_globs(self, user: str):
        """
        Placeholder
        :param user:
        :return:
        """
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
 
    def get_TZ(self):
        output = self.ssh.send_command('date', read_timeout=self.read_timeout)
        m = re.search("\S+\s*\S+\d{1,2}\s*\d{2}:\d{2}:\d{2}\s*(\S+)", output)
        if m is not None:
            self.logger.timezone_NE = m.groups(1)[0]
        else:
            self.logger.timezone_NE = 'Not Set'
 
    def reset_root_params(self):
        self.user = 'root'
        self.port = get_port(self.user)
        self.domain = 'root'
        self.login_success = False
        self.ssh.base_prompt = self._home_prompt
 
    def verify_user_prompt(self, user):
        try:
            output = self.ssh.find_prompt(pattern=PROMPT_STRINGS[user])
            #print(f"{__name__}.verify_user_prompt - user: {user}  -  OUT: {output}")
 
            if RE_EXP[user].search(output) is None:
                self.ssh.base_prompt = ".*[#~]?\s*$"
                return False
            self.ssh.base_prompt = output.strip()
        except (ReadTimeout, ValueError) as err:
            SSH_Conn_Failure(self.host, user, self.port, err,
                             message="verify_user_prompt - Failed to read prompt.")
            return False
 
        return True
 
    def login_verification(self, user_login: str) -> None:
        """
        Call verify prompt which extracts and verifies prompt format matches the user specified
        :param: user_login: [admin | root]
        :return: None
        """
 
        # Send a null string to produce a line that contains only the command-line prompt
        if self.verify_user_prompt(user_login) is True:
            self.logger.log_cmd(f'{user_login} Login verification via root login success', self.ssh.base_prompt, '', 0.0, self.domain)
            return True
 
        self.logger.log_cmd(f'{user_login} Login verification failed', self.ssh.base_prompt, 'na', 0.0, self.domain)
        return False
 
    def execute(self, cmd: str, prompt: str='', read_timeout: float=None, cmd_verify=True) -> dict:
        """
        Basic execution method
        :param cmd: NE Command string
        :param prompt: (Optional) regular expression expected prompt
        :param read_timeout: (Optional) Command response timeout (secs)
        :param cmd_verify: (Optional) If True look for command in response, else produce Read_Timeout exception
                                        if not found. If False, skip check for command in response
        :return: Last command response as a log response dictionary
        """
        # Check if the connection is still up before we attempt to execute a command
        try:
            if self.ssh.is_alive() is False:
                self.logger.log_cmd('ssh.is_alive()', '', 'abnormal connection closure', 0.0, self.domain)
                return
        except AttributeError:
            raise
 
        # Check if the user is asking to override the class
        # attributes below for this specific execute call
        if prompt == '':
            prompt = self._default_prompt
        if read_timeout is None:
            read_timeout = self.read_timeout
 
        start_secs = time.monotonic()
        try:
            # Send the command and look for the expected prompt, aka command completion, or "More" prompt
            output = self.ssh.send_command(cmd, read_timeout=read_timeout, expect_string=prompt, cmd_verify=cmd_verify)
            output = self.ssh.strip_ansi_escape_codes(output)
            # Test for More prompt in output. If present, sen "Y" to collect full response
            while (RE_EXP['more'].search(output) is not None):
                more_out = self.response_return + self.ssh.send_command_timing('y',
                                                                        read_timeout=self.read_timeout,
                                                                        cmd_verify=False)
                output += self.response_return + self.ssh.strip_ansi_escape_codes(more_out)
                # Check is the last chuck of output data contained another more
                # prompt. If so, continue. If not, break
                if RE_EXP['more'].search(more_out) is None:
                    break
        except ReadTimeout as err:
            output = 'Failed command response'
            cmd_duration = round(time.monotonic() - start_secs, 4)
            self.logger.log_cmd(f"{self.host}: {cmd}", '', err, cmd_duration, self.domain)
            SSH_Cmd_Response_Failure(self.host , cmd , err)
 
        # Log the command response and save the newly created log
        cmd_duration = round(time.monotonic() - start_secs, 4)
        rtn = self.logger.log_cmd(cmd, output, '', cmd_duration, self.domain)
        print(f'Host:{self.host} - {cmd} - {cmd_duration} secs')
 
        # Return the last command added to the logger store from above
        return rtn
 
 
 
