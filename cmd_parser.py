import json
import os
import re
import textfsm
from pathlib import Path
 
 
PROJECT_Dir = Path(__file__).parents[1] # Save the project directory which is one level up from the module file location
 
# Location of template files used by the TextFSM package to parser the NE command
# responses. Dictionary of NE commands with supporting templates available to parse
# NE output
TemplateBase = os.path.join(PROJECT_Dir, 'cmd_templates')
TemplateDir = {
    'ne': os.path.join(TemplateBase, 'ne'),
    'root': os.path.join(TemplateBase, 'root', 'linux'),
    'dbgCutThru': os.path.join(TemplateBase, 'root', 'dbgCutThru'),
    }
 
# key: val
# <command> : <template file>
Cmd_to_Template_Map = {
        # Linux Mapping
        'root' :{
                'bootcmd r': 'bootcmd r',
                'bm.power': 'bm.power',
                'bm.report': 'bm.report',
                'bm.status': 'bm.status',
                'last': 'last',
                'last reboot': 'last',
                'last shutdown': 'last',
                'last -x reboot': 'last',
                'last -x shutdown': 'last',
                'ls -l': 'ls -l',
                'ls -al': 'ls -l',
                'pwd': 'pwd',
                'uptime': 'uptime',
                'vlan_setm r ilan': 'vlan_setm r ilan',
                'vlan_setm r net': 'vlan_setm r net',
                'who': 'who',
                },
    # dbgCutThru Mapping
    'dbgCutThru': {},
 
    # NE Mapping
    'ne': {
        'paging status': 'paging status',
        'show card': 'show card',
        'show card inv': 'show card inv',
        'show card inv *': 'show card inv *',
        'show condition': 'show condition',
        'show firmware ne': 'show firmware ne',
        'show interface brief': 'show interface brief',
        'show interface topology *': 'show interface topology *',
        'show odukxc brief': 'show odukxc brief',
        'show pf': 'show pf',
        'show slot *': 'show slot *',
        'show software ne brief': 'show software ne brief',
        'show version': 'show version',
        'show xc *': 'show xc *',
        'who': 'who',
         },
}
 
 
def zip_results(cmd,  stdout, domain):
    dict_outout= {}
 
    # Check if user passed in a text string for stdout and if so, parse the text.
    # If not, we will assume they passed in a already parsed stdout and just want
    # the zipped version of the date
    if isinstance(stdout, str) is True:
        parsed_results = parse_cmd(cmd, stdout, domain)
    else:
        parsed_results = stdout
 
    try:
        for template_file, info in parsed_results.items():
            header, parsed_text = info
            dict_outout.update({template_file: to_dict(header, parsed_text)})
    except AttributeError:
        # something went wrong in parsing the current command response, continue
        pass
    return dict_outout
 
 
def to_dict(header, result)-> list:
    """
    Helper func - takes as its input header info and results test that is consistent with the output
    of textFSM header attribute and ParseText method calls and converts the resulting information
    into a list of dicts
    :param header: textFSM compliant header list
    :param result: textFSM compliant parsing result
    :return:
    """
    output = []
    for item in result:
        try:
            output.append(dict(zip(header, item)))
        except TypeError:
            raise
    return output
 
def get_templates(cmd: str, domain: str) -> list:
    """
    Lookup the command string passed into the NE and determine if a template or
    set of template files exists to parse the command output. If so return the
    a list of template file IDs, read-only, otherwise return None
 
    :param cmd: Cmd string, with params
    :param domain: used to direct the command parser to the correct template file
    :return: None or TextFSM Template file ID
    """
    # ToDo - provide method to morph commands with multiple args that produce input that can be parsed
    #        using the same template to a common template name, avoid duplicate entries, e.g. last
    if 'alm' == cmd:
        cmd = 'show condition'
    elif '.bm.power' in cmd:
        cmd = 'bm.power'
    elif '.bm.report' in cmd:
        cmd = 'bm.report'
    elif '.bm.status' in cmd:
        cmd = 'bm.status'
    elif re.search('show card \d+/\d+', cmd) is not None:
        cmd = 'show card'
    elif re.search('show card inv \d+/\d+', cmd) is not None:
        cmd = 'show card inv'
    elif re.search('show pf \d+/\d+', cmd) is not None:
        cmd = 'show pf'
    elif 'uptime' in cmd:
        cmd = 'uptime'
 
    try:
        template_dir_name = os.path.join(TemplateDir[domain], Cmd_to_Template_Map[domain][cmd])
 
        # Determine if template path is a directory contains more than one temple to process
        # # output from the current command
        dir_names = []
        if os.path.isdir(template_dir_name) is False:
            dir_names.append(template_dir_name)
        else:
            # Is a directory so collect the path and files names for all present
            # Iterate directory
            for path in os.listdir(template_dir_name):
                # check if current path is a file
                if os.path.isfile(os.path.join(template_dir_name, path)):
                    dir_names.append(path)
 
        # Open each template file found and store its file ID
        fids = []
        for dn in dir_names:
            fids.append(open(os.path.join(template_dir_name, dn), "r"))
 
        return fids
    except KeyError:
        return []
    except FileNotFoundError:
        return []
 
 
def parse_cmd(cmd_str: str, cmd_result: str, domain: str) -> dict:
    """
    Lookup the template file ID to parse the current command result information. If one exists, use
    the template to parse the information. If not, return None.
 
    Some command responses contain a list of tuples [(header, parsed command),(header, parsed command),....]
    Some command responses require complex command parsing. to support this the utility will can call multiple
     command parses and return the aggregate results. The output of the format is a list of dictionaries
     whose parsed output requires multiple header, parsed text information.
        {template_name: (header info, [dicts containing parsed output]), template_name: (header info, [dicts containing parsed output]),...}
 
 
 
    :param cmd_str: Original NE command string
    :param cmd_result: Resulting command string response from the NE
    :param domain: used to direct the command parser to the correct template file
    :return: (dict) -
        {template_name: (header info, [dicts containing parsed output]), template_name: (header info, [dicts containing parsed output]),...}
        else None
    """
    if domain != 'na':
        template_fids = get_templates(cmd_str, domain)
        result = {}
        for t_fid in template_fids:
            if t_fid is not None:
                # Extract template file name including the removal or any
                # file extension that may be present on the right side of the
                # file name.
                # NOTE- Users should not label template files with a dot-extension
                # that is intended to be part of the template name since it will be striped
                template_filename = os.path.basename(t_fid.name).split('.')[0]
 
                # Call unsupported textFSM package with debug support
                #re_table = textfsm.TextFSM(t_fid, debug=True)
                re_table = textfsm.TextFSM(t_fid)
 
                header = re_table.header
                # result.append((header, re_table.ParseText(cmd_result)))
                result.update({template_filename: (header, re_table.ParseText(cmd_result))})
        if bool(result):
            return result
 
    return {}
