#!/usr/bin/env bash

# this will push the generated html doc to github pages

set -euo pipefail

REPO="git@github.com:system-storage-manager/system-storage-manager.github.io.git"
TARGET="singlehtml"

DIR="$(pwd)/_build/$TARGET/"


# Clone the pages repo and move git files into the newly generated dir.
# (This is easier than to shuffle with unkwnown amount of generated files
# the other way around...)
cd $DIR/..
git clone $REPO PAGES
mv PAGES/.git PAGES/README.md $TARGET/

# We don't need the cloned dir anymore
rm -rf PAGES

cd $TARGET
# We are publishing straight HTML, so disable Jekyll and all it's stuff
# like hiding underscored files/dirs (_static in our case).
touch .nojekyll

# Now add the new files and push it up.
git add -A
git commit -m "autoupdated at $(date)"
git push -u origin master
