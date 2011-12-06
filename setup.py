import sys
from distutils.core import setup

if sys.version < '2.7':
    print "Python version 2.7 or higher is required " + \
         "for System Storage Manager to run correctly!"
    sys.exit(1)

setup(
    name='SystemStorageManager',
    version='0.1dev',
    author='Lukas Czerner',
    author_email='lczerner@redhat.com',
    maintainer='Lukas Czerner',
    maintainer_email='lczerner@redhat.com',
    packages=['ssmlib', 'ssmlib.backends'],
    scripts=['bin/ssm'],
    description='System Storage Manager - A single tool to manage your storage',
    license='GNU General Public License version 2 or any later version',
    long_description=open('README').read(),
    requires=['argparse', 'itertools'],
    platforms=['Linux'],
)
