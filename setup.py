import os
import sys
from distutils.core import setup

VERSION='0.1-alpha'
DOC_BUILD='doc/_build/'

if sys.version < '2.6':
    print "Python version 2.6 or higher is required " + \
         "for System Storage Manager to run correctly!"
    sys.exit(1)

setup(
    name='SystemStorageManager',
    version=VERSION,
    author='Lukas Czerner',
    author_email='lczerner@redhat.com',
    maintainer='Lukas Czerner',
    maintainer_email='lczerner@redhat.com',
    packages=['ssmlib', 'ssmlib.backends'],
    scripts=['bin/ssm'],
    description='System Storage Manager - A single tool to manage your storage',
    license='GNU General Public License version 2 or any later version',
    long_description=open('README').read(),
    requires=['argparse', 'itertools', 'tempfile', 'threading', 'subprocess',
              'datetime', 're', 'os', 'sys', 'stat'],
    platforms=['Linux'],
    data_files=[('/usr/share/man/man8', ['doc/_build/man/ssm.8']),
                ('/usr/share/doc/ssm-{0}'.format(VERSION),
                    ['README', 'TODO', 'CHANGES', 'COPYING'])]
)

