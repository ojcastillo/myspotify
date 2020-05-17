if ! conda env list | grep -q 'myspotify'; then
    echo "Didn't find a 'myspotify' conda env. Setting one for you."
    conda create -n myspotify python=3.7 pip
fi

echo "Activating myspotify env"
conda activate myspotify

echo "Installing dependencies into myspotify env"
pip install -r requirements.txt
