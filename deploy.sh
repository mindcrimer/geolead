#!/bin/bash
git pull
source venv/bin/activate
find . -type f -name "*.pyc" -exec rm -f {} \;
pip install -U pip setuptools pip-tools
pip install -r requirements.txt
yes "yes" | python manage.py migrate
cd static/
npm install
cd ../
python manage.py collectstatic --noinput
chown rtadmin:rtadmin -R .
chmod o+r -R public/
chmod 0777 public/static/node_modules/phantomjs/bin/phantomjs
touch venv/uwsgi.reload
