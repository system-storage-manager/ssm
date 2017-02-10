#!/usr/bin/env python

import re
import sys, os

# Add into PATH so we don't use installed ssmlib, but the one we are developing
sys.path.insert(0, os.path.join( os.path.dirname(os.path.realpath(__file__)), ".." ))

from ssmlib import main

SYNOPSIS_INC = "src/synopsis.inc"
OPTIONS_DIR = "src/options/"
SSM_OPTIONS_INC = OPTIONS_DIR + "ssm_options.inc"
CREATE_OPTIONS_INC = OPTIONS_DIR + "create_options.inc"
LIST_OPTIONS_INC = OPTIONS_DIR + "list_options.inc"
REMOVE_OPTIONS_INC = OPTIONS_DIR + "remove_options.inc"
RESIZE_OPTIONS_INC = OPTIONS_DIR + "resize_options.inc"
CHECK_OPTIONS_INC = OPTIONS_DIR + "check_options.inc"
SNAPSHOT_OPTIONS_INC = OPTIONS_DIR + "snapshot_options.inc"
ADD_OPTIONS_INC = OPTIONS_DIR + "add_options.inc"
MOUNT_OPTIONS_INC = OPTIONS_DIR + "mount_options.inc"

SSM_USAGE_INC = OPTIONS_DIR + "ssm_usage.inc"
CREATE_USAGE_INC = OPTIONS_DIR + "create_usage.inc"
LIST_USAGE_INC = OPTIONS_DIR + "list_usage.inc"
REMOVE_USAGE_INC = OPTIONS_DIR + "remove_usage.inc"
RESIZE_USAGE_INC = OPTIONS_DIR + "resize_usage.inc"
CHECK_USAGE_INC = OPTIONS_DIR + "check_usage.inc"
SNAPSHOT_USAGE_INC = OPTIONS_DIR + "snapshot_usage.inc"
ADD_USAGE_INC = OPTIONS_DIR + "add_usage.inc"
MOUNT_USAGE_INC = OPTIONS_DIR + "mount_usage.inc"


class GenerateIncludes(object):

    def __init__(self):
        self.storage = main.StorageHandle()
        self.ssm_parser = main.SsmParser(self.storage, 'ssm')
        self.parser = self.ssm_parser.parser

    def _parse_usage(self, usage):
        s = re.compile('usage: |\n')
        res = s.sub(r'', usage)
        s = re.compile('\s\s+')
        res = s.sub(r' ', res)
        s = re.compile('(--\w+|-.)')
        res = s.sub(r'**\1**', res)
        s = re.compile('([a-z]+)\s+')
        res = s.sub(r'**\1** ', res)
        return res

    def _write_message(self, message, filename):
        with open(filename, 'w') as f:
            f.write(message)

    def format_synopsis(self, parser):
        return "{0}\n\n".format(self._parse_usage(parser.format_usage()))

    def write_ssm_usage(self):
        message = self.format_synopsis(self.ssm_parser.parser)
        self._write_message(message, SSM_USAGE_INC)

    def write_create_usage(self):
        message = self.format_synopsis(self.ssm_parser.parser_create)
        self._write_message(message, CREATE_USAGE_INC)

    def write_list_usage(self):
        message = self.format_synopsis(self.ssm_parser.parser_list)
        self._write_message(message, LIST_USAGE_INC)

    def write_remove_usage(self):
        message = self.format_synopsis(self.ssm_parser.parser_remove)
        self._write_message(message, REMOVE_USAGE_INC)

    def write_resize_usage(self):
        message = self.format_synopsis(self.ssm_parser.parser_resize)
        self._write_message(message, RESIZE_USAGE_INC)

    def write_check_usage(self):
        message = self.format_synopsis(self.ssm_parser.parser_check)
        self._write_message(message, CHECK_USAGE_INC)

    def write_snapshot_usage(self):
        message = self.format_synopsis(self.ssm_parser.parser_snapshot)
        self._write_message(message, SNAPSHOT_USAGE_INC)

    def write_add_usage(self):
        message = self.format_synopsis(self.ssm_parser.parser_add)
        self._write_message(message, ADD_USAGE_INC)

    def write_mount_usage(self):
        message = self.format_synopsis(self.ssm_parser.parser_mount)
        self._write_message(message, MOUNT_USAGE_INC)

    def write_usage(self):
        self.write_ssm_usage()
        self.write_create_usage()
        self.write_list_usage()
        self.write_remove_usage()
        self.write_resize_usage()
        self.write_check_usage()
        self.write_snapshot_usage()
        self.write_add_usage()
        self.write_mount_usage()

    def _format_options(self, parser):
        help = parser.format_help()
        out = False
        message = ""
        for line in help.split('\n'):
            if line == '':
                out = False
            if out:
                message += "{0}\n".format(line[2:])
            if line == "optional arguments:":
                out = True
        return message

    def write_option_includes(self):
        message = self._format_options(self.parser)
        self._write_message(message, SSM_OPTIONS_INC)

        message = self._format_options(self.ssm_parser.parser_create)
        self._write_message(message, CREATE_OPTIONS_INC)

        message = self._format_options(self.ssm_parser.parser_list)
        self._write_message(message, LIST_OPTIONS_INC)

        message = self._format_options(self.ssm_parser.parser_remove)
        self._write_message(message, REMOVE_OPTIONS_INC)

        message = self._format_options(self.ssm_parser.parser_resize)
        self._write_message(message, RESIZE_OPTIONS_INC)

        message = self._format_options(self.ssm_parser.parser_check)
        self._write_message(message, CHECK_OPTIONS_INC)

        message = self._format_options(self.ssm_parser.parser_snapshot)
        self._write_message(message, SNAPSHOT_OPTIONS_INC)

        message = self._format_options(self.ssm_parser.parser_add)
        self._write_message(message, ADD_OPTIONS_INC)

        message = self._format_options(self.ssm_parser.parser_mount)
        self._write_message(message, MOUNT_OPTIONS_INC)

includes = GenerateIncludes()

includes.write_option_includes()
includes.write_usage()
