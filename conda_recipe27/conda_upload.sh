# Only need to change these two variables
PKG_NAME=tofu
USER=Didou09

OS=linux-64
mkdir ~/conda-bld
conda config --set anaconda_upload no
conda update -n root conda-build
#conda config --add channels pypi
export CONDA_BLD_PATH=~/conda-bld
#export VERSION=`date +%Y.%m.%d`
echo ""
echo "VERSION"
echo $VERSION
export VERSION=$(head -n 1 version.txt)
echo $VERSION

echo ""
echo $VERSION
echo $RECIPE
conda build $RECIPE

echo "uploading..."
pwd .
ls .

echo "CONDA_BLD_PATH"
echo $CONDA_BLD_PATH
ls $CONDA_BLD_PATH/$OS
echo ""
echo $PKG_NAME-$VERSION-$VADD.tar.bz2

echo ""
echo "RECIPE"
ls $RECIPE

anaconda -t $CONDA_UPLOAD_TOKEN upload -u $USER -l nightly $CONDA_BLD_PATH/$OS/$PKG_NAME-$VERSION-$VADD.tar.bz2 --force
