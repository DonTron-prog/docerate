#!/bin/bash
# Blog management script

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Check if conda environment exists
if ! conda env list | grep -q "^blog "; then
    echo -e "${YELLOW}Creating conda environment 'blog'...${NC}"
    conda create -n blog python=3.11 -y
    conda activate blog
    pip install -r requirements.txt
else
    conda activate blog
fi

# Run the generator with the given command
if [ $# -eq 0 ]; then
    echo "Usage: ./blog.sh [build|serve|watch|new]"
    echo "  build  - Build the static site"
    echo "  serve  - Build and serve locally"
    echo "  watch  - Watch for changes and rebuild"
    echo "  new    - Create a new post"
else
    echo -e "${GREEN}Running: python generator.py $@${NC}"
    python generator.py "$@"
fi