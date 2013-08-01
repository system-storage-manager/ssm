#!/usr/bin/env python
#
# (C)2012 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# problem.py - dealing with problems and errors in ssm

import sys

__all__ = ["ProblemSet", "SsmError", "GeneralError", "ProgrammingError",
           "BadEnvVariable", "NotEnoughSpace", "ResizeMatch", "FsNotSpecified",
           "DeviceUsed", "NoDevices", "ToolMissing", "CanNotRun",
           "CommandFailed", "UserInterrupted", "NotSupported"]

# Define prompt codes
PROMPT_NONE =           0
PROMPT_UNMOUNT =        1
PROMPT_SET_DEFAULT =    2
PROMPT_IGNORE =         3
PROMPT_REMOVE =         4
PROMPT_ADJUST =         5

PROMPT_MSG = [
        None,
        'Unmount',
        'Set default',
        'Ignore',
        'Remove',
        'Adjust',
        ]

# Define problem flags
FL_NONE =               0
FL_MSG_ONLY =           2
FL_VERBOSE_ONLY =       (4 | FL_MSG_ONLY)
FL_DEBUG_ONLY =         (8 | FL_MSG_ONLY)
FL_DEFAULT_NO =         16
FL_SILENT =             32
FL_EXIT_ON_NO =         64
FL_EXIT_ON_YES =        128
FL_FATAL =              256


class SsmError(Exception):
    """Base exception class for the ssm."""
    def __init__(self, msg, errcode=None):
        super(SsmError, self).__init__()
        self.msg = msg
        self.errcode = errcode

    def __str__(self):
        return repr("Error ({0}): {1}".format(self.errcode, self.msg))


class GeneralError(SsmError):
    def __init__(self, msg, errcode=2001):
        super(GeneralError, self).__init__(msg, errcode)


class ProgrammingError(SsmError):
    def __init__(self, msg, errcode=2002):
        super(ProgrammingError, self).__init__(msg, errcode)


class FsMounted(SsmError):
    def __init__(self, msg, errcode=2003):
        super(FsMounted, self).__init__(msg, errcode)


class BadEnvVariable(SsmError):
    def __init__(self, msg, errcode=2004):
        super(BadEnvVariable, self).__init__(msg, errcode)


class NotEnoughSpace(SsmError):
    def __init__(self, msg, errcode=2005):
        super(NotEnoughSpace, self).__init__(msg, errcode)


class ResizeMatch(SsmError):
    def __init__(self, msg, errcode=2006):
        super(ResizeMatch, self).__init__(msg, errcode)


class FsNotSpecified(SsmError):
    def __init__(self, msg, errcode=2007):
        super(FsNotSpecified, self).__init__(msg, errcode)


class DeviceUsed(SsmError):
    def __init__(self, msg, errcode=2008):
        super(DeviceUsed, self).__init__(msg, errcode)


class NoDevices(SsmError):
    def __init__(self, msg, errcode=2009):
        super(NoDevices, self).__init__(msg, errcode)


class ToolMissing(SsmError):
    def __init__(self, msg, errcode=2010):
        super(ToolMissing, self).__init__(msg, errcode)


class CanNotRun(SsmError):
    def __init__(self, msg, errcode=2011):
        super(CanNotRun, self).__init__(msg, errcode)


class CommandFailed(SsmError):
    def __init__(self, msg, errcode=2012):
        super(CommandFailed, self).__init__(msg, errcode)


class UserInterrupted(SsmError):
    def __init__(self, msg, errcode=2013):
        super(UserInterrupted, self).__init__(msg, errcode)


class NotSupported(SsmError):
    def __init__(self, msg, errcode=2014):
        super(NotSupported, self).__init__(msg, errcode)


class ProblemSet(object):

    def __init__(self, options):
        self.set_options(options)
        self.init_problem_set()

    def set_options(self, options):
        self.options = options

    def init_problem_set(self):
        self.PROGRAMMING_ERROR = \
            ['Programming error detected! {0}',
             PROMPT_NONE, FL_FATAL, ProgrammingError]

        self.GENERAL_ERROR = \
            ['SSM Error: {0}!', PROMPT_NONE, FL_FATAL, GeneralError]

        self.GENERAL_INFO = \
            ['SSM Info: {0}', PROMPT_NONE, FL_NONE, None]

        self.GENERAL_WARNING = \
            ['SSM Warning: {0}!', PROMPT_NONE, FL_NONE, None]

        self.FS_MOUNTED = \
            ['Device \'{0}\' is mounted on \'{1}\'',
             PROMPT_UNMOUNT, FL_DEFAULT_NO | FL_EXIT_ON_NO, FsMounted]

        self.BAD_ENV_VARIABLE = \
            ['Environment variable \'{0}\' contains unsupported value \'{1}\'!',
             PROMPT_SET_DEFAULT, FL_EXIT_ON_NO, BadEnvVariable]

        self.RESIZE_NOT_ENOUGH_SPACE = \
            ['There is not enough space in the pool \'{0}\' to grow volume' + \
             ' \'{1}\' to size {2} KB!',
             PROMPT_NONE, FL_FATAL, NotEnoughSpace]

        self.CREATE_NOT_ENOUGH_SPACE = \
            ['Not enough space ({0} KB) in the pool \'{1}\' to create ' + \
             'volume!', PROMPT_ADJUST, FL_DEFAULT_NO | FL_EXIT_ON_NO,
             NotEnoughSpace]

        self.RESIZE_ALREADY_MATCH = \
            ['\'{0}\' is already {1} KB long, there is nothing ' + \
             'to resize!',
             PROMPT_NONE, FL_FATAL, ResizeMatch]

        self.CREATE_MOUNT_NOFS = \
            ['Mount point \'{0}\' specified, but no file system provided!',
            PROMPT_IGNORE, FL_EXIT_ON_NO, FsNotSpecified]

        self.DEVICE_USED = \
            ['Device \'{0}\' is already used in the \'{1}\'!',
             PROMPT_REMOVE, FL_DEFAULT_NO, DeviceUsed]

        self.NO_DEVICES = \
            ['No devices available to use for the \'{0}\' pool!',
             PROMPT_NONE, FL_FATAL, NoDevices]

        self.TOOL_MISSING = \
            ['\'{0}\' is not installed on the system!',
             PROMPT_NONE, FL_FATAL, ToolMissing]

        self.CAN_NOT_RUN = \
            ['Can not run command \'{0}\'',
             PROMPT_NONE, FL_FATAL, CanNotRun]

        self.COMMAND_FAILED = \
            ['Error while running command \'{0}\'',
             PROMPT_NONE, FL_FATAL, CommandFailed]

        self.NOT_SUPPORTED = \
            ['{0} is not supported!',
             PROMPT_NONE, FL_FATAL, NotSupported]

    def _can_print_message(self, flags):
        if (flags & FL_DEBUG_ONLY):
            return self.options.debug
        elif (flags & FL_VERBOSE_ONLY):
            return self.options.verbose
        else:
            return True

    def _read_char(self):
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def _ask_question(self, flags):
        if flags & FL_DEFAULT_NO:
            print "(N/y/q) ?",
        else:
            print "(Y/n/q) ?",
        ch = ''
        if self.options.interactive:
            while ch not in ['Y', 'N', 'Q', chr(13)]:
                ch = self._read_char().upper()
        elif flags & FL_DEFAULT_NO:
            ch = 'N'
        else:
            ch = 'Y'
        if ch == chr(13):
            if flags & FL_DEFAULT_NO:
                ch = 'N'
            else:
                ch = 'Y'
        print ch

        if ch == 'Y':
            return True
        elif ch == 'N':
            return False
        elif ch == 'Q':
            err = "Terminated by user!"
            raise UserInterrupted(err)

    def check(self, problem, args):
        if type(args) is not list:
            args = [args]
        message = problem[0].format(*args)
        prompt_msg = PROMPT_MSG[problem[1]]
        flags = problem[2]
        exc = problem[3]

        if (flags & FL_DEFAULT_NO):
            res = False
        else:
            res = True

        if self._can_print_message(flags) and \
           (flags & FL_MSG_ONLY or prompt_msg is None):
            print >> sys.stderr, message,
        else:
            print message,
        if not flags & FL_MSG_ONLY and prompt_msg is not None:
            print '{0}'.format(prompt_msg),
            res = self._ask_question(flags)
        else:
            print >> sys.stderr

        if (flags & FL_FATAL):
            if exc:
                raise exc(message)
            else:
                raise Exception(message)

        if ((flags & FL_EXIT_ON_NO) and (not res)) or \
           ((flags & FL_EXIT_ON_YES) and res):
            if exc:
                raise exc(message)
            else:
                raise Exception(message)

        return res

    def error(self, args):
        self.check(self.GENERAL_ERROR, args)

    def info(self, args):
        self.check(self.GENERAL_INFO, args)

    def warn(self, args):
        self.check(self.GENERAL_WARNING, args)

    def not_supported(self, args):
        self.check(self.NOT_SUPPORTED, args)
