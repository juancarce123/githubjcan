import json
import os
import re
import datetime
import queue
 
from utils.cmd_parser import parse_cmd, to_dict, zip_results
 
RUN_START = datetime.datetime.now()   # Record the start time for the current run. Used to calculate elapsed time
HOST_TZ = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()  # TZ for the machine running the app
_Log_Q = queue.Queue
 
class LoggerAttributeError(Exception):
    """
    Customer Exception
    Call in-place of the generic AttributeError exception if a user passes
    in an invalid logger action string
    """
    def __init__(self, action: str, message: str = "Valid actions [clone | append | replace (default)"):
        self.action = action
        self.message = f'Invalid action "{action}" - {message})'
        print(self.message)
        super().__init__(self.message)
 
class FileNotOpen(Exception):
    """
    Customer Exception
    Call in-place of the generic AttributeError exception if a user passes
    in an invalid logger action string
    """
    def __init__(self, message: str = "Log file not open, write request blocked"):
        self.message = f'Invalid action "{message}'
        print(self.message)
        super().__init__(self.message)
 
 
def _file_max_suffix(pattern: str, ext='json') -> str:
    """
    Looks for files that match pattern and return a suffix that is one more than the max
    suffix that matches the file pattern (e.g. file-10.json ==> return file-11.json. If the file
    is not present returns file.json
 
    :param pattern: file pattern
    :param ext: (Optional) File extension
    :return: file suffix as noted above
    """
    matching_file_suffix = []   # array to hold file name suffix
    pattern_re = re.compile(f'({pattern})-?([0-9]*).{ext}')
 
    # Look through directory for all files matching pattern. When found extract file suffix and store as integer in
    # array. At the end we will look for the max suffix and return one more
    for f in os.listdir(os.curdir):
        match = pattern_re.search(f)  # capture only integer before ".csv" and EOL
        if match is None:
            continue
 
        if match.group(1) == pattern and match.group(2) == '':
            matching_file_suffix.append(0)
        elif match.group(1) == pattern and match.group(2) != '':
            # Add suffix for the file whose name matches pattern
            matching_file_suffix.append(int(match.group(2)))
 
    if bool(matching_file_suffix) is False:
        # the file pattern does not exist
        return f'{pattern}.{ext}'
    else:
        # File pattern exists, return one more than the current max matched file suffix
        return f'{pattern}-{max(matching_file_suffix) + 1}.{ext}'
 
def _json_prefix() -> str:
    return '[\n'
def _json_delim() -> str:
    return ',\n'
def _json_suffix() -> str:
    return '\n{ }]'
 
 
# ToDo: add param to change location of default dir for log files from CWD to somewhere else
class CmdLogger:
    def __init__(self, host: str, action: str = 'open'):
        """
        :param host: IP Address
        :param action:  - Open new log file (open)
                        - append to previously opened file (append)
        :param domain: used to direct the command parser to the correct template file
        """
        self.host = host
        self.action = action
        self.timezone_NE = 'not set'
        self._log_fid = None
 
        # Produce date suffix for the file as yyyy_mm-dd
        # Although file writes are not thread-safe multiple shells opened within the same user script
        # run synchronously, hence multiple shells can use the same logger safely
        date = datetime.datetime.today().strftime("%Y_%m_%d")
        if self.action.lower() == 'open':
            file_name = _file_max_suffix(f'log-{self.host}-{date}')
            self._log_fid = open(file_name, 'w')
            self._log_fid.write(_json_prefix())
            self._log_fid.flush()
        elif self.action.lower() == 'append':
            if self._log_fid is not None:
                LoggerAttributeError(action, message = "Append action required prior to open file")
        else:
            raise LoggerAttributeError(self.action)
 
    def __del__(self):
        try:
            self._close
        except AttributeError:
            raise
 
    def _close(self):
        self._log_fid.write(_json_suffix())
        self._log_fid.close()
 
    def log_comment(self, cmt: str, telnet_host: str = None) -> None:
        """
        Provide shorthand call to logger that allows the suer to insert a comment into the log file
        :param cmt: User comment to be inserted into log file
        :param telnet_host: (Optional) IP address of telnet host when a telnet session
                                        through existing SSH session is in-use
        :return: None - inserts record into log file
        """
        self.log_cmd(f'Comment: {cmt}', 'na', 'na', 0.0, 'na', telnet_host=telnet_host)
 
    def build_log_entry(self, stdin: str, stdout: str, stderr: str, cmd_duration: float, domain: str, telnet_host: str = None) -> dict:
        """
        Helper function of log_cmd and use utility to construct a log entry
        NOTE: Params must align with those of log_cmd
 
        :param stdin: Input send to stdin
        :param stdout: Output from stdout
        :param stderr: Result from stderr
        :param cmd_duration: duration of command execution in secs
        :param telnet_host: (Optional) IP address of telnet host when a telnet session
                                        through existing SSH session is in-use
        :return: dict - last log result
        """
 
        # convert the parsed command output results and list of tuples contain (header, parsed values) into a
        # dictionary with all header values representing the key for all values returned
        dict_output = zip_results(stdin,  stdout, domain)
 
        # Build the complete log entry
        rtn = {'timestamp': str(datetime.datetime.now()),
                'host': self.host,
                'stdin': str(stdin),
                'stdout': str(stdout),
                'stderr': str(stderr),
                'results': dict_output,
                'cmd_duration (secs)': cmd_duration,
                'elapsed_time (h:m:s)': str(datetime.datetime.now() - RUN_START),
                'timezone_NE': self.timezone_NE,
                'timezone_host': HOST_TZ,
               }
        if telnet_host is not None:
            rtn.update({'telnet_host': telnet_host})
        return rtn
 
    def log_cmd(self, stdin: str, stdout: str, stderr: str, cmd_duration: float, domain: str, telnet_host: str = None) -> dict:
        """
        Populate an ordered Dict with the results of the command run against a
        specific host
 
        :param stdin: Input send to stdin
        :param stdout: Output from stdout
        :param stderr: Result from stderr
        :param cmd_duration: duration of command execution in secs
        :param telnet_host: (Optional) IP address of telnet host when a telnet session
                                through existing SSH session is in-use
        :return: dict - last log result
        """
        rtn = self.build_log_entry(stdin, stdout, stderr, cmd_duration, domain, telnet_host=telnet_host)
        if self._log_fid is not None:
            self._log_fid.write(f"\t\t{json.dumps(rtn, indent=4)}{_json_delim()}")
            self._log_fid.flush()
        else:
            FileNotOpen()
        return rtn
 
 
if __name__ == '__main__':
    print(_file_max_suffix('log-135.104.221.100-2022_08_02'))